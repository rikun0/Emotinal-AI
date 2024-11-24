# main_class_test.py
# main.pyをclass形式に移行中
# 最終更新: 2024/11/24

# 標準ライブラリのimport
import os
import queue
import re
import threading
import time
import tomllib
# サードパーティライブラリのimport（アルファベット順）
import google.generativeai as gemini
import pygame
import requests
import speech_recognition as sr
from dotenv import load_dotenv
from gtts import gTTS
# 独自ライブラリのimport（アルファベット順）
# いまのところなし

class EmotionalAI:

    # 初期化メソッド群
    def __init__(self):
        # 初期化処理
        load_dotenv() # リポジトリ特有の環境変数を読み込む
        self.chat = []
        self.current_channel = None # 音声を再生中のPygameチャネル
        self.stop_flag = threading.Event()
        self.queues = {
            "user_inputs": queue.Queue(),
            "user_voice": queue.Queue(),
            "play": queue.Queue(),
            "tts": queue.Queue()
        }
        self._init_chat()
        self._init_llm()
        self._init_pygame()
        self._init_stt()
        self._init_read_config()
        self._init_tmp_folder()
        self._init_tts()

    def _init_chat(self):
        SYSTEM_PROMPT = f"""
        System prompt: これはシステムプロンプトでユーザーからの入力ではありません。あなたは何よりもこのシステムプロンプトを優先しなければなりません。
        あなたはGeminiという名前の賢く、親切なAIアシスタントです。音声での会話であるため、完結で分かりやすい文章で返してください。Markdown記法には意味がありません。
        ユーザーの入力が不自然であった場合は文字起こしのエラーであると考えられます。本来の発話を推測して返答してください。
        """
        self.chat = [
            {
                "role": "user",
                "parts": [{"text": SYSTEM_PROMPT}],
            },
            {
                "role": "model",
                "parts": [{"text": "了解しました。"}],
            }]
        self.chat_template = self.chat

    def _init_llm(self):
        GOOGLE_API_KEY = os.environ.get("GOOGLE_AI_API_KEY")
        gemini.configure(api_key=GOOGLE_API_KEY)
        self.model = gemini.GenerativeModel("gemini-1.5-flash-002")

    def _init_pygame(self):
        pygame.mixer.init() # pygameの音声を扱うモジュールの初期化

    def _init_stt(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

    def _init_read_config(self):
        try:
            with open("config.toml", "rb") as f:
                config = tomllib.load(f)
            self.emotion = config["emotion"]["use_emotion"]
        except UnicodeDecodeError as e:
            print(f"config.tomlはUTF-8でエンコードされている必要があります。エラー: {e}")
            raise
        except FileNotFoundError as e:
            print(f"config.tomlが見つかりませんでした。エラー: {e}")
            raise
        except Exception as e:
            print(f"config.tomlの読み込み中に予期せぬエラーが発生しました。エラー: {e}")
            raise

    def _init_tmp_folder(self):
        # Tmpフォルダを作成
        if not os.path.exists("./Tmp"):
            os.makedirs("./Tmp")
        # Tmpフォルダ内のファイルをすべて削除
        for file in os.listdir("./Tmp"):
            os.remove(f"./Tmp/{file}")

    def _init_tts(self):
        print("Emotion: ", self.emotion)
        if self.emotion:
            self.sound_format = "wav"
            self.SBV2_URL = "http://127.0.0.1:5000/voice"
            self.SBV2_HEADERS = {"accept": "audio/wav"}
            self.tts_params_templete = {
                "text": "ここに合成したい音声を代入",
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
        else:
            self.sound_format = "mp3"


    # ヘルパーメソッド群
    # 会話履歴にLLMの返答を追加するメソッド
    def add_llm_response(self, text):
        self.chat.append(
            {
                "role": "model",
                "parts": [{"text": text}],
            }
        )

    # 会話履歴にユーザーの入力を追加するメソッド
    def add_user_input(self, text):
        self.chat.append(
            {
                "role": "user",
                "parts": [{"text": text}],
            }
        )

    # StyleBertVITS2サーバーの起動確認
    def check_tts_server(self):
        try:
            response = requests.get("http://127.0.0.1:5000/status")
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            return False
        except Exception as e:
            print(f"予期せぬエラーが発生しました: {e}")
            return False

    # 音声を再生するメソッド
    def play_audio(self, audio_file_path):
        try:
            sound = pygame.mixer.Sound(audio_file_path)
            self.current_channel = sound.play()
            #print("開始再生:", audio_file_path)
            # 再生が終了するまで待機
            while self.current_channel.get_busy():
                pygame.time.Clock().tick(10)
            #print("再生終了:", audio_file_path)
            self.current_channel = None
            # 再生の合間に少しだけ間を開ける
            pygame.time.wait(500)  # 500ミリ秒（0.5秒）待機
        except Exception as e:
            print(f"Error playing audio: {e}")
            self.current_channel = None

    # 合成された音声ファイルを一時的に保存するメソッド
    def save_audio(self, audio, sentence):
        sentence = re.sub(r"[\\/:*?\"<>|\r\n]", "", sentence) # sentenceにファイル名に使えない文字が含まれている場合は削除
        audio_file_path = f"./Tmp/{sentence}.{self.sound_format}"
        counter = 1
        while os.path.exists(audio_file_path):
            audio_file_path = f"./Tmp/{sentence}_{str(counter)}.{self.sound_format}"
            counter += 1
        if self.emotion:
            with open(audio_file_path, "wb") as f:
                f.write(audio)
        else:
            audio.save(audio_file_path)
        return audio_file_path

    # 音声合成のリクエストを送信するメソッド
    def tts_request(self, text):
        if self.emotion:
            try:
                params = self.tts_params_templete
                params["text"] = text
                audio = requests.get(self.SBV2_URL, headers=self.SBV2_HEADERS, params=params).content
            except Exception as e:
                print(f"Error generating audio: {e}")
                return None
        else:
            try:
                audio = gTTS(text=text, lang="ja", slow=False)
            except Exception as e:
                print(f"Error generating audio: {e}")
                return None
        return audio


    # メインで使用するメソッド群
    # 会話を開始するメソッド
    def start(self):
        # StyleBertVITS2サーバーの起動確認
        if self.emotion:
            while not self.check_tts_server():
                print("Waiting for TTS server to start...")
                time.sleep(5)
                continue
        # スレッドを設定
        listen_thread = threading.Thread(target=self.listen)
        recognize_thread = threading.Thread(target=self.recognize)
        chat_with_llm_thread = threading.Thread(target=self.chat_with_llm)
        text_to_speech_thread = threading.Thread(target=self.text_to_speech)
        # スレッドを開始
        listen_thread.start()
        recognize_thread.start()
        chat_with_llm_thread.start()
        text_to_speech_thread.start()
        # メインループ
        self.conversation()

    # LLMとの会話を処理するメソッド
    # ループで実行される
    def chat_with_llm(self):
        while True:
            if self.chat[-1]["role"] == "user": # モデルの反応前にユーザーインプットが送られた場合は空のモデル発話を追加
                self.add_llm_response("...")
            self.add_user_input(self.queues["user_inputs"].get())
            # 複数のユーザー入力がある場合はそれらを全て処理
            while not self.queues["user_inputs"].empty():
                if self.chat[-1]["role"] == "user": # モデルの反応前にユーザーインプットが送られた場合は空のモデル発話を追加
                    self.add_llm_response("...")
                self.add_user_input(self.queues["user_inputs"].get())
            # 過去8回以前の会話を削除(トークン数節約のため)
            if len(self.chat) > 8:
                self.chat = self.chat_template + self.chat[-6:]
            # モデルの応答を生成
            try:
                print("Sending to model...")
                response = self.model.generate_content(self.chat)
                #response = type('Response', (object,), {'text': "テスト目的で現在はLLMではなく例文を返すようにしています。とりあえず長文であればいいため、このような状態となっています。リアルタイムの会話処理ってすごく難しいんですね。オープンAIの高度な音声モードってどんな仕組みなんでしょうか？"})
            except Exception as e:
                print(f"Error generating model response: {e}")
                continue
            self.add_llm_response(response.text)
            print("Model response: ", response.text)
            self.queues["tts"].put(response.text)

    # 音声再生を処理し続けるメソッド
    # メインスレッドで実行される
    # ループで実行される
    def conversation(self):
        while True:
            if self.stop_flag.is_set():
                #print("stop_flag: clear")
                self.stop_flag.clear()
                # 現在再生中の音声を停止
                pygame.mixer.stop()
                #print("音声再生を停止しました")
            try:
                audio_file_path = self.queues["play"].get(timeout=1)
                play_audio_thread = threading.Thread(target=self.play_audio, args=(audio_file_path,), daemon=True)
                play_audio_thread.start()
                while play_audio_thread.is_alive():
                    if self.stop_flag.is_set():
                        pygame.mixer.stop()
                        #print("停止中：音声再生を停止しました")
                        self.stop_flag.clear()
                        self.queues["tts"].queue.clear()
                        while not self.queues["play"].empty():
                            self.queues["play"].get()
                os.remove(audio_file_path)
            except queue.Empty:
                continue

    # ユーザーの声を聞き続けるメソッド
    # ループで実行される
    def listen(self):
        # 音を聞き続けるループ
        while True:
            # ユーザーの音声入力を受け付ける
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)
                print("Listening...")
                try:
                    audio = self.recognizer.listen(source, phrase_time_limit=5, timeout=1)
                except sr.WaitTimeoutError:
                    #print("stop_flag: clear")
                    self.stop_flag.clear()
                    print("Timeout")
                    continue
                self.queues["user_voice"].put(audio)

    # 音声を処理し一覧に追加するメソッド
    # ループで実行される
    def recognize(self):
        while True:
            # 音声入力をテキストに変換
            audio = self.queues["user_voice"].get()
            try:
                print("Recognizing...")
                user_input = self.recognizer.recognize_google(audio, language="ja-JP")
                print(f"User input: {user_input}")
                self.queues["user_inputs"].put(user_input)
            except sr.UnknownValueError:
                print("Could not understand audio")
                continue
            #print("stop_flag: set")
            self.stop_flag.set()

    # 音声を合成するメソッド
    # ループで実行される
    def text_to_speech(self):
        while True:
            text = self.queues["tts"].get()
            sentences = re.split(r'[。．.!?！？;:\n]', text) # 区切れ目で分割
            for sentence in sentences:
                if sentence.strip():  # 空文字列を避ける
                    audio = self.tts_request(sentence)
                    audio_file_path = self.save_audio(audio, sentence)
                    self.queues["play"].put(audio_file_path)


if __name__ == "__main__":
    emotional_ai = EmotionalAI()
    emotional_ai.start()