@echo off

echo Checking for Python...

set install_dir=..\..\python
set python_dir=%install_dir%\python.3.9.3
set python_bin=%python_dir%\tools\python

%python_bin% --version 2>NUL
if errorlevel 1 (
    echo "Python not found. Grabbing NuGet..."
    if not exist nuget.exe powershell -Command "Invoke-WebRequest https://dist.nuget.org/win-x86-commandline/v5.9.0/nuget.exe -OutFile nuget.exe"
    nuget install python -o %install_dir%
    nuget verify %python_dir%\python.3.9.3.nupkg -All
    del %python_dir%\python.3.9.3.nupkg
)

%python_bin% -m pip install -r ..\wolfpackmaker\requirements.txt --no-warn-script-location
%python_bin% ..\wolfpackmaker\wolfpackmaker.py %*

