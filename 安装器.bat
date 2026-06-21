@echo off
REM Claude Code 扩展汉化 · Windows 一键启动器
REM 双击本文件即可调起 GUI(隐藏黑窗口,弹 PowerShell 窗口跑安装)
chcp 65001 >nul
powershell -ExecutionPolicy Bypass -File "%~dp0安装器.ps1"
