@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
color 0B
title ระบบประเมินเม็ดไขมันในตับจากภาพ - liverV1.pt

rem ============================================================
rem  เปิดระบบประเมินเม็ดไขมันในตับจากภาพ (แบบจำลอง liverV1.pt)
rem  - หา Python ที่มี torch + ultralytics ให้เอง (โฟลเดอร์ runtime ก่อนเสมอ)
rem  - ถ้าไม่พบ จะพยายามคัดลอกโฟลเดอร์ runtime ให้เอง (ถ้ามีต้นทางในเครื่อง)
rem  - พอร์ต 8000 ถ้าถูกใช้โดยโปรแกรมอื่น จะเลือกพอร์ตถัดไปให้ (8001, 8002 ...)
rem  - เปิดเบราว์เซอร์หลังเครื่องประมวลผลตอบสนองจริงเท่านั้น
rem  - ทำงานได้ทุกเครื่องที่คัดลอกโฟลเดอร์ไป ไม่ขึ้นกับชื่อผู้ใช้/ชื่อเครื่อง
rem ============================================================

set "PY="
set "PORT="
set "RUNTIME_EXE=%~dp0runtime\python311\python.exe"

rem ---- 1) หา Python ที่ใช้งานกับ ultralytics ได้ ----
if exist "%RUNTIME_EXE%" (
  "%RUNTIME_EXE%" -c "import ultralytics, torch" >nul 2>&1
  if not errorlevel 1 set "PY=%RUNTIME_EXE%"
)
if not defined PY call :try_py "%~dp0runtime\python.exe"
if not defined PY call :try_py "%~dp0.venv\Scripts\python.exe"
if not defined PY call :try_py "%~dp0venv\Scripts\python.exe"
if not defined PY call :try_py "%~dp0..\runtime\python311\python.exe"
if not defined PY call :try_py "%USERPROFILE%\OneDrive\Desktop\นับเหรียญ3\runtime\python311\python.exe"
if not defined PY call :try_py "%USERPROFILE%\Desktop\นับเหรียญ3\runtime\python311\python.exe"
if not defined PY call :try_py "C:\ProgramData\liverV1\runtime\python311\python.exe"
if not defined PY call :try_py "D:\liverV1\runtime\python311\python.exe"
if not defined PY call :try_py_drive

rem ยังไม่พบตัวที่สมบูรณ์ -> พยายามคัดลอกโฟลเดอร์ runtime ให้เอง
if not defined PY (
  echo [2/5] ยังไม่พบตัววิเคราะห์ในเครื่องนี้ - กำลังค้นหาโฟลเดอร์ runtime ให้คัดลอก...
  call :find_runtime
)
if not defined PY call :try_py_cmd python
if not defined PY call :try_py_cmd py

if not defined PY goto :no_python
"%PY%" -c "import torch, ultralytics" >nul 2>&1
if errorlevel 1 goto :no_python
echo [1/5] Python ที่ใช้ประมวลผล: %PY%
"%PY%" -c "import sys,torch,ultralytics;print('[1.1] torch',torch.__version__,'/ ultralytics',ultralytics.__version__)"
if errorlevel 1 (
  echo.
  echo [ERROR] Python ตัวนี้ยังใช้วิเคราะห์ภาพไม่ได้ - กำลังเปิดคู่มือติดตั้งให้
  start "" notepad "%~dp0README-ติดตั้งเครื่องใหม่.txt"
  goto :fail
)

if not exist "liverV1.pt" (
  echo.
  echo [ERROR] ไม่พบไฟล์แบบจำลอง liverV1.pt ในโฟลเดอร์นี้
  echo         %CD%
  echo         ต้องคัดลอกไฟล์ liverV1.pt มาวางไว้ข้างไฟล์ start.bat
  echo         ถ้าคัดลอกผ่าน USB/อีเมล ไฟล์อาจถูกตัดขนาด - เทียบขนาดกับเครื่องต้นทาง ^(ประมาณ 6 MB^)
  goto :fail
)
if not exist "Index.html" (
  if not exist "index.html" (
    if not exist "templates\index.html" (
      echo.
      echo [ERROR] ไม่พบไฟล์หน้าเว็บ Index.html ในโฟลเดอร์นี้
      echo         ต้องคัดลอก Index.html มาวางไว้ข้างไฟล์ start.bat
      goto :fail
    )
  )
)
echo [2/5] พบแบบจำลอง liverV1.pt และหน้าเว็บแล้ว

