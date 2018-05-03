@echo off
cd %~dp0
pip install -r requirements.txt
pyinstaller -F --hidden-import=win32timezone ClientAgent.py
regedit.exe -s config.reg
MD "%SYSTEMDRIVE%\Program Files\MonitoringClientAgent"
copy dist\ClientAgent.exe "%SYSTEMDRIVE%\Program Files\MonitoringClientAgent\ClientAgent.exe"
copy uninstall.bat "%SYSTEMDRIVE%\Program Files\MonitoringClientAgent\uninstall.bat"
cd "%SYSTEMDRIVE%\Program Files\MonitoringClientAgent"
"ClientAgent.exe" --startup=delayed install
"ClientAgent.exe" start