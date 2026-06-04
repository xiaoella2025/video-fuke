@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo  老师端 · 生成激活码
echo  ==========================================
echo  按提示输入课程 ID 与学员发来的机器码。
echo.

set /p COURSE=课程 ID（起风之时填 case-02，25cm 填 25cm）:
if "%COURSE%"=="" (
    echo [错误] 课程 ID 不能为空。
    pause & exit /b 1
)

set /p DEVICE=学员机器码（如 QIFENG-XXXX-XXXX-XXXX）:
if "%DEVICE%"=="" (
    echo [错误] 机器码不能为空。
    pause & exit /b 1
)

set PY=
where python >nul 2>nul && set PY=python
if "%PY%"=="" ( where py >nul 2>nul && set PY=py )
if "%PY%"=="" (
    echo [错误] 未检测到 Python。请先安装 Python 3 并执行：pip install cryptography
    pause & exit /b 1
)

echo.
echo === 激活码（把这一整行发给学员粘贴）===
%PY% sign-license.py --course %COURSE% --device %DEVICE%
echo =====================================
echo.
pause
endlocal
