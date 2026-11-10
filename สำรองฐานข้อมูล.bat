@echo off
chcp 65001 >nul
cd /d "%~dp0"
title สำรองฐานข้อมูล - ระบบประเมินเม็ดไขมันในตับ
echo ============================================================
echo  สำรองฐานข้อมูลกลาง (data\db.sqlite) เป็นไฟล์ JSON
echo ============================================================
echo.

set "PY="
if exist "runtime\python311\python.exe" set "PY=runtime\python311\python.exe"
if not defined PY if exist "..\นับเหรียญ3\runtime\python311\python.exe" set "PY=..\นับเหรียญ3\runtime\python311\python.exe"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo [error] ไม่พบ Python ในเครื่องนี้ - คัดลอกโฟลเดอร์ runtime มาวางข้างไฟล์นี้
  pause
  exit /b 1
)

echo [1/2] ตรวจฐานข้อมูล...
"%PY%" backup_db.py check
echo.
echo [2/2] สำรองข้อมูล...
"%PY%" backup_db.py backup
echo.
echo ไฟล์สำรองอยู่ในโฟลเดอร์ data\ (ชื่อ backup-วันเวลา.json)
echo กู้คืน: ดับเบิลคลิก คืนค่าฐานข้อมูล.bat
echo.
pause
