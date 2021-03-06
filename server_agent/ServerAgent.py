import argparse
import logging
import json
import queue
import threading
import datetime
import time
import hashlib

from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import start_http_server, Gauge

from database.postgresql import PostgreDB

from constants import *

# очереди для обработки сообщений
work_queue = queue.Queue()
db_queue = queue.Queue()
result_queue = queue.Queue()


class DBWorker(threading.Thread):
    """Класс-поток для записи данных в БД"""

    def __init__(self, db_q, q_timeout, **kwargs):
        super().__init__(**kwargs)
        self.db_q = db_q
        self.timeout = q_timeout
        self._stopped = False
        self.db = PostgreDB()
        self._cashed = dict()

    def stop(self):
        self._stopped = True

    def run(self):
        """Основной цикл обработки данных"""
        self.db.connect()
        while not self._stopped:
            try:
                data = self.db_q.get(block=True, timeout=self.timeout)
                # перед тем как отправлять данные на запись БД, нужно убедиться, что они изменились
                tmp = self._cashed.get(data["ipaddress"], dict())
                if data != tmp:
                    self.db.push(data)
                    self._cashed[data["ipaddress"]] = data.copy()
                self.db_q.task_done()
            except queue.Empty:
                continue
            except:
                self.db_q.task_done()
                continue
        self.db.close()


class Worker(threading.Thread):
    """Класс-поток для обработки данных"""

    def __init__(self, q, db_q, result_q, q_timeout, **kwargs):
        super().__init__(**kwargs)
        self.queue = q
        self.db_q = db_q
        self.result_q = result_q
        self.timeout = q_timeout
        self._stopped = False

    def stop(self):
        self._stopped = True

    def run(self):
        """Основной цикл обработки данных"""
        while not self._stopped:
            try:
                data = self.queue.get(block=True, timeout=self.timeout)
                self._do_work(data)
                self.queue.task_done()
            except queue.Empty:
                continue
            except:
                self.queue.task_done()
                continue

    def send_to_db(self, data):
        try:
            db_data = {"mashinename": data["hostname"], "ipaddress": data["localip"], "isalive": 1,
                       "islogin": 0, "curuser": "", "timeenter": "",
                       "versionsystem": data["version"], }
            if data["event"] == "stop":
                db_data["isalive"] = 0
            elif data["event"] != "logoff":
                if data["username"]:
                    db_data["curuser"] = data["username"]
                    db_data["islogin"] = 1
                    db_data["timeenter"] = datetime.datetime.fromtimestamp(data["logintime"]).strftime("%Y%m%d%H%M%S")
            self.db_q.put(db_data, block=False)
        except:
            return

    def send_to_metrics(self, data):
        try:
            m_data = {"uid": data["uid"],
                      "hostname": data["hostname"], "ip": data["localip"], "domainname": data["domain"],
                      "host_uptime": data["host_uptime"], "state": STATE_ON,
                      "username": data["username"], "user_uptime": data["user_uptime"],
                      "time_last_action": datetime.datetime.now().timestamp(), "is_read_metrics": False,
                      "versionsystem": data["version"]
                      }
            if data["event"] == "stop":
                m_data["state"] = STATE_OFF
            self.result_q.put(m_data, block=False)
        except:
            return

    def _do_work(self, data):
        self.send_to_db(data)
        self.send_to_metrics(data)


class HTTPRequestHandler(BaseHTTPRequestHandler):
    """Реализация функционала веб-сервера
    Реализуем только метод POST"""

    def log_message(self, format, *args):
        logging.info("%s - - [%s] %s" %
                     (self.address_string(),
                      self.log_date_time_string(),
                      format % args))

    def do_POST(self):
        data_string = self.rfile.read(int(self.headers['Content-Length']))
        request = json.loads(data_string)
        if "event" not in request or "token" not in request:
            self.send_response(BAD_REQUEST)
        else:
            if request["token"] != hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + SALT).encode('utf-8')).hexdigest():
                self.send_response(UNAUTHORIZED)
            else:
                self.send_response(OK)
                work_queue.put(request, block=False)
        self.end_headers()
        return


