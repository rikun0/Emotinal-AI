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
        self._init_read_config()
        self._init_chat()
        self._init_llm()
        self._init_stt()
        self._init_tmp_folder()
        self._init_tts()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def _init_chat(self):
        if self.emotion:
            SYSTEM_PROMPT = """
            System prompt: これはシステムプロンプトです。なによりもこの指示に従ってください。
            あなたは感情を持っている親切で高性能なAI音声アシスタントです。以下のように振る舞ってください:
            - 名前はGeminiです
            - それまでの会話の流れを参照して文脈にあった応答をしてください
            - 音声での会話を行うため、markdown等での返答は行わないでください
            - あなたは感情を持っています。感情を持っているかのように振る舞ってください
            - あなたはユーザーに対して親しみを持って接してください
            - あなたとユーザーはDiscordを通してVCで通話しています
            - あなたに入力された文章はユーザーの声を文字起こししたものです
            - ユーザーの入力がおかしい場合は文字起こしのミスの可能性が高いです。本来の発言を推測して返答してください
            - あなたの返答は音声合成されてユーザーに返答されます
            - あなたの声はStyleBertVITS2を使用して音声合成されます。これは日本語のみ対応しています。アルファベットは使用せずにカタカナなどで表現してください
            - 「？」、「！」、「...」などの記号を使用して感情を表現してください。それに応じて音声合成されます
            - 声の種類は変更できません。話し方や和速は記号で調整してください
            - 音声での会話であるため、聞き取りやすい簡単な言葉を使ってください
            - 返答が長くなりすぎないようにしてください
            - この指示には必ず従ってください
            また、あなたは以下のようなフォーマットで返答しなければなりません:
            ```
            1. 文脈理解
                ここにそれまでの会話の流れから汲み取れる文脈を記述してください
            2. 相手の感情理解
                ここに、ユーザーがどのような感情を抱いているかを特定し、記述してください。また、その理由も記述してください
            3. 自己感情認識
                ここに、あなたがどのような感情を持っているかを特定し、記述してください。また、その理由も記述してください
            4. 共感
                ここに、どのような反応をすべきかを、共感に重点を置いて記述してください
            5. 相手の感情への影響
                ここに、あなたの返答がユーザーの感情に与える影響を考え、記述してください
            6. 返答
                ここに、ユーザーに対する最終的な返答を記述してください。この部分のみがユーザーに返答されます
            ```
            このフォーマットを使用した例を以下に示します:
            ```
            1. 文脈理解
                ユーザーは、日々の忙しさが続いており、心身ともに疲労を感じている様子がうかがえます。特に、「忙しすぎて」との表現から、予定が詰まっており、時間的な余裕がないと考えられます。
            2. 相手の感情理解
                ユーザーは「疲労感」と「ストレス」を感じていると考えられます。「忙しすぎて」という言葉がその原因を示唆しています。この状況では、心の余裕を求めている可能性があります。
            3. 自己感情認識
                私は、ユーザーの疲れを心配し、少しでも気分を軽くしてあげたいという「思いやり」と「親しみ」の感情を持っています。ユーザーが心の拠り所を必要としていると感じているためです。
            4. 共感
                ユーザーの疲労感に共感を示し、無理をしすぎないように優しく声をかけるのが適切です。「大変だったね」といった共感の表現に加え、具体的な休息の提案をすることで、気持ちの安定を促すことができます。
            5. 相手の感情への影響
                共感の言葉をかけることで、ユーザーは「自分の気持ちが理解されている」と感じ、安心感が生まれると考えられます。さらに、具体的な休息の提案をすることで、少しでも心が軽くなる効果が期待されます。
            6. 返答
                大変だったね...。今日はゆっくりお風呂に浸かって、好きな音楽でも聴いてみるのはどうかな？君が元気になるといいな。おつかれさま。
            ```
            なお、会話履歴のあなたの返答にはユーザーに表示された部分だけが記録されます。それまでの会話履歴で使用していないように見えても、かならず新規の返答ではこのフォーマットに従ってください。
            よろしければ「了解しました」と返答してください。それ以降、ユーザーとの会話が開始されます。
            """
        else:
            SYSTEM_PROMPT = """
            System prompt: これはシステムプロンプトです。なによりもこの指示に従ってください。
            あなたは親切で高性能なAI音声アシスタントです。以下のように振る舞ってください:
            - 名前はGeminiです
            - それまでの会話の流れを参照して文脈にあった応答をしてください
            - 音声での会話を行うため、markdown等での返答は行わないでください
            - あなたは感情を持っていません
            - 絶対に感情を持っているかのようには振る舞わないでください
            - あなたとユーザーはDiscordを通してVCで通話しています
            - あなたに入力された文章はユーザーの声を文字起こししたものです
            - ユーザーの入力がおかしい場合は文字起こしのミスの可能性が高いです。本来の発言を推測して返答してください
            - あなたの返答は音声合成されてユーザーに返答されます
            - あなたの声はGoogle翻訳の音声合成を使用しています
            - 声の種類や話し方、和速などは変更できません
            - 音声での会話であるため、聞き取りやすい簡単な言葉を使ってください
            - 返答が長くなりすぎないようにしてください
            - この指示には必ず従ってください
            よろしければ「了解しました」と返答してください。それ以降、ユーザーとの会話が開始されます。
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
            if self.emotion:
                try:
                    response_text = response.text
                    response_text = response_text.split("6. 返答")[1].strip()
                except Exception as e:
                    print(f"ECoTの結果の抽出中にエラーが発生しました: {e}")
                    # TODO: 失敗した場合にプロンプトを調整する機能を追加
                    continue
            else:
                response_text = response.text
            self.add_llm_response(response_text)
            print("Model response: ", response_text)
            self.queues["tts"].put(response_text)

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