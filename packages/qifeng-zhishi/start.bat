@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  视频复刻 · 起风之时 · 学员包
echo  ==================================
echo.
echo  正在启动本地服务...
echo  浏览器打开后请勿关闭本窗口，关闭窗口即停止服务。
echo.

REM 先尝试 python，再尝试 py 启动器
where python >nul 2>nul
if %errorlevel%==0 (
    start "" "http://localhost:8000/web/index.html"
    python -m http.server 8000
    goto end
)

where py >nul 2>nul
if %errorlevel%==0 (
    start "" "http://localhost:8000/web/index.html"
    py -m http.server 8000
    goto end
)

echo  [错误] 未检测到 Python。
echo  请先安装 Python 3：https://www.python.org/downloads/
echo  安装时勾选 "Add Python to PATH"。
pause

:end
