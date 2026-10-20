import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(14, GPIO.OUT)  # TRIG
GPIO.setup(15, GPIO.IN)   # ECHO

class SlidingWindow:
    def __init__(self, size):
        self.size = size
        self.window = []

    def update(self, new_value):
        if new_value is None:
            return None
        self.window.append(new_value)
        if len(self.window) > self.size:
            self.window.pop(0)

        return sum(self.window) / len(self.window)

sliding_window = SlidingWindow(size=5)

def measure_distance():
    GPIO.output(14, GPIO.HIGH)
    time.sleep(0.00001)  # 10us pulse
    GPIO.output(14, GPIO.LOW)

    timeout = time.time() + 0.04
    while GPIO.input(15) == 0:
        start_time = time.time()
        if start_time > timeout:
            return None

    timeout = time.time() + 0.04
    while GPIO.input(15) == 1:
        end_time = time.time()
        if end_time > timeout:
            return None
        
    # Calculate distance in cm
    elapsed_time = end_time - start_time
    distance = (elapsed_time * 34300) / 2
    return distance

def get_smoothed_distance():
    d = measure_distance()

    if d is not None:
        return sliding_window(d)
    return None