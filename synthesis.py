import requests
import json
import tempfile
import winsound
import os

engine_api = "http://127.0.0.1:50032"

# 音声を合成する関数
def tts(text, speaker, engine):
    if engine == "voicevox":
        return voicevox(text, speaker)
    if engine == "coeiroink":
        speaker = "3c37646f-3881-5374-2a83-149267990abc"
        styleId = 0
        response = coeiroink(styleId, speaker, text)
        return response

def voicevox(text, speaker):
    # 音声合成用のクエリ作成
    query = requests.post(
        f'http://127.0.0.1:50021/audio_query',
        params=(('text', text),('speaker', speaker),)
    )
    # 音声合成
    synthesis = requests.post(
        f'http://127.0.0.1:50021/synthesis',
        headers = {"Content-Type": "application/json"},
        params=(('text', text),('speaker', speaker),),
        data = json.dumps(query.json())
    )
    # 一時ファイルを作成し、音声データを保存
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
        temp_file.write(synthesis.content)
        temp_file_path = temp_file.name
    return temp_file_path

def coeiroink(styleId, speaker, text):
    # 音声合成
    response = requests.post(
        engine_api + '/v1/predict',
        json={
            'text': text,
            'speakerUuid': speaker,
            'styleId': styleId,
            'prosodyDetail': None,
            'speedScale': 1
        })

    # 一時ファイルを作成し、音声データを保存
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
        temp_file.write(response.content)
        temp_file_path = temp_file.name
    return temp_file_path