rem ---- 2) ตรวจสิทธิ์เขียนโฟลเดอร์ (เครื่องใหม่มักวางใน Program Files แล้วบันทึกผลไม่ได้) ----
if not exist "exports" mkdir "exports" >nul 2>&1
echo probe> "exports\.probe" 2>nul
if errorlevel 1 (
  echo.
  echo [ERROR] โฟลเดอร์นี้เขียนไฟล์ไม่ได้ ^(บันทึกผลการตรวจไม่ได้^)
  echo         %CD%
  echo         ให้ย้ายทั้งโฟลเดอร์โปรแกรมไปไว้ใน Documents หรือ Desktop แล้วเปิด start.bat ใหม่
  goto :fail
)
del "exports\.probe" >nul 2>&1
echo [3/5] เขียนโฟลเดอร์ exports\ ได้ ^(ที่บันทึกผลการตรวจ^)

rem ---- 3) เลือกพอร์ต: ใช้ 8000 ถ้าว่าง ถ้าไม่ว่างเลือกพอร์ตถัดไป ----
set "PORT=8000"
call :find_free_port
if not defined PORT (
  echo.
  echo [ERROR] พอร์ต 8000-8020 ถูกใช้ทั้งหมด - ปิดโปรแกรมที่ใช้พอร์ตเหล่านี้แล้วลองใหม่
  goto :fail
)
echo [4/5] ใช้พอร์ต %PORT%

rem ---- 4) เริ่มเซิร์ฟเวอร์ ----
echo [5/5] กำลังเปิดเครื่องประมวลผล ... ^(หน้าต่างนี้ต้องเปิดทิ้งไว้ตลอดการใช้งาน^)
echo ============================================================
echo   ระบบประเมินเม็ดไขมันในตับจากภาพถ่าย ^(liverV1.pt^)
echo   ศูนย์วิจัยและพัฒนาการเพาะเลี้ยงสัตว์น้ำชายฝั่งฉะเชิงเทรา
echo ============================================================
echo   หน้าเว็บใช้งานจริง : http://127.0.0.1:%PORT%
echo   แบบจำลอง           : liverV1.pt ^(ประมวลผลในเครื่องนี้เท่านั้น^)
echo   โฟลเดอร์บันทึกผล   : %CD%\exports
echo ============================================================
echo   ครั้งแรกใช้เวลา 10-40 วินาที ^(กำลังโหลดแบบจำลอง^)
echo   ถ้าหน้าเว็บขึ้นว่าเชื่อมต่อไม่ได้ ให้รอแล้วกด F5 อีกครั้ง
echo ============================================================
echo.

if /i "%~1"=="--no-browser" goto :run_server

rem ตัวเฝ้า: เปิดเบราว์เซอร์เมื่อ /health ตอบ 200 (ทำงานแยก ไม่บล็อกหน้าต่างนี้)
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 180;$i++){try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:%PORT%/health';if($r.StatusCode -eq 200){Start-Process 'http://127.0.0.1:%PORT/';break}}catch{};Start-Sleep -Milliseconds 700}"

:run_server
set "LIVER_PORT=%PORT%"
"%PY%" app.py
set "RC=%ERRORLEVEL%"
echo.
echo ============================================================
if not "%RC%"=="0" (
  echo เซิร์ฟเวอร์หยุดทำงานผิดปกติ ^(exit code %RC%^)
  echo ข้อความ error อยู่ด้านบน ^(บรรทัดที่ขึ้นต้นด้วย [error]^)
  echo ถ้ายังหาสาเหตุไม่ได้ ให้ดับเบิลคลิก ตรวจสอบระบบ.bat
) else (
  echo เซิร์ฟเวอร์หยุดทำงานแล้ว
)
echo กดปุ่มใดก็ได้เพื่อปิดหน้าต่างนี้
pause >nul
exit /b %RC%

rem ============================================================
rem  กรณีไม่พบ Python/ตัววิเคราะห์
rem ============================================================
:no_python
echo.
echo [ERROR] เครื่องนี้ยังไม่มีตัววิเคราะห์ ^(Python + torch + ultralytics^)
echo         จึงยังวิเคราะห์ภาพด้วยแบบจำลอง liverV1.pt ไม่ได้
echo.
echo         วิธีแก้ ^(เร็วที่สุด ไม่ต้องต่ออินเทอร์เน็ต^)
echo           1^) ไปที่เครื่องที่ใช้งานได้ แล้วคัดลอกโฟลเดอร์ runtime
echo              ^(ข้างในมี python311\python.exe และไลบรารี ประมาณ 5 GB^)
echo           2^) วางไว้ข้างไฟล์ start.bat ในเครื่องนี้
echo              ให้เป็น   %CD%\runtime\python311\python.exe
echo           3^) ดับเบิลคลิก start.bat อีกครั้ง
echo.
echo         วิธีที่ต้องต่ออินเทอร์เน็ต
echo           ติดตั้ง Python 3.11 ^(64-bit^) จาก python.org ^(ติ๊ก Add to PATH^) แล้วพิมพ์
echo              pip install ultralytics
where python 2>nul
where py 2>nul
echo.
echo         รายละเอียดทั้งหมด: README-ติดตั้งเครื่องใหม่.txt
start "" notepad "%~dp0README-ติดตั้งเครื่องใหม่.txt"
goto :fail

