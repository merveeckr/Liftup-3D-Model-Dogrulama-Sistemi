@echo off
chcp 65001 > nul
title LIFT UP — 3D Model Dogrulama Sistemi

echo.
echo  ============================================
echo   LIFT UP — 3D Model Dogrulama Sistemi
echo   Ankara Yildirim Beyazit Universitesi
echo  ============================================
echo.

cd /d "%~dp0backend"

echo  [*] Sunucu baslatiliyor...
echo  [*] Tarayici: http://localhost:8000
echo.
echo  Durdurmak icin bu pencereyi kapatin.
echo.

"C:\Users\merve\AppData\Local\Programs\Python\Python311\python.exe" main.py
pause
