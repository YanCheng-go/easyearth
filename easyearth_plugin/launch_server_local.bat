@echo off
REM Virtual environment
echo Using base directory: %BASE_DIR%

set "PYTHON_CMD=%BASE_DIR%\easyearth_env\Scripts\python.exe"
if not exist "%PYTHON_CMD%" (
    set "PYTHON_CMD=%BASE_DIR%\easyearth_env\python.exe"
)

echo Current Python: %PYTHON_CMD%

set "MODEL_CACHE_DIR=%USERPROFILE%\.cache\easyearth\models"
echo Using model cache directory: %MODEL_CACHE_DIR%

if not exist "%MODEL_CACHE_DIR%" mkdir "%MODEL_CACHE_DIR%"
if not exist "%BASE_DIR%\embeddings" mkdir "%BASE_DIR%\embeddings"
if not exist "%BASE_DIR%\images" mkdir "%BASE_DIR%\images"
if not exist "%BASE_DIR%\logs" mkdir "%BASE_DIR%\logs"
if not exist "%BASE_DIR%\predictions" mkdir "%BASE_DIR%\predictions"
if not exist "%BASE_DIR%\tmp" mkdir "%BASE_DIR%\tmp"

echo Created directories

set "USER_BASE_DIR=%BASE_DIR%"
set "RUN_MODE=local"

cd /d "%BASE_DIR%"
"%PYTHON_CMD%" -m easyearth.app