:fail
echo ============================================================
pause
exit /b 1

rem ============================================================
rem  ฟังก์ชันช่วย
rem ============================================================
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

rem ค้นหาโฟลเดอร์ runtime ที่มี torch+ultralytics อยู่แล้วในเครื่องนี้ (ไดรฟ์ C: ถึง F:, ลึก 4 ชั้น)
:try_py_drive
for %%D in (C D E F) do (
  if exist "%%D:\" (
    for /f "delims=" %%F in ('dir /b /s "%%D:\python311\python.exe" 2^>nul') do call :try_py "%%F"
    if defined PY goto :eof
  )
)
for %%D in (C D E F) do (
  if exist "%%D:\" (
    for /f "delims=" %%F in ('dir /b /s "%%D:\runtime\python.exe" 2^>nul') do call :try_py "%%F"
    if defined PY goto :eof
  )
)
goto :eof

rem คัดลอกโฟลเดอร์ runtime ให้เอง ถ้าพบต้นทางในเครื่อง (เช่น โฟลเดอร์เดิมของระบบนี้)
:find_runtime
set "SRC="
for %%C in (
  "%USERPROFILE%\OneDrive\Desktop\นับเหรียญ3\runtime"
  "%USERPROFILE%\Desktop\นับเหรียญ3\runtime"
  "%USERPROFILE%\OneDrive\Desktop\จำแนกพูตับ V1\runtime"
) do (
  if not defined SRC if exist "%%~C\python311\python.exe" set "SRC=%%~C"
)
if not defined SRC echo [2/5] ไม่พบโฟลเดอร์ runtime ให้คัดลอก - ต้องคัดลอกเอง ^(ดู README-ติดตั้งเครื่องใหม่.txt^)
if not defined SRC goto :eof
echo [2/5] พบโฟลเดอร์ runtime: %SRC%
echo       กำลังคัดลอกมาไว้ในโฟลเดอร์นี้ ^(ราว 5 GB ใช้เวลาหลายนาที^) ...
if not exist "runtime" mkdir "runtime" >nul 2>&1
robocopy "%SRC%" "%CD%\runtime" /E /NFL /NDL /NJH /NJS /R:1 /W:1 >nul
if exist "%RUNTIME_EXE%" (
  "%RUNTIME_EXE%" -c "import ultralytics, torch" >nul 2>&1
  if not errorlevel 1 (
    set "PY=%RUNTIME_EXE%"
    echo [2/5] คัดลอกเสร็จแล้ว: %RUNTIME_EXE%
    goto :eof
  )
)
echo [2/5] คัดลอกแล้วแต่ยังใช้งานไม่ได้ - ต้องคัดลอกใหม่ทั้งโฟลเดอร์ ^(ดู README-ติดตั้งเครื่องใหม่.txt^)
goto :eof

rem หาพอร์ตว่างในช่วง 8000-8020
:find_free_port
set "PORT="
for /l %%P in (8000,1,8020) do (
  if not defined PORT (
    netstat -ano | findstr /R /C:":%%P .*LISTENING" >nul 2>&1
    if errorlevel 1 set "PORT=%%P"
  )
)
goto :eof
