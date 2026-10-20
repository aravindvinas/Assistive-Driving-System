#import RPi.GPIO as GPIO
import time

SPEED_OF_SOUND = 34300
WAIT_TIMEOUT = 0.04
'''

GPIO.setmode(GPIO.BCM)
GPIO.setup(14, GPIO.OUT)  # TRIG
GPIO.setup(15, GPIO.IN)   # ECHO
'''
class SlidingWindow:
    '''
    This class will take in the instantaneous values provided by the ultrasonic sensor
    in batches of self.size, and aggregate over those values.
    '''
    def __init__(self, size):
        self.size = size
        self.window = []

    def update(self, new_value):
        '''
        We append a new value when the sensor gets a new distance
        we also do not need the previous values so those get discarded
        '''
        if new_value is None:
            return None
        self.window.append(new_value)
        if len(self.window) > self.size:
            self.window.pop(0) # discarding the first item so the list returns back to a length of size, self.size

        print(f"{self.window}")

        return sum(self.window) / len(self.window)

sliding_window = SlidingWindow(size=5)
'''
def measure_distance():
    # GPIO 14 is connected to TRIG and GPIO15 to ECHO
    # we initiate a measurement by setting the TRIG input to 
    # high for at least 10 microseconds
    GPIO.output(14, GPIO.HIGH) # set to high
    time.sleep(0.00001)  # wait for at least 10 microseconds, rPi might take more time but that is fine
    GPIO.output(14, GPIO.LOW) # end pulse

    timeout = time.time() + WAIT_TIMEOUT # The sensor should wait for a HIGH signal for WAIT_TIMEOUT(arbitrary) seconds before continuing
    while GPIO.input(15) == 0:
        start_time = time.time()
        if start_time > timeout:
            return None

    timeout = time.time() + WAIT_TIMEOUT # The sensor should wait for a LOW signal for WAIT_TIMEOUT(arbitrary) seconds and then continue
    while GPIO.input(15) == 1:
        end_time = time.time()
        if end_time > timeout:
            return None
        
    # Calculate distance in cm
    elapsed_time = end_time - start_time
    # the distance = time x speed of sound(34,300cm/s)/2
    distance = (elapsed_time * SPEED_OF_SOUND) / 2
    return distance

def get_smoothed_distance():
    d = measure_distance()

    if d is not None:
        return sliding_window(d)
    return None

    '''