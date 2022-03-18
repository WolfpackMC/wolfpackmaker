@echo off


cd %INST_DIR%
set install_dir=python
for /f "delims=" %%D in ('dir %install_dir% /a:d /b') do set python_dir=%%~nxD
set python_bin="%install_dir%\%python_dir%\tools\python"

%python_bin% --version 2>NUL
if errorlevel 1 (
    if not exist nuget.exe powershell -Command "Invoke-WebRequest https://dist.nuget.org/win-x86-commandline/v5.9.0/nuget.exe -OutFile nuget.exe"
    nuget install python -o %install_dir%
)

for /f "delims=" %%D in ('dir %install_dir% /a:d /b') do set python_dir=%%~nxD
set python_bin="%install_dir%\%python_dir%\tools\python"

"%python_bin%" -m pip install -r "src\requirements-client.txt" --no-warn-script-location


"%python_bin%" "src\src\launch.py" %* -d ".minecraft\mods" -v


EXIT /B %ERRORLEVEL%

