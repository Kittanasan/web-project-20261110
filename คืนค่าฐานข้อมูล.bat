@echo off
chcp 65001 >nul
cd /d "%~dp0"
title คืนค่าฐานข้อมูล - ระบบประเมินเม็ดไขมันในตับ
echo ============================================================
echo  คืนค่าฐานข้อมูลจากไฟล์สำรองในโฟลเดอร์ data\
echo  (ใช้ไฟล์ล่าสุดอัตโนมัติ - ถ้าต้องการไฟล์อื่นให้ลากไฟล์มาวางบน .bat นี้)
echo ============================================================
echo.

set "PY="
if exist "runtime\python311\python.exe" set "PY=runtime\python311\python.exe"
if not defined PY if exist "..\นับเหรียญ3\runtime\python311\python.exe" set "PY=..\นับเหรียญ3\runtime\python311\python.exe"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [error] ไม่พบ Python ในเครื่องนี้
  pause
  exit /b 1
)

set "FILE=%~1"
if defined FILE (
  "%PY%" backup_db.py restore "%FILE%"
) else (
  "%PY%" backup_db.py restore
)
echo.
pause
