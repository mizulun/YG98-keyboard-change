@echo off
setlocal
cd /d "%~dp0\.."

echo [1/3] Installing dependencies...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m pip install --upgrade pyinstaller

echo [2/3] Building YG98CrossRipple.exe...
py -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name YG98CrossRipple ^
  --icon assets\YG98CrossRipple.ico ^
  --add-data "assets\YG98CrossRipple.ico;assets" ^
  --hidden-import=hid ^
  src\yg98_cross_ripple.py

echo [3/3] Done.
echo.
echo EXE: %CD%\dist\YG98CrossRipple.exe
echo.
pause
