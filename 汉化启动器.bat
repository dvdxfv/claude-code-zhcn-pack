@echo off
REM Claude Code 扩展汉化 · Windows 启动器
REM 双击本文件调起 Python 跑一键汉化.py(TUI 模式)
REM 关闭黑窗口 = 中断当前步骤(脚本不会继续跑)
title Claude Code 扩展汉化 · 启动器
python 一键汉化.py --tui --audit
echo.
echo === 汉化脚本已结束,按任意键关闭窗口 ===
pause >nul