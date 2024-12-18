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
import asyncio
import websockets
# サードパーティライブラリのimport
import google.generativeai as gemini
from gtts import gTTS
from dotenv import load_dotenv
import pygame
import requests
import speech_recognition as sr
# 独自ライブラリのimport
# いまのところなし

class EmotionalAI:

    # 初期化メソッド群
    def __init__(self):
        # 初期化処理
        load_dotenv() # リポジトリ特有の環境変数を読み込む
        self.chat = []
        self.current_channel = None # 音声を再生中のPygameチャネル
        self.is_speaking = False
        self.stop_flag = threading.Event()
        self.queues = {
            "user_inputs": queue.Queue(),
            "play": queue.Queue(),
            "tts": queue.Queue(),
            "user_voice": queue.Queue(),
        }
        self.websocket_server = None
        self._init_chat()
        self._init_llm()
        self._init_stt()
        self._init_read_config()
        self._init_tmp_folder()
        self._init_tts()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

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
        self.model = gemini.GenerativeModel("gemini-1.5-flash")

    def _init_stt(self):
        self.recognizer = sr.Recognizer()
        #self.microphone = sr.Microphone()

    def _init_read_config(self):
        try:
            with open("config.toml", "rb") as f:
                config = tomllib.load(f)
            self.emotion = config["emotion"]["use_emotion"]
            self.voice_detection_config = config["voice_detection"]
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
        # recordedフォルダを作成
        if not os.path.exists("./recorded"):
            os.makedirs("./recorded")
        # recordedフォルダ内のファイルをすべて削除
        for file in os.listdir("./recorded"):
            os.remove(f"./recorded/{file}")

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

    # WebSocketサーバーを開始するメソッド
    async def start_websocket_server(self):
        self.websocket_server = await websockets.serve(
            lambda ws: self.websocket_handler(ws),
            "localhost",
            8765
        )
        await self.websocket_server.wait_closed()

    def start_server_thread(self):
        server_thread = threading.Thread(target=self.loop.run_until_complete, args=(self.start_websocket_server(),))
        server_thread.start()


    # メインで使用するメソッド群
    # 会話を開始するメソッド
    def start(self):
        # WebSocketサーバーを開始
        print("WebSocketサーバーを起動中...")
        self.start_server_thread()
        # StyleBertVITS2サーバーの起動確認
        if self.emotion:
            while not self.check_tts_server():
                print("TTSサーバーの起動を待機中...")
                time.sleep(5)
                continue
        # スレッドを設定
        recognize_thread = threading.Thread(target=self.recognize)
        chat_with_llm_thread = threading.Thread(target=self.chat_with_llm)
        text_to_speech_thread = threading.Thread(target=self.text_to_speech)
        # スレッドを開始
        print("各スレッドを起動中...")
        recognize_thread.start()
        chat_with_llm_thread.start()
        text_to_speech_thread.start()
        # メインループ
        print("メインループを起動中...")
        asyncio.run_coroutine_threadsafe(self.send_message("ready"), self.loop)
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
        print("正常に起動しました")
        while True:
            audio_file_path = self.queues["play"].get()
            try:
                asyncio.run_coroutine_threadsafe(self.send_message(audio_file_path), self.loop)
            except Exception as e:
                print(f"Error sending audio file path: {e}")

    # 音声を処理し一覧に追加するメソッド
    # ループで実行される
    def recognize(self):
        while True:
            # 音声入力をテキストに変換
            audio_file_path = self.queues["user_voice"].get()
            # ファイルパスから音声を読み込む
            with sr.AudioFile(audio_file_path) as source:
                audio = self.recognizer.record(source)
            os.remove(audio_file_path)
            try:
                print("Recognizing...")
                user_input = self.recognizer.recognize_google(audio, language="ja-JP")
                print(f"User input: {user_input}")
                self.queues["user_inputs"].put(user_input)
            except sr.UnknownValueError:
                asyncio.run_coroutine_threadsafe(self.send_message("restart"), self.loop)
                print("Could not understand audio")
                continue
            #print("stop_flag: set")
            asyncio.run_coroutine_threadsafe(self.send_message("delete"), self.loop)
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

    # WebSocketハンドラー
    async def websocket_handler(self, websocket):
        try:
            self.websocket = websocket
            async for message in websocket:
                if message == "speech_start":
                    print("Discord: Speech started")
                    self.stop_flag.set()  # 現在の音声を停止
                elif message == "speech_end":
                    print("Discord: Speech ended")
                elif message.endswith(".wav"):
                    try:
                        # 音声データを受信
                        audio_file_path = message
                        if audio_file_path is not None:
                            self.queues["user_voice"].put(audio_file_path)
                        else:
                            print("受け取った音声データのパスがNoneです")
                    except Exception as e:
                        print(f"音声ファイルパスの受け取りに失敗しました: {e}")
                else:
                    print(f"受信したメッセージ: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.websocket = None

    # websocketでメッセージを送信するメソッド
    async def send_message(self, message):
        if hasattr(self, "websocket") and self.websocket:
            try:
                await self.websocket.send(str(message))
                print(f"{message} と送信しました")
            except Exception as e:
                print(f"メッセージの送信に失敗しました: {e}")


if __name__ == "__main__":
    emotional_ai = EmotionalAI()
    emotional_ai.start()