chcp 65001 > NUL
@echo off
pushd %~dp0
REM ここにStyle-Bert-Vits2のパスを指定してください
start "" "C:\Applications\StyleBertVits2\Style-Bert-VITS2\Server.bat"
start bot_start.cmd
call .venv\Scripts\python.exe main.py

popd
pause
