#!/usr/bin/env python
# -*- coding: utf-8 -*-

import psycopg2
import os
import time
import logging

from .abstract import AbstractDatabase


class PostgreDB(AbstractDatabase):

    def __init__(self, timeout=1):
        super().__init__(timeout)
        self.config()
        self._db = None

    def config(self):
        """Read param connections from ENV"""
        self._config["db_host"] = os.environ.get("DB_HOST", "")
        self._config["db_port"] = os.environ.get("DB_PORT", 12345)
        self._config["db_name"] = os.environ.get("DB_NAME", "")
        self._config["db_user"] = os.environ.get("DB_USER", "")
        self._config["db_password"] = os.environ.get("DB_PASSWORD", "")
        self._config["db_table"] = os.environ.get("DB_TABLE", "")

    def connect(self):
        max_attempt = 5
        cur_attempt = 1
        while cur_attempt <= max_attempt and not self._connected:
            try:
                self._db = psycopg2.connect(database=self._config["db_name"],
                                            user=self._config["db_user"],
                                            host=self._config["db_host"],
                                            password=self._config["db_password"],
                                            port=self._config["db_port"])
                self._connected = True
                logging.info("Open connection {0}:{1}".format(self._config["db_host"], self._config["db_port"]))
                break
            except psycopg2.DatabaseError:
                time.sleep(self._timeout*cur_attempt)
                cur_attempt += 1

    def close(self):
        if self._connected:
            self._db.close()
            logging.info("Close connection {0}:{1}".format(self._config["db_host"], self._config["db_port"]))

    def push(self, data):
        # попытаемся переподключиться к БД
        if not self._connected:
            self.connect()
        # если не получилось, то выходим
        if not self._connected:
            return
        # сделаем попытку обновления данных
        error_update = False
        query = "UPDATE " + self._config["db_table"] + " SET "
        sep = ""
        for key, val in data.items():
            if key == "ipaddress":
                continue
            query += sep + key + "='" + str(val) + "'"
            sep = ", "
        query += " WHERE ipaddress='" + data["ipaddress"] + "';"
        # print("QUERY:", query)
        try:
            cur = self._db.cursor()
            cur.execute(query)
            self._db.commit()
            if not cur.rowcount:
                error_update = True
        except psycopg2.DatabaseError:
            if self._connected:
                self._db.rollback()
            return False
        # если ни одной строки не обновилось, то вставляем в БД новую строку
        if error_update:
            sep = ""
            keys = " ("
            values = " ("
            for key, val in data.items():
                keys += sep + key
                values += sep + "'" + str(val) + "'"
                sep = ", "
            keys += ") "
            values += ");"
            query = "INSERT INTO " + self._config["db_table"] + keys + "VALUES" + values
            # print("QUERY:", query)
            try:
                cur = self._db.cursor()
                cur.execute(query)
                self._db.commit()
            except psycopg2.DatabaseError:
                if self._connected:
                    self._db.rollback()
                return False
        return True
