# Client Agent

## Requirements

  * Python 3.5.x
  * [Visual C++ Build Tools 2015](http://go.microsoft.com/fwlink/?LinkId=691126)
  * PyInstaller 3.2

## Install requirements

    env = PYTHONPATH\Scripts (C:\Users\admin\AppData\Local\Programs\Python\Python36-32\Scripts)

    (env)$ pip install -r requirements.txt

## Build

    (env)$ pyinstaller -F --hidden-import=win32timezone ClientAgent.py

## Run

    (env) dist\ClientAgent.exe install
    Installing service ClientAgent
    Service installed

    (env) dist\ClientAgent.exe start
    Starting service ClientAgent

## Clean

    (env) dist\ClientAgent.exe stop
    (env) dist\ClientAgent.exe remove

## Описание работы

    1. Параметры подключения к серверу лежат в реестре, а также версия сборки ОС и уникальный идентификатор
    2. Логирование в журнал Windows (журнал приложений)
    3. Собираем следующую информацию:
        уникальный идентификатор (если в реестре отсутствует, то используем mac-адрес),
        имя хоста,
        время включения хоста (по сути старта службы),
        время выключения хоста (остановка службы),
        имя домена и активного пользователя (используем обертку wmi),
        время входа пользователя в систему и время выхода из системы
    4. Push серверу происходит при старте и остановке, а также раз в 30 секунд (отпраляются события "login", "logoff", "state")
