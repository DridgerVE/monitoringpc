OK = 200
BAD_REQUEST = 400
UNAUTHORIZED = 401

SALT = "29"

QUEUE_TIMEOUT = 0.1
SLEEP_TIMEOUT = 0.1
METRICS_TIMEOUT = 10

# возможные состояния ПК
STATE_OFF = 0
STATE_ON = 1
STATE_UNKNOWN = 2

STATE = {
    STATE_OFF: "OFF",
    STATE_ON: "ON",
    STATE_UNKNOWN: "UNKNOWN",
}
# таймауты для автоматического изменения состояния
STATE_TIMEOUT_UNKNOWN = 60
STATE_TIMEOUT_OFF = 300

# названия метрик
COMPUTER_STATE = "computer_state"
HOST_UPTIME = "host_uptime"
USER_UPTIME = "user_uptime"

PROMETHEUS_CLIENT_PORT = 9332
