@echo off

:: Virtual environment
echo Using base directory: %BASE_DIR%
call "%BASE_DIR%\easyearth_env\Scripts\activate.bat"
set PATH=%BASE_DIR%\easyearth_env\Scripts;%PATH%
set PYTHON_CMD=%BASE_DIR%\easyearth_env\Scripts\python
echo Current Python: %PYTHON_CMD%
%PYTHON_CMD% --version

:: Determine model cache directory
if "%OS%"=="Windows_NT" (
    set "MODEL_CACHE_DIR=%USERPROFILE%\.cache\easyearth\models"
) else (
    set "MODEL_CACHE_DIR=%HOME%\.cache\easyearth\models"
)

echo Using model cache directory: %MODEL_CACHE_DIR%

:: Create necessary directories
mkdir "%MODEL_CACHE_DIR%" 2>nul
mkdir "%BASE_DIR%\embeddings" 2>nul
mkdir "%BASE_DIR%\images" 2>nul
mkdir "%BASE_DIR%\logs" 2>nul
mkdir "%BASE_DIR%\predictions" 2>nul
mkdir "%BASE_DIR%\tmp" 2>nul

echo Created directories

:: Set environment variables
set USER_BASE_DIR=%BASE_DIR%
set RUN_MODE=local
set PYTORCH_ENABLE_MPS_FALLBACK=1

:: Navigate to the base directory and run the application
cd /d "%BASE_DIR%"
"%PYTHON_CMD%" -m easyearth.app --host 0.0.0.0 --port 3781
