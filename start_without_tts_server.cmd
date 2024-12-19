chcp 65001 > NUL
@echo off
pushd %~dp0
start bot_start.cmd
call .venv\Scripts\python.exe main.py

popd
pause