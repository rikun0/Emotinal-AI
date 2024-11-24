import speech_recognition as sr
import threading
from dotenv import load_dotenv
from os import environ
import google.generativeai as gemini
import queue
import re
from gtts import gTTS
import os
import pygame
import requests

# 設定
emotion = True

# .envファイルの読み込み
load_dotenv()

# Tmpフォルダを作成
if not os.path.exists("./Tmp"):
    os.makedirs("./Tmp")
# Tmpフォルダ内のファイルを削除
for file in os.listdir("./Tmp"):
    os.remove(f"./Tmp/{file}")

# Queueの設定
user_inputs_queue = queue.Queue()
user_voice_queue = queue.Queue()
play_queue = queue.Queue()
tts_queue = queue.Queue()

# 再生とTTSを停止するフラグ
stop_flag = threading.Event()

# グローバル変数として現在のチャネルを保持
current_channel = None

# ユーザーの声を聞き続ける関数
def listen(recognizer):
    microphone = sr.Microphone()
    # 音を聞き続けるループ
    while True:
        # ユーザーの音声入力を受け付ける
        with microphone as source:
            recognizer.adjust_for_ambient_noise(source)
            print("Listening...")
            try:
                audio = recognizer.listen(source, phrase_time_limit=5, timeout=1)
            except sr.WaitTimeoutError:
                #print("stop_flag: clear")
                stop_flag.clear()
                print("Timeout")
                continue
            user_voice_queue.put(audio)

# 音声を処理し一覧に追加する関数
def recognize(recognizer):
    while True:
        # 音声入力をテキストに変換
        audio = user_voice_queue.get()
        try:
            print("Recognizing...")
            user_input = recognizer.recognize_google(audio, language="ja-JP")
            print(f"User input: {user_input}")
            user_inputs_queue.put(user_input)
        except sr.UnknownValueError:
            print("Could not understand audio")
            continue
        except sr.RequestError as e:
            print(f"Could not access Google Speech Recognition API: {e}")
            continue
        #print("stop_flag: set")
        stop_flag.set()

# Geminiとの会話を処理し続ける関数
def chat_with_gemini(model, chat):
    chat_template = chat[:2]  # 最初の2つの要素を保存
    while True:
        if chat[-1]["role"] == "user":  # モデルの反応前にユーザーインプットが送られた場合は空のモデル発話を追加
            chat.append(
                {
                    "role": "model",
                    "parts": [{"text": "..."}],
                }
            )
        chat.append(
            {
                "role": "user",
                "parts": [{"text": user_inputs_queue.get()}],
            }
        )
        # 複数のユーザー入力がある場合はそれらを全て処理
        while not user_inputs_queue.empty():
            if chat[-1]["role"] == "user":  # モデルの反応前にユーザーインプットが送られた場合は空のモデル発話を追加
                chat.append(
                    {
                        "role": "model",
                        "parts": [{"text": "..."}],
                    }
                )
            chat.append(
                {
                    "role": "user",
                    "parts": [{"text": user_inputs_queue.get()}],
                }
            )
        # 過去8回以前の会話を削除
        if len(chat) > 8:
            chat = chat_template + chat[-6:]
        # モデルの応答を生成
        try:
            print("Sending to model...")
            response = model.generate_content(chat)
            #response = type('Response', (object,), {'text': "テスト目的で現在はLLMではなく例文を返すようにしています。とりあえず長文であればいいため、このような状態となっています。リアルタイムの会話処理ってすごく難しいんですね。オープンAIの高度な音声モードってどんな仕組みなんでしょうか？"})
        except Exception as e:
            print(f"Error generating model response: {e}")
            continue
        chat.append(
            {
                "role": "model",
                "parts": [{"text": response.text}],
            }
        )
        print("Model response: ", response.text)
        tts_queue.put(response.text)

