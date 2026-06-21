@echo off
REM Claude Code 扩展汉化 · Windows GUI 启动器
REM 双击本文件即可调起 GUI 窗口(隐藏黑窗口,只弹 PowerShell 窗口),窗口内运行一键汉化.py
chcp 65001 >nul
powershell -ExecutionPolicy Bypass -File "%~dp0汉化启动器.ps1"
