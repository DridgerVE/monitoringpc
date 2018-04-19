# Server Agent

## Requirements

  * psycopg2
  * prometheus_client

## Install requirements

    pip install -r requirements.txt

## Run

    usage: python ServerAgent.py [-h] [-w WORKERS_COUNT] [-a HOST] [-p PORT] [-l LOG]
    Server agent web server
    Optional arguments:
        -h, --help        show this help message and exit
        -w WORKERS_COUNT  Worker count
        -a HOST           Server agent web server bind address
        -p PORT           Server agent web server port
        -l LOG            Log filename

## Параметры подключения к БД PostgreSQL

    Параметры должны находиться в переменных окружения
        DB_PORT	- порт
        DB_USER - имя пользователя
        DB_TABLE - нзвание таблицы
        DB_NAME - название БД
        DB_HOST - имя хоста
        DB_PASSWORD - пароль пользователя

## Описание работы

    1. Запускаем веб-сервер (порт передается параметром командной строки, по умолчанию 8080)
    2. Запускаем обработчики запросов (количество тредов по умолчанию 4)
    3. Запускаем тред для записи данных в БД
        Адаптер к БД реализован отдельным пакетом 'database', содержащем 2 файла:
            - abstract.py - содержит абстрактный класс AbstractDatabase с описанием интерфейса
            - postgresql.py - содержит класс PostgreDB для работы с БД PostgreSQL (наследуется от AbstractDatabase)
    5. Запускаем тред для построения метрик в формате prometheus
    6. Зупаскаем веб-сервер, реализованный в пакете prometheus_client, на порту 9332
    7. Синхронизация потоков происходит с помощью потокобезопасных очередей