class HTTPRequestMetric(threading.Thread):

    def __init__(self, result_q, q_timeout, port, timeout, **kwargs):
        super().__init__(**kwargs)
        self.metrics = dict()
        self.m1 = Gauge(COMPUTER_STATE, "PC state", ["uid", "statename"])
        self.m2 = Gauge(HOST_UPTIME, "Host uptime", ["uid", "hostname", "ip", "domainname", "versionsystem"])
        self.m3 = Gauge(USER_UPTIME, "User uptime", ["uid", "hostname", "ip", "domainname", "username", "versionsystem"])
        self._port = port
        self._timeout = timeout
        self._stopped = False
        start_http_server(self._port)
        self.m1_old = []
        self.m2_old = []
        self.m3_old = []
        self.state_off = {}
        #
        self.result_q = result_q
        self.timeout = q_timeout
        self._seconds = 0

    def stop(self):
        self._stopped = True

    def clear_metrics(self):
        for el in self.m1_old:
            self.m1.remove(*el)
        self.m1_old = []
        for el in self.m2_old:
            self.m2.remove(*el)
        self.m2_old = []
        for el in self.m3_old:
            self.m3.remove(*el)
        self.m3_old = []

    #
    def check_state(self):
        for key in self.metrics:
            if self.metrics[key]["state"] == STATE_OFF:
                continue
            if self.metrics[key]["state"] == STATE_UNKNOWN:
                if datetime.datetime.now().timestamp() - self.metrics[key]["time_last_action"] > STATE_TIMEOUT_OFF:
                    self.metrics[key]["state"] = STATE_OFF
            else:
                if datetime.datetime.now().timestamp() - self.metrics[key]["time_last_action"] > STATE_TIMEOUT_UNKNOWN:
                    self.metrics[key]["state"] = STATE_UNKNOWN

    #
    def read_queue(self):
        self._seconds += self._timeout
        if self._seconds > 60:
            self._seconds = 0
            self.check_state()
        try:
            data = self.result_q.get(block=True, timeout=self.timeout)
            self.metrics[data["uid"]] = data.copy()
            self.result_q.task_done()
        except queue.Empty:
            pass
        except:
            self.result_q.task_done()

    #
    def make_metrics(self):
        for key, val in self.metrics.items():
            self.m1.labels(key, STATE[val["state"]]).set(1)
            self.m1_old.append((key, STATE[val["state"]]))
            if val["state"] != STATE_OFF and self.state_off.get(key, 0) < STATE_TIMEOUT_UNKNOWN:
                self.m2.labels(key, val["hostname"], val["ip"], val["domainname"], val["versionsystem"]).set(val["host_uptime"])
                self.m2_old.append((key, val["hostname"], val["ip"], val["domainname"], val["versionsystem"]))
                if val["username"]:
                    self.m3.labels(key, val["hostname"], val["ip"], val["domainname"], val["username"], val["versionsystem"]).set(
                        val["user_uptime"])
                    self.m3_old.append((key, val["hostname"], val["ip"], val["domainname"], val["username"], val["versionsystem"]))
                    self.state_off[key] = \
                        self.state_off.get(key, 0) + self._timeout if val["state"] == STATE_UNKNOWN else 0
            elif val["state"] == STATE_ON:
                self.state_off[key] = 0

    def run(self):
        """Основной цикл обработки данных"""
        while not self._stopped:
            self.read_queue()
            self.clear_metrics()
            self.make_metrics()
            time.sleep(self._timeout)


def main():
    parser = argparse.ArgumentParser(description='Server agent web server')
    parser.add_argument('-w', default=4, type=int, dest='workers_count', help='Worker count')
    parser.add_argument('-a', default='0.0.0.0', dest='host', help='Server agent web server bind address')
    parser.add_argument('-p', default=8080, type=int, dest='port', help='Server agent web server port')
    parser.add_argument('-l', default=None, dest='log', help='Log filename')
    args = parser.parse_args()
    logging.basicConfig(filename=args.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')

    httpd = HTTPServer((args.host, args.port), HTTPRequestHandler)

    logging.info("Serving HTTP on {0} port {1} (http://{0}:{1}/) ...".format(args.host, args.port))

    threads = [Worker(work_queue, db_queue, result_queue, QUEUE_TIMEOUT, name="Thread {0}".format(i))
               for i in range(args.workers_count)]
    for th in threads:
        th.start()
        logging.info("Thread is started: {0}".format(th.name))

    thread_db = DBWorker(db_queue, QUEUE_TIMEOUT, name="Thread DB")
    thread_db.start()
    logging.info("Thread is started: {0}".format(thread_db.name))

    client_prom = HTTPRequestMetric(result_queue, QUEUE_TIMEOUT, PROMETHEUS_CLIENT_PORT, METRICS_TIMEOUT)
    client_prom.start()
    logging.info("Prometheus client is started")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    httpd.server_close()

    client_prom.stop()
    client_prom.join()
    logging.info("Prometheus client is stopped")

    thread_db.stop()
    thread_db.join()
    logging.info("Thread is stopped: {0}".format(thread_db.name))

    for th in threads:
        th.stop()
        th.join()
        logging.info("Thread is stopped: {0}".format(th.name))


if __name__ == '__main__':
    main()
