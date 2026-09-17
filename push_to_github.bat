@echo off
title Push Updates to GitHub
echo ========================================================
echo    Pushing Trading Terminal Updates to GitHub
echo ========================================================
cd /d "%~dp0"

echo [1/3] Adding changes...
git add .

set /p commit_msg="Enter commit message (or press ENTER for default): "
if "%commit_msg%"=="" set commit_msg=update: terminal and strategy improvements

echo [2/3] Committing changes...
git commit -m "%commit_msg%"

echo [3/3] Pushing to GitHub...
git push

echo ========================================================
echo    Done! Changes pushed to GitHub successfully.
echo ========================================================
pause
