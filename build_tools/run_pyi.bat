pyinstaller --windowed ^
            --noconfirm ^
            --icon="%GITHUB%\IV_Swinger\icons\IV_Swinger2.ico" ^
            --add-data="%GITHUB%\IV_Swinger\python\Splash_Screen.png;." ^
            --add-data="%GITHUB%\IV_Swinger\python\version.txt;." ^
            --add-data="%GITHUB%\IV_Swinger\icons\IV_Swinger2.ico;." ^
            --name "IV Swinger 2" ^
            %GITHUB%\IV_Swinger\python\IV_Swinger2.py
