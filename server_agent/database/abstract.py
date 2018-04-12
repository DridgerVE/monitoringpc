#!/usr/bin/env python
# -*- coding: utf-8 -*-

from abc import abstractmethod


class AbstractDatabase(object):

    def __init__(self, timeout):
        self._connected = False
        self._timeout = timeout
        self._config = {"db_host": "host",
                        "db_port": 12345,
                        "db_name": "name",
                        "db_user": "user",
                        "db_password": "password"}

    @abstractmethod
    def connect(self):
        """Connect to database"""
        # обязательно реализовать в наследниках
        raise NotImplementedError

    @abstractmethod
    def close(self):
        """Close connect"""
        # обязательно реализовать в наследниках
        raise NotImplementedError

    @abstractmethod
    def push(self, data):
        """Insert or Update data in DB"""
        # обязательно реализовать в наследниках
        raise NotImplementedError
