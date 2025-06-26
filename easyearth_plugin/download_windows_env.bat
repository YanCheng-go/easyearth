@echo off
setlocal enabledelayedexpansion

REM Check where Python is located
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python is not found in PATH. Please add Python to PATH and retry.
    exit /b 1
)

REM Capture Python path
for /f "delims=" %%P in ('where python') do (
    set PYTHON_PATH=%%P
    goto FoundPython
)

:FoundPython
echo Found Python at: %PYTHON_PATH%

REM Detect Python version for dynamic scripts directory
for /f "tokens=2 delims= " %%V in ("%PYTHON_PATH%" -c "import sys; print(f\"{sys.version_info.major}{sys.version_info.minor}\")") do (
    set "PYTHON_VERSION=%%V"
)
set "SCRIPTS_DIR=%USERPROFILE%\AppData\Roaming\Python\Python%PYTHON_VERSION%\Scripts"

REM Add Scripts folder to PATH for current session only
set "PATH=%SCRIPTS_DIR%;%PATH%"

REM Set BASE_DIR if not defined
if not defined BASE_DIR (
    set "BASE_DIR=%cd%"
)
echo Using base directory: %BASE_DIR%

REM Upgrade pip and install gdown
"%PYTHON_PATH%" -m pip install --upgrade pip
"%PYTHON_PATH%" -m pip show gdown >nul 2>&1 || (
    echo gdown not found, installing...
    "%PYTHON_PATH%" -m pip install --user --force-reinstall gdown || (
        echo Failed to install gdown. Ensure Python and pip are correctly configured.
        exit /b 1
    )
)

REM Google Drive file ID and output file
set "FILE_ID=1RBv2I_30fwNGwqvBAL31vr4HO5KUbXQc"
set "OUTPUT_FILE=easyearth_env_win.tar"

REM Download environment using gdown
echo Downloading environment from Google Drive...
"%PYTHON_PATH%" -m gdown "https://drive.google.com/uc?id=%FILE_ID%" -O "%BASE_DIR%\%OUTPUT_FILE%"
if %ERRORLEVEL% neq 0 (
    echo Failed to download the environment file.
    exit /b 1
)

REM Extract the tar archive
echo Extracting environment...
"%PYTHON_PATH%" -c "import tarfile; tarfile.open(r'%BASE_DIR%\%OUTPUT_FILE%', 'r').extractall(r'%BASE_DIR%')"
if %ERRORLEVEL% neq 0 (
    echo Failed to extract the environment file.
    exit /b 1
)

REM Cleanup
del "%BASE_DIR%\%OUTPUT_FILE%"

echo Python environment for Windows system download and extraction completed successfully.