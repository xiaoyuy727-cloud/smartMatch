@echo off
cd /d .\backend
call .\.venv\Scripts\Activate.bat
uvicorn main:app --reload
pause