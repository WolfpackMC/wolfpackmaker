@echo off


for /f "delims=" %%D in ('dir %install_dir% /a:d /b') do set python_dir=%%~nxD

echo Checking for Python...

set install_dir=..\..\python
goto :CHECK_PYTHON
set python_bin=%install_dir%\%python_dir%\tools\python

%python_bin% --version 2>NUL
if errorlevel 1 (
    echo "Python not found. Grabbing NuGet..."
    if not exist nuget.exe powershell -Command "Invoke-WebRequest https://dist.nuget.org/win-x86-commandline/v5.9.0/nuget.exe -OutFile nuget.exe"
    nuget install python -o %install_dir%
    for /f "delims=" %%D in ('dir %install_dir% /a:d /b') do set python_dir=%%~nxD
)

%python_bin% -m pip install -r ..\wolfpackmaker\requirements-client.txt --no-warn-script-location

echo "Updating wolfpackmaker.py..."
powershell -Command "Invoke-WebRequest https://raw.githubusercontent.com/kalkafox/wolfpackmaker/master/wolfpackmaker.py -OutFile ..\wolfpackmaker\wolfpackmaker.py"

%python_bin% ..\wolfpackmaker\wolfpackmaker.py %*
EXIT /B %ERRORLEVEL%

