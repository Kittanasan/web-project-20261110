@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Liver Engine Bridge - เชื่อมเครื่องนี้ขึ้นเว็บออนไลน์

echo ============================================================
echo   ท่อส่งภาพจากเครื่องนี้ ^(liverV1.pt^) ขึ้นเว็บออนไลน์
echo ============================================================
echo.
echo  หน้านี้ต้องเปิดค้างไว้ ระหว่างใช้งานเว็บออนไลน์
echo.

REM ---- 1) เปิดท่อฝั่งเครื่องนี้ (พอร์ต 9000) ----
set LIVER_MODE=engine
set LIVER_ENGINE_PORT=9000
set PYTHONIOENCODING=utf-8

echo [1/2] กำลังเปิดท่อพอร์ต 9000 ...
start "Liver Engine Bridge" cmd /k python cloud_app.py --engine

echo [2/2] รอ 4 วินาที แล้วเปิดท่อออกอินเทอร์เน็ต ...
timeout /t 4 /nobreak >nul

where cloudflared >nul 2>nul
if errorlevel 1 (
  echo.
  echo *** ไม่พบโปรแกรม cloudflared ***
  echo ติดตั้งครั้งเดียวด้วยคำสั่งนี้ ^(เปิด Command Prompt กด Run as administrator^):
  echo     winget install --id Cloudflare.cloudflared
  echo.
  echo หรือดาวน์โหลด Cloudflare Tunnel แล้ววางไฟล์ cloudflared.exe ไว้ข้างไฟล์นี้
  echo.
  pause
  exit /b 1
)

echo.
echo ---- คัดลอก URL ที่ขึ้นต้นด้วย https://xxxx.trycloudflare.com ----
echo ---- ไปใส่ที่ Render: Environment -^> LIVER_ENGINE แล้ว Save ----
echo.
cloudflared tunnel --url http://127.0.0.1:9000

pause
