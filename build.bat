@echo off
setlocal

echo.
echo [INFO] Starting WeaveRunner build process...
echo.

set PYTHON_CMD=python
set SPEC_FILE=WeaveRunner.spec
set INSTALLER_SCRIPT=WeaveRunner_installer.iss

echo [STEP 1/3] Cleaning up previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist venv_gpu rmdir /s /q venv_gpu
echo    - Cleanup complete.
echo.

echo [STEP 2/3] Building GPU version (CUDA 12.1)...
echo    - Creating virtual environment 'venv_gpu'...
%PYTHON_CMD% -m venv venv_gpu
if errorlevel 1 goto :error

echo    - Activating environment and installing dependencies from requirements_gpu.txt...
call .\venv_gpu\Scripts\activate.bat
pip install -r requirements_gpu.txt
if errorlevel 1 goto :error

echo    - Running PyInstaller for GPU build...
pyinstaller %SPEC_FILE% --distpath dist/gpu
if errorlevel 1 goto :error
call .\venv_gpu\Scripts\deactivate.bat
echo    - GPU build successful.
echo.

echo [STEP 3/3] Compiling the installer...
iscc "%INSTALLER_SCRIPT%"
if errorlevel 1 goto :error
goto :success

:error
echo.
echo [ERROR] The build process failed at the last step.
echo Please check the output above for more details.
pause
exit /b 1

:success
echo.
echo ============================================================================
echo  BUILD SUCCEEDED
echo ============================================================================
echo.
echo Your distributable application folders are in:
echo   - dist\gpu\WeaveRunner
echo.
echo The final installer is located at:
echo   - dist\installer\WeaveRunner-setup.exe
echo.
pause
exit /b 0
