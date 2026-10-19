import RPi.GPIO as GPIO
import time


GPIO.setmode(GPIO.BCM)
GPIO.setup(14, GPIO.OUT)  # TRIG
GPIO.setup(15, GPIO.IN)   # ECHO

def measure_distance():
    GPIO.output(14, GPIO.HIGH)
    time.sleep(0.00001)  # 10us pulse
    GPIO.output(14, GPIO.LOW)

    while GPIO.input(15) == 0:
        start_time = time.time()

    while GPIO.input(15) == 1:
        end_time = time.time()
        
    # Calculate distance in cm
    elapsed_time = end_time - start_time
    distance = (elapsed_time * 34300) / 2
    return distance