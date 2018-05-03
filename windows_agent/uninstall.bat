@echo off
cd "%SYSTEMDRIVE%\Program Files\MonitoringClientAgent"
"ClientAgent.exe" stop
"ClientAgent.exe" remove
echo Y|del "%SYSTEMDRIVE%\Program Files\MonitoringClientAgent"
cd "%SYSTEMDRIVE%\Program Files"
echo Y|RD MonitoringClientAgent
