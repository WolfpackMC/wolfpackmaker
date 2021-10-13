@echo off
set "thisDir=%~dp0"

start /wait cmd /c "%thisDir%\wolfpackmaker.bat" %*

EXIT /B %ERRORLEVEL%
