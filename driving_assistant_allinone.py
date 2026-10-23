#!/usr/bin/env python3
"""Driving/reversing assistant: HC-SR04 + buzzer + live phone dashboard.

BCM pin mapping:
  TRIG  GPIO24 (physical pin 18)
  ECHO  GPIO23 (physical pin 16) -- MUST use a voltage divider to reduce 5V echo to 3.3V
  Buzzer GPIO18 (physical pin 12)
  GND   physical pin 6 (common ground)

Runs without Flask or other web-framework dependencies. Dashboard is served on port 5000.
"""
import json
import logging
import signal
import threading
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

TRIG_PIN = 24
ECHO_PIN = 23
BUZZER_PIN = 18
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000
POLL_SECONDS = 0.12
MAX_VALID_CM = 400.0

# State thresholds in centimetres
DANGER_CM = 30.0
WARNING_CM = 60.0
CAUTION_CM = 100.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("driving-assistant")


class Assistant:
    def __init__(self):
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.distance_samples = deque(maxlen=3)
        self.pwm = None
        self.last_duty = None
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.state = {
            "distance_cm": None,
            "raw_cm": None,
            "zone": "UNKNOWN",
            "message": "Waiting for the first sensor reading…",
            "buzzer": "OFF",
            "sensor_ok": False,
            "updated": None,
            "error": None,
        }

    def setup_gpio(self):
        if GPIO is None:
            raise RuntimeError("RPi.GPIO is not installed. Run this program on the Raspberry Pi.")
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(TRIG_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(ECHO_PIN, GPIO.IN)
        GPIO.setup(BUZZER_PIN, GPIO.OUT, initial=GPIO.LOW)
        time.sleep(0.1)
        # Passive buzzer supported through PWM; duty cycle 0 means silent.
        self.pwm = GPIO.PWM(BUZZER_PIN, 2000)
        self.pwm.start(0)
        log.info("GPIO ready: TRIG=%s ECHO=%s BUZZER=%s", TRIG_PIN, ECHO_PIN, BUZZER_PIN)

    def read_distance(self):
        # Trigger HC-SR04 with a 10 microsecond pulse.
        GPIO.output(TRIG_PIN, GPIO.LOW)
        time.sleep(0.000002)
        GPIO.output(TRIG_PIN, GPIO.HIGH)
        time.sleep(0.00001)
        GPIO.output(TRIG_PIN, GPIO.LOW)

        # Wait for echo start and end, with timeouts so a disconnected sensor
        # cannot freeze the program.
        timeout = time.monotonic() + 0.03
        while GPIO.input(ECHO_PIN) == 0:
            if time.monotonic() > timeout:
                return None
        pulse_start = time.monotonic()
        timeout = pulse_start + 0.03
        while GPIO.input(ECHO_PIN) == 1:
            if time.monotonic() > timeout:
                return None
        pulse_end = time.monotonic()
        distance = (pulse_end - pulse_start) * 34300.0 / 2.0
        if distance <= 0 or distance > MAX_VALID_CM:
            return None
        return round(distance, 1)

    @staticmethod
    def zone_for(distance):
        if distance is None:
            return "UNKNOWN"
        if distance <= DANGER_CM:
            return "DANGER"
        if distance <= WARNING_CM:
            return "WARNING"
        if distance <= CAUTION_CM:
            return "CAUTION"
        return "SAFE"

    @staticmethod
    def message_for(zone, distance):
        if zone == "DANGER":
            return "STOP — obstacle very close"
        if zone == "WARNING":
            return "Slow down — obstacle nearby"
        if zone == "CAUTION":
            return "Caution — obstacle ahead"
        if zone == "SAFE":
            return "Area appears clear"
        return "No valid echo — check sensor/target"

    def update_buzzer(self, zone, distance):
        if self.pwm is None:
            return
        now = time.monotonic()
        # DANGER: continuous tone. WARNING: fast intermittent beeps.
        # CAUTION: slower beeps. SAFE/UNKNOWN: silent.
        if zone == "DANGER":
            duty = 50
        elif zone == "WARNING":
            duty = 50 if int(now / 0.22) % 2 == 0 else 0
        elif zone == "CAUTION":
            duty = 50 if int(now / 0.75) % 2 == 0 else 0
        else:
            duty = 0
        if duty != self.last_duty:
            try:
                self.pwm.ChangeDutyCycle(duty)
                self.last_duty = duty
            except Exception:
                log.exception("Could not update buzzer")

    def sensor_loop(self):
        while not self.stop_event.is_set():
            try:
                raw = self.read_distance()
                if raw is not None:
                    self.distance_samples.append(raw)
                    # Median of up to 3 valid readings suppresses isolated spikes.
                    ordered = sorted(self.distance_samples)
                    distance = ordered[len(ordered) // 2]
                else:
                    distance = None

                zone = self.zone_for(distance)
                self.update_buzzer(zone, distance)
                with self.lock:
                    self.state.update({
                        "distance_cm": distance,
                        "raw_cm": raw,
                        "zone": zone,
                        "message": self.message_for(zone, distance),
                        "buzzer": "CONTINUOUS" if zone == "DANGER" else (
                            "PULSING" if zone in ("WARNING", "CAUTION") else "OFF"
                        ),
                        "sensor_ok": raw is not None,
                        "updated": datetime.now().isoformat(timespec="seconds"),
                        "error": None,
                    })
                log.info("Raw: %s cm | Smoothed: %s cm | %s",
                         raw if raw is not None else "no echo",
                         distance if distance is not None else "unknown", zone)
            except Exception as exc:
                log.exception("Sensor loop error")
                with self.lock:
                    self.state.update({
                        "zone": "UNKNOWN",
                        "message": "Sensor error — check wiring",
                        "buzzer": "OFF",
                        "sensor_ok": False,
                        "updated": datetime.now().isoformat(timespec="seconds"),
                        "error": str(exc),
                    })
                self.update_buzzer("UNKNOWN", None)
            self.stop_event.wait(POLL_SECONDS)

    def snapshot(self):
        with self.lock:
            data = dict(self.state)
        data.update({
            "trig_pin_bcm": TRIG_PIN,
            "echo_pin_bcm": ECHO_PIN,
            "buzzer_pin_bcm": BUZZER_PIN,
            "thresholds_cm": {
                "danger": DANGER_CM, "warning": WARNING_CM, "caution": CAUTION_CM
            },
            "started_at": self.started_at,
        })
        return data

    def shutdown(self):
        self.stop_event.set()
        if self.pwm is not None:
            try:
                self.pwm.ChangeDutyCycle(0)
                self.pwm.stop()
            except Exception:
                pass
        if GPIO is not None:
            try:
                GPIO.output(BUZZER_PIN, GPIO.LOW)
                GPIO.cleanup()
            except Exception:
                pass


assistant = Assistant()


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#101827">
<title>Driving Assistant</title>
<style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#edf2f7;min-height:100vh}
main{max-width:760px;margin:auto;padding:22px 16px 36px}
header{display:flex;align-items:center;gap:12px;margin-bottom:20px}
.logo{width:48px;height:48px;border-radius:14px;background:#1e293b;display:grid;place-items:center;font-size:25px}
h1{font-size:1.35rem;margin:0}header p{color:#9caec5;margin:3px 0 0;font-size:.9rem}
.panel{background:#131e30;border:1px solid #26354b;border-radius:20px;padding:20px;margin:14px 0}
.zone{font-size:clamp(2rem,9vw,3.4rem);font-weight:850;letter-spacing:.04em;margin:5px 0}
.distance{font-size:2.5rem;font-weight:750;margin:8px 0}
.muted{color:#9caec5}.small{font-size:.85rem}
.pill{display:inline-block;padding:6px 10px;border-radius:999px;background:#26354b;font-size:.8rem;font-weight:700}
.DANGER{color:#ff6b6b}.WARNING{color:#ffb454}.CAUTION{color:#ffe082}.SAFE{color:#6ee7a0}.UNKNOWN{color:#aab7ca}
.bar{height:10px;background:#26354b;border-radius:20px;overflow:hidden;margin:16px 0 8px}
.fill{height:100%;width:0%;background:currentColor;transition:width .2s}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.stat{padding:14px;background:#0d1727;border-radius:13px}
.stat b{display:block;margin-top:5px;font-size:1.05rem}
ol{padding-left:20px;color:#bdc9d9;line-height:1.7}
footer{color:#71839c;text-align:center;font-size:.78rem;margin-top:20px}
@media(max-width:440px){main{padding:16px 12px}.panel{padding:16px}.grid{gap:8px}}
</style>
</head>
<body><main>
<header><div class="logo">🚗</div><div><h1>Driving Assistant</h1><p>Live reversing distance monitor</p></div></header>
<section class="panel">
<div class="muted small">OBSTACLE STATUS</div>
<div id="zone" class="zone UNKNOWN">CONNECTING</div>
<div id="message">Waiting for Raspberry Pi…</div>
<div id="distance" class="distance">-- <span class="small muted">cm</span></div>
<div class="bar"><div id="fill" class="fill"></div></div>
<div class="muted small">Distance scale: 0–100 cm</div>
</section>
<section class="panel">
<div class="grid">
<div class="stat"><span class="muted small">Buzzer</span><b id="buzzer">--</b></div>
<div class="stat"><span class="muted small">Sensor</span><b id="sensor">--</b></div>
<div class="stat"><span class="muted small">Last update</span><b id="updated">--</b></div>
<div class="stat"><span class="muted small">Pi service</span><b id="service">Connecting…</b></div>
</div>
</section>
<section class="panel"><b>Alert ranges</b><ol>
<li><span class="DANGER">DANGER: 0–30 cm</span> — continuous tone</li>
<li><span class="WARNING">WARNING: over 30–60 cm</span> — fast beeps</li>
<li><span class="CAUTION">CAUTION: over 60–100 cm</span> — slower beeps</li>
<li><span class="SAFE">SAFE: over 100 cm</span> — silent</li>
<li><span class="UNKNOWN">UNKNOWN</span> — no valid echo; silent</li>
</ol><p class="muted small">Use this as an experimental aid only. Keep looking and check your surroundings; do not rely on this system as the sole safety device.</p></section>
<footer>Raspberry Pi • HC-SR04 • Auto-refreshes every 0.5 seconds</footer>
</main>
<script>
async function refresh(){
 try{
  const r=await fetch('/api/status',{cache:'no-store'});
  if(!r.ok) throw new Error('HTTP '+r.status);
  const d=await r.json(); const z=d.zone||'UNKNOWN';
  const zone=document.getElementById('zone'); zone.textContent=z; zone.className='zone '+z;
  document.getElementById('message').textContent=d.message||'';
  document.getElementById('distance').innerHTML=(d.distance_cm===null||d.distance_cm===undefined?'--':Number(d.distance_cm).toFixed(1))+' <span class="small muted">cm</span>';
  const fill=document.getElementById('fill'); fill.style.width=Math.max(0,Math.min(100,100-(Number(d.distance_cm||0))))+'%'; fill.className='fill '+z;
  document.getElementById('buzzer').textContent=d.buzzer||'--';
  document.getElementById('sensor').textContent=d.sensor_ok?'OK':'NO ECHO';
  document.getElementById('updated').textContent=d.updated?new Date(d.updated).toLocaleTimeString():'--';
  document.getElementById('service').textContent='Online';
 }catch(e){document.getElementById('service').textContent='Offline';}
}
refresh();setInterval(refresh,500);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/status":
            body = json.dumps(assistant.snapshot()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/health":
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)
    def log_message(self, fmt, *args):
        log.debug("HTTP %s - %s", self.address_string(), fmt % args)


def main():
    if GPIO is None:
        raise SystemExit("ERROR: RPi.GPIO unavailable. Run on Raspberry Pi OS with python3-rpi.gpio installed.")
    assistant.setup_gpio()
    sensor_thread = threading.Thread(target=assistant.sensor_loop, name="sensor-loop", daemon=True)
    sensor_thread.start()
    server = ThreadingHTTPServer((WEB_HOST, WEB_PORT), Handler)
    server.daemon_threads = True

    def stop_handler(signum, frame):
        log.info("Stopping driving assistant…")
        assistant.stop_event.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    log.info("Dashboard listening on http://0.0.0.0:%s", WEB_PORT)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        assistant.shutdown()
        log.info("Shutdown complete")


if __name__ == "__main__":
    main()
