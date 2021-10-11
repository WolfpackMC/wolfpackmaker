@echo off
set "thisDir=%~dp0"

start /wait cmd /K "%thisDir%\wolfpackmaker.bat" %*

EXIT /B %ERRORLEVEL%
