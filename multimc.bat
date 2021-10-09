@echo off
set "thisDir=%~dp0"

start /wait cmd /K "%~dp0\wolfpackmaker.bat" %*

EXIT /B %ERRORLEVEL%
