@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0.."

echo.
echo 起风之时 · 学员交付包生成器
echo ----------------------------------------
echo 本工具会检查 packages/qifeng-zhishi 并生成带密码 zip。
echo 请不要把解压密码写进脚本或 README。
echo.

set "ZIP_PASSWORD="
set /p ZIP_PASSWORD=请输入本次压缩包解压密码：
if "%ZIP_PASSWORD%"=="" (
  echo.
  echo 未输入解压密码，已取消。
  pause
  exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  set "PYTHON_CMD=python"
)

echo.
%PYTHON_CMD% scripts\package-student-course.py ^
  --package-dir packages/qifeng-zhishi ^
  --output dist/qifeng-zhishi-student-package.zip ^
  --password "%ZIP_PASSWORD%" ^
  --course-id case-02 ^
  --expected-title "动漫视频拆解 01｜起风之时" ^
  --require-video

echo.
if %errorlevel%==0 (
  echo 已完成。输出文件：dist\qifeng-zhishi-student-package.zip
) else (
  echo 生成失败，请查看上方错误提示。
)
pause