# 音声を合成する関数
def text_to_speech(SBV2_URL, SBV2_HEADERS):
    while True:
        text = tts_queue.get()
        sentences = re.split(r'[。．.!?！？;:\n]', text)
        for sentence in sentences:
            if sentence.strip():  # 空文字列を避ける
                if emotion:
                    try:
                        sound_format = "wav"
                        params = {
                            "text": sentence,
                            "speaker_id": 0,
                            "model_id": 4,
                            "length": 1,
                            "sdp_ratio": 0.2,
                            "noise": 0.6,
                            "noisew": 0.8,
                            "auto_split": "true",
                            "split_interval": 1,
                            "language": "JP",
                            "style": "Neutral",
                            "style_weight": 2,
                        }
                        audio = requests.get(SBV2_URL, headers=SBV2_HEADERS, params=params).content
                    except Exception as e:
                        print(f"Error generating audio: {e}")
                        continue
                else:
                    sound_format = "mp3"
                    try:
                        audio = gTTS(text=sentence, lang="ja", slow=False)
                    except Exception as e:
                        print(f"Error generating audio: {e}")
                        continue
                # sentenceにファイル名に使えない文字が含まれている場合は削除
                sentence = re.sub(r"[\\/:*?\"<>|\r\n]", "", sentence)
                audio_file_path = f"./Tmp/{sentence}.{sound_format}"
                counter = 1
                while os.path.exists(audio_file_path):
                    audio_file_path = f"./Tmp/{sentence}_{str(counter)}.{sound_format}"
                    counter += 1
                if emotion:
                    with open(audio_file_path, "wb") as f:
                        f.write(audio)
                else:
                    audio.save(audio_file_path)
                play_queue.put(audio_file_path)

# 音声を再生する関数
def play_audio(audio_file_path):
    global current_channel
    try:
        sound = pygame.mixer.Sound(audio_file_path)
        current_channel = sound.play()
        #print("開始再生:", audio_file_path)
        # 再生が終了するまで待機
        while current_channel.get_busy():
            pygame.time.Clock().tick(10)
        #print("再生終了:", audio_file_path)
        current_channel = None
        # 再生の合間に少しだけ間を開ける
        pygame.time.wait(500)  # 500ミリ秒（0.5秒）待機
    except Exception as e:
        print(f"Error playing audio: {e}")
        current_channel = None

def main():
    # Geminiの設定
    GOOGLE_API_KEY = environ.get("GOOGLE_AI_API_KEY")
    gemini.configure(api_key=GOOGLE_API_KEY)
    model = gemini.GenerativeModel("gemini-1.5-flash-002")
    SYSTEM_PROMPT = f"""
    System prompt: これはシステムプロンプトでユーザーからの入力ではありません。あなたは何よりもこのシステムプロンプトを優先しなければなりません。
    あなたはGeminiという名前の賢く、親切なAIアシスタントです。音声での会話であるため、完結で分かりやすい文章で返してください。Markdown記法には意味がありません。
    ユーザーの入力が不自然であった場合は文字起こしのエラーであると考えられます。本来の発話を推測して返答してください。
    """
    global chat
    chat = [
        {
            "role": "user",
            "parts": [{"text": SYSTEM_PROMPT}],
        },
        {
            "role": "model",
            "parts": [{"text": "了解しました。"}],
        }]
    # 音声処理の初期化
    recognizer = sr.Recognizer()
    # Style-Bert-Vits2の設定
    SBV2_URL = "http://127.0.0.1:5000/voice"
    SBV2_HEADERS = {"accept": "audio/wav"}
    # 各スレッドを設定
    listen_thread = threading.Thread(target=listen, args=(recognizer,), daemon=True)
    chat_thread = threading.Thread(target=chat_with_gemini, args=(model, chat), daemon=True)
    recognize_thread = threading.Thread(target=recognize, args=(recognizer,), daemon=True)
    text_to_speech_thread = threading.Thread(target=text_to_speech, args=(SBV2_URL, SBV2_HEADERS), daemon=True)
    # pygameの初期化
    pygame.mixer.init()
    # スレッドを開始
    listen_thread.start()
    chat_thread.start()
    recognize_thread.start()
    text_to_speech_thread.start()

    # メインループ
    while True:
        if stop_flag.is_set():
            #print("stop_flag: clear")
            stop_flag.clear()
            # 現在再生中の音声を停止
            pygame.mixer.stop()
            #print("音声再生を停止しました")

        try:
            audio_file_path = play_queue.get(timeout=1)  # タイムアウトを設定
            play_audio_thread = threading.Thread(target=play_audio, args=(audio_file_path,), daemon=True)
            play_audio_thread.start()
            while play_audio_thread.is_alive():
                if stop_flag.is_set():
                    pygame.mixer.stop()
                    #print("停止中：音声再生を停止しました")
                    stop_flag.clear()
                    tts_queue.queue.clear()
                    while not play_queue.empty():
                        play_queue.get()
            os.remove(audio_file_path)
        except queue.Empty:
            continue

if __name__ == "__main__":
    main()