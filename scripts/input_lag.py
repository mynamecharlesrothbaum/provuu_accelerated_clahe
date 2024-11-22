import Jetson.GPIO as GPIO
import time
import numpy as np
import pygame 

w = 1920
h = 1200

cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Image", int(w/2), int(h/2))
cv2.setWindowProperty("Image",cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

black = np.zeros(shape=(h, w), dtype=np.uint8)
white = np.ones(shape=(h, w), dtype=np.uint8) * 255

led_pin = 7

GPIO.setmode(GPIO.BOARD)
GPIO.setup(led_pin, GPIO.OUT, initial=GPIO.HIGH)

count = 1
try:
    while True:
        count += 1
        GPIO.output(led_pin, GPIO.HIGH)
        cv2.imshow("Image", white)
        cv2.waitKey(1)  # Ensure the window is updated
        time.sleep(1)
        
        GPIO.output(led_pin, GPIO.LOW)
        cv2.imshow("Image", black)
        cv2.waitKey(1)  # Ensure the window is updated
        time.sleep(1)
        
        if(count > 30):
            break  # Add a break to exit the loop after 10 cycles
except KeyboardInterrupt:
    pass

GPIO.cleanup()
cv2.destroyAllWindows()  # Ensure all OpenCV windows are properly closed
