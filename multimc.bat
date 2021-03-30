@echo off
set "thisDir=%~dp0"

start /wait cmd /c "%~dp0\wolfpackmaker.bat" %*

goto :EOF
