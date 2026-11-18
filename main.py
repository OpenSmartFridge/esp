import time

import network
import ntptime
import ujson
import urequests
from machine import Pin

SSID = ""
PASSWORD = ""
URL = "https:///api/get_products_with_key"
KEY = ""
CRONS = [
    "*/10 * * * * *",
    "0 0 12 * * *",
]

wlan = network.WLAN(network.STA_IF)
always_on = Pin(32, Pin.OUT, value=1)
warning = Pin(33, Pin.OUT, value=0)


def connect():
    try:
        wlan.active(True)
        if wlan.isconnected():
            return True
        wlan.connect(SSID, PASSWORD)
        for _ in range(20):
            if wlan.isconnected():
                return True
            time.sleep(1)
    except Exception as error:
        print("WLAN:", error)
        try:
            wlan.active(False)
            time.sleep(1)
        except Exception:
            pass
    return False


def products():
    response = None
    try:
        response = urequests.post(
            URL,
            data=ujson.dumps({"key": KEY}),
            headers={"Content-Type": "application/json"},
        )
        print("API:", response.status_code)
        return response.json() if response.status_code == 200 else []
    except Exception as error:
        print(error)
        return []
    finally:
        if response:
            response.close()


def expiring(items):
    now = time.time()
    limit = now + 7 * 24 * 60 * 60
    for item in items:
        value = item.get("Expire", "")
        try:
            date, clock = value.replace("Z", "").split("T")
            year, month, day = [int(x) for x in date.split("-")]
            hour, minute, second = [int(x) for x in clock[:8].split(":")]
            if time.mktime((year, month, day, hour, minute, second, 0, 0)) <= limit:
                return True
        except Exception:
            pass
    return False


def sync():
    try:
        ntptime.settime()
        return True
    except Exception as error:
        print("NTP:", error)
        return False


def blink():
    for _ in range(5):
        warning.value(1)
        time.sleep(1)
        warning.value(0)
        time.sleep(1)


def cron_field(field, value, minimum, maximum):
    for item in field.split(","):
        if item == "*":
            return True
        if "-" in item:
            start, end = [int(x) for x in item.split("-")]
            if start <= value <= end:
                return True
        elif "/" in item:
            base, step = item.split("/")
            step = int(step)
            start = minimum if base == "*" else int(base)
            if step > 0 and start <= value <= maximum:
                if (value - start) % step == 0:
                    return True
        elif int(item) == value:
            return True
    return False


def cron_match():
    now = time.gmtime(time.time())
    weekday = (now[6] + 1) % 7
    values = (now[5], now[4], now[3], now[2], now[1], weekday)
    limits = ((0, 59), (0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
    for cron in CRONS:
        fields = cron.split()
        if len(fields) != 6:
            print("Ungültiger Cron:", cron)
            continue
        matches = True
        for field, value, limit in zip(fields, values, limits):
            if not cron_field(field, value, limit[0], limit[1]):
                matches = False
                break
        if matches:
            return True
    return False


synced = False
last_check = None

while True:
    if connect():
        if not synced:
            synced = sync()
        if synced:
            now = time.gmtime(time.time())
            current = now[:6]
            if cron_match() and current != last_check:
                last_check = current
                items = products()
                print("Produkte:", len(items))
                if expiring(items):
                    blink()
    time.sleep(1)
