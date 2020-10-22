@echo off
if "%~1" NEQ "" (
  if "%~1" == "python" set ok=1
  if "%~1" == "python3" set ok=1
)
if defined ok (
  pyinstaller --windowed ^
              --noconfirm ^
              --icon="%GITHUB%\IV_Swinger\icons\IV_Swinger2.ico" ^
              --add-data="%GITHUB%\IV_Swinger\%1\Splash_Screen.png;." ^
              --add-data="%GITHUB%\IV_Swinger\%1\Blank_Screen.png;." ^
              --add-data="%GITHUB%\IV_Swinger\%1\version.txt;." ^
              --add-data="%GITHUB%\IV_Swinger\icons\IV_Swinger2.ico;." ^
              --name "IV Swinger 2" ^
              %GITHUB%\IV_Swinger\%1\IV_Swinger2_gui.py
) else (
  echo ERROR: must specify either 'python' or 'python3'
  exit -1
)
