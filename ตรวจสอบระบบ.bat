@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
color 0E
title ตรวจสอบระบบประเมินเม็ดไขมันในตับจากภาพ

rem ============================================================
rem  ใช้เมื่อ "ย้ายโปรแกรมไปเครื่องอื่นแล้ววิเคราะห์ไม่ได้"
rem  - ตรวจว่าเครื่องนี้มี Python + torch + ultralytics หรือไม่
rem  - ตรวจว่าแบบจำลองถูกอ่านได้ และวิเคราะห์ภาพจริงได้
rem  - บอกตรง ๆ ว่าติดข้อไหน แล้วแก้ให้ตามที่ทำได้
rem ============================================================

set "PORT=8000"
set "PY="
set "PYNOTE="

rem ---- หา Python ที่ import torch + ultralytics ได้ ----
if exist "%~dp0runtime\python311\python.exe" call :try_py "%~dp0runtime\python311\python.exe"
if not defined PY if exist "%~dp0runtime\python.exe" call :try_py "%~dp0runtime\python.exe"
if not defined PY if exist "%~dp0.venv\Scripts\python.exe" call :try_py "%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0venv\Scripts\python.exe" call :try_py "%~dp0venv\Scripts\python.exe"
if not defined PY call :try_py "%~dp0..\runtime\python311\python.exe"
if not defined PY call :try_py "C:\Users\%USERNAME%\OneDrive\Desktop\นับเหรียญ3\runtime\python311\python.exe"
if not defined PY call :try_py "%USERPROFILE%\Desktop\นับเหรียญ3\runtime\python311\python.exe"
if not defined PY call :try_py "C:\Users\%USERNAME%\OneDrive\Desktop\จำแนกพูตับ V1\runtime\python311\python.exe"
rem ยังไม่พบตัวที่สมบูรณ์ -> ลอง Python ธรรมดาเพื่อรายงานว่าติดอะไร
if not defined PY call :any_py python
if not defined PY call :any_py py

if not defined PY goto :no_python
if defined PYNOTE echo [หมายเหตุ] %PYNOTE%
echo [Python ที่ใช้ตรวจ] %PY%
echo.

echo กำลังตรวจระบบ (ครั้งแรกอาจใช้เวลา 1-2 นาที ถ้าต้องโหลดแบบจำลอง) ...
echo ------------------------------------------------------------
"%PY%" diagnose.py %PORT%
set "RC=%ERRORLEVEL%"
echo ------------------------------------------------------------
echo.

if not "%RC%"=="0" goto :failed

rem ---- ทุกอย่างผ่าน: เปิดหน้าเว็บให้ใช้งาน ----
powershell -NoProfile -Command "try{ $r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://127.0.0.1:%PORT%/health'; if($r.StatusCode -eq 200){ exit 0 } } catch { exit 1 }"
if errorlevel 1 (
  echo ยังไม่มีเครื่องประมวลผลทำงาน - กำลังเปิดให้ในหน้าต่างใหม่ ...
  start "เครื่องประมวลผล liverV1.pt" /min "%PY%" "%~dp0app.py"
  powershell -NoProfile -Command "for($i=0;$i -lt 150;$i++){try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:%PORT%/health';if($r.StatusCode -eq 200){break}}catch{};Start-Sleep -Milliseconds 700}"
)
start "" http://127.0.0.1:%PORT%/
echo เปิดหน้าเว็บ http://127.0.0.1:%PORT% แล้ว - ใช้งานได้เลย
echo.
echo กดปุ่มใดก็ได้เพื่อปิดหน้าต่างนี้
pause >nul
exit /b 0

rem ============================================================
:failed
echo ระบบยังวิเคราะห์ภาพไม่ได้ - ดูข้อ [FAIL] ด้านบน
echo.
echo วิธีแก้ที่พบบ่อยที่สุด ^(เครื่องใหม่ยังไม่มีตัววิเคราะห์^)
echo   1^) จากเครื่องที่ใช้งานได้ คัดลอกโฟลเดอร์ runtime ^(ทั้งโฟลเดอร์ ราว 5 GB^)
echo      มาวางไว้ข้างไฟล์ app.py ในเครื่องนี้
echo      ให้เป็น  โฟลเดอร์โปรแกรม\runtime\python311\python.exe
echo   2^) ดับเบิลคลิก ตรวจสอบระบบ.bat อีกครั้ง
echo.
echo ถ้าติดข้ออื่น ^(แบบจำลองอ่านไม่ได้ / เขียนไฟล์ไม่ได้ / พอร์ตไม่ว่าง^)
echo ให้อ่านคำแนะนำใต้ข้อนั้นในหน้าต่างนี้ - ระบุสาเหตุไว้แล้ว
echo.
echo รายละเอียดทั้งหมดอยู่ในไฟล์ README-ติดตั้งเครื่องใหม่.txt
start "" notepad "%~dp0README-ติดตั้งเครื่องใหม่.txt"
echo.
echo กดปุ่มใดก็ได้เพื่อปิดหน้าต่างนี้
pause >nul
exit /b 1

rem ============================================================
:no_python
echo ============================================================
echo [ERROR] เครื่องนี้ไม่มี Python เลย จึงยังวิเคราะห์ภาพไม่ได้
echo.
echo   วิธีแก้ที่เร็วที่สุด ^(ไม่ต้องติดตั้งอะไร^)
echo     1^) ไปที่เครื่องที่ใช้งานได้ ^(หรือโฟลเดอร์สำรอง^)
echo     2^) คัดลอกโฟลเดอร์ runtime ทั้งโฟลเดอร์
echo        ^(ข้างในมี python311\python.exe และไลบรารี ประมาณ 5 GB^)
echo     3^) วางไว้ข้างไฟล์ app.py ในเครื่องนี้
echo        ให้เป็น  โฟลเดอร์โปรแกรม\runtime\python311\python.exe
echo     4^) ดับเบิลคลิก ตรวจสอบระบบ.bat อีกครั้ง
echo.
echo   หรือติดตั้ง Python 3.11 ^(64-bit^) จาก python.org แล้วรัน
echo     pip install ultralytics
echo   ^(ต้องต่ออินเทอร์เน็ต และมีที่ว่างราว 5 GB^)
echo ============================================================
echo Python ที่พบในเครื่องนี้:
where python 2>nul
where py 2>nul
echo.
start "" notepad "%~dp0README-ติดตั้งเครื่องใหม่.txt"
echo กดปุ่มใดก็ได้เพื่อปิดหน้าต่างนี้
pause >nul
exit /b 1

rem ============================================================
:try_py
if not exist "%~1" goto :eof
"%~1" -c "import ultralytics, torch" >nul 2>&1
if errorlevel 1 goto :eof
set "PY=%~1"
set "PYNOTE="
goto :eof

:any_py
where %~1 >nul 2>&1 || goto :eof
if defined PY goto :eof
set "PY=%~1"
set "PYNOTE=%PY% ยังไม่มี torch/ultralytics - ระบบจะวิเคราะห์ภาพไม่ได้"
goto :eof
