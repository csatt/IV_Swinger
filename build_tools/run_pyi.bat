@echo off
pyinstaller --windowed ^
            --noconfirm ^
            --icon="%GITHUB%\IV_Swinger\icons\IV_Swinger2.ico" ^
            --add-data="%GITHUB%\IV_Swinger\python3\Splash_Screen.png;." ^
            --add-data="%GITHUB%\IV_Swinger\python3\Blank_Screen.png;." ^
            --add-data="%GITHUB%\IV_Swinger\python3\version.txt;." ^
            --add-data="%GITHUB%\IV_Swinger\icons\IV_Swinger2.ico;." ^
            --name "IV Swinger 2" ^
            %GITHUB%\IV_Swinger\python3\IV_Swinger2_gui.py
