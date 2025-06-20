@echo off
setlocal enabledelayedexpansion

REM Base directory (default to current directory if not set)
set "BASE_DIR=%cd%"
echo Using base directory: %BASE_DIR%

python -m pip install --upgrade pip

REM Check for gdown and install if missing
where gdown >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo gdown could not be found, installing...
    python -m pip install --user gdown
    if %ERRORLEVEL% neq 0 (
        echo Failed to install gdown. Ensure Python and pip are correctly configured.
        exit /b 1
    )
)

REM Google Drive file ID
set "FILE_ID=1RBv2I_30fwNGwqvBAL31vr4HO5KUbXQc"
set "OUTPUT_FILE=easyearth_env_win.tar"

REM Use gdown to download
echo Downloading environment from Google Drive...
python -m gdown.cli "https://drive.google.com/uc?id=%FILE_ID%" -O "%BASE_DIR%\%OUTPUT_FILE%"
if %ERRORLEVEL% neq 0 (
    echo Failed to download the environment file.
    exit /b 1
)

REM Extract the tar archive
echo Extracting environment...
python -c "import tarfile; tarfile.open(r'%BASE_DIR%\%OUTPUT_FILE%', 'r').extractall(r'%BASE_DIR%')"
if %ERRORLEVEL% neq 0 (
    echo Failed to extract the environment file.
    exit /b 1
)

REM Cleanup
del "%BASE_DIR%\%OUTPUT_FILE%"

echo Python environment for Windows system download and extraction completed successfully.