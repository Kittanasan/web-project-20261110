@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title เปิดหน้าเว็บระบบประเมินเม็ดไขมันในตับ

rem ============================================================
rem  ทางลัด: เปิดหน้าเว็บของระบบ (ใช้ start.bat เป็นตัวหลัก)
rem  - หา Python ที่มี torch+ultralytics ให้เองเหมือน start.bat
rem  - ถ้ายังไม่มีเซิร์ฟเวอร์ เปิดให้ก่อนแล้วรอจนพร้อมจริง
rem  - ใช้ได้ทั้งเครื่องนี้และเครื่องที่ย้ายไปใหม่
rem ============================================================

set "PORT=%LIVER_PORT%"
if not defined PORT set "PORT=8000"
set "PY="

if exist "%~dp0runtime\python311\python.exe" call :try_py "%~dp0runtime\python311\python.exe"
if not defined PY if exist "%~dp0runtime\python.exe" call :try_py "%~dp0runtime\python.exe"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" call :try_py "%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0venv\Scripts\python.exe" call :try_py "%~dp0venv\Scripts\python.exe"
if not defined PY call :try_py "%~dp0..\runtime\python311\python.exe"
if not defined PY call :try_py "C:\Users\%USERNAME%\OneDrive\Desktop\นับเหรียญ3\runtime\python311\python.exe"
if not defined PY call :try_py "%USERPROFILE%\Desktop\นับเหรียญ3\runtime\python311\python.exe"
if not defined PY call :try_py_cmd python
if not defined PY call :try_py_cmd py

if not defined PY (
  echo [ERROR] ไม่พบ Python ที่มี torch/ultralytics ในเครื่องนี้
  echo         ระบบจะวิเคราะห์ภาพไม่ได้ - กำลังเปิดคู่มือติดตั้งให้
  start "" notepad "%~dp0README-ติดตั้งเครื่องใหม่.txt"
  pause
  exit /b 1
)

rem มีเซิร์ฟเวอร์ทำงานอยู่แล้วหรือไม่
powershell -NoProfile -Command "try{ $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://127.0.0.1:%PORT%/health'; if($r.StatusCode -eq 200){ exit 0 } } catch { exit 1 }"
if errorlevel 1 (
  echo [INFO] ยังไม่พบเครื่องประมวลผล - กำลังเปิดให้ ...
  start "ระบบประเมินเม็ดไขมันในตับ" /min "%PY%" "%~dp0app.py"
  powershell -NoProfile -Command "for($i=0;$i -lt 150;$i++){try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:%PORT%/health';if($r.StatusCode -eq 200){break}}catch{};Start-Sleep -Milliseconds 700}"
) else (
  echo [INFO] เชื่อมต่อเครื่องประมวลผลได้ที่ http://127.0.0.1:%PORT%
)
start "" http://127.0.0.1:%PORT%/
exit /b 0

:try_py
if not exist "%~1" goto :eof
"%~1" -c "import ultralytics, torch" >nul 2>&1
if errorlevel 1 goto :eof
set "PY=%~1"
goto :eof

:try_py_cmd
where %~1 >nul 2>&1 || goto :eof
%~1 -c "import ultralytics, torch" >nul 2>&1
if errorlevel 1 goto :eof
set "PY=%~1"
goto :eof

