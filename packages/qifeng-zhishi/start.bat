@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set PORT=18602
set URL=http://127.0.0.1:%PORT%/web/index.html

echo.
echo  视频复刻 · 起风之时 · 学员包
echo  ==================================
echo  启动目录: %CD%
echo  端口:     %PORT%
echo.

REM 1) 端口占用检查 —— 避免浏览器打到别的本地服务
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if %errorlevel%==0 (
    echo  [错误] 端口 %PORT% 已被其它程序占用。
    echo  请关闭占用该端口的程序后再启动。
    echo.
    pause
    exit /b 1
)

REM 2) 找 Python
set PY=
where python >nul 2>nul && set PY=python
if "%PY%"=="" ( where py >nul 2>nul && set PY=py )
if "%PY%"=="" (
    echo  [错误] 未检测到 Python。
    echo  请先安装 Python 3：https://www.python.org/downloads/
    echo  安装时务必勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

REM 3) 等服务起来再开浏览器
start "" cmd /c "timeout /t 2 /nobreak >nul & start """" %URL%"

echo  正在启动本地服务... 关闭本窗口即停止服务。
echo  浏览器将自动打开：%URL%
echo.
%PY% -m http.server %PORT% --bind 127.0.0.1

endlocal
