# requirements: neopixel, adafruit_lsm6ds
import board
from busio import I2C
import digitalio
from ulab import numpy as np

import neopixel
from adafruit_lsm6ds.lsm6ds3trc import LSM6DS3TRC


i2c_scl = board.GP9
i2c_sda = board.GP8
pixel_pin = board.GP7
button_pins = [board.GP0, board.GP1, board.GP2, board.GP3, board.GP4, board.GP5]


pixels = neopixel.NeoPixel(pixel_pin, 6)
pixels.fill((0x20,0x20,0x20))


# our array of button objects
buttons = []

# the physical value when a buttons is pressed.
button_active_value = False


# make all pin objects, make them inputs w/pullups
for pin in button_pins:
    button = digitalio.DigitalInOut(pin)
    button.direction = digitalio.Direction.INPUT
    button.pull = digitalio.Pull.DOWN if button_active_value else digitalio.Pull.UP
    buttons.append(button)


states = set()
while True:
	for i in range(6):
		if not buttons[i].value:  # low active
			states.add(i)
			pixels[i] = (0, 0, 0)
	if len(states) == 6:
		print("all buttons okay")
		break


i2c = I2C(i2c_scl, i2c_sda)
imu = LSM6DS3TRC(i2c, 0x6a)
square_root_three = np.sqrt(3)
led_positions = np.array(
	(
		(0, 1),
		(square_root_three, 0.5),
		(square_root_three, -0.5),
		(0, -1),
		(-square_root_three, -0.5),
		(-square_root_three, 0.5),
	)
)

green = np.array((0, 0x40, 0))
blue = np.array((0, 0, 0x40))
red = np.array((0x40, 0, 0))

g = np.array((0, 0, 9.80665))

comp_vector = np.array((0,0,0))

import time
time.sleep(2)

for i in range(100):
	x1, y1, z1 = imu.acceleration
	comp_vector += (g - np.array((x1, y1, z1))) * 0.01

print("Comp: {}".format(comp_vector * 10000))


while True:
	# somehow the positive direction is opposite to the one specified in the image from the datasheet, perhaps a library bug?
	x1, y1, z1 = comp_vector + imu.acceleration
	x2, y2, z2 = imu.gyro
	# print("Acc: X:%6.2f, Y: %6.2f, Z: %6.2f m/s^2; G: X:%6.2f, Y: %6.2f, Z: %6.2f radians/s" % (x1, y1, z1, x2, y2, z2))
	platform_vector = np.array((x1, y1))
	length = np.linalg.norm(platform_vector)
	if length < 0.27:
		pixels.fill(green.tolist())
		continue
	unit_vector = platform_vector / length
	factors = np.dot(led_positions, unit_vector)
	# unfortunately ulab hasn't implemented reshape
	factors = np.array([factors]).transpose()
	colors = factors * red + (1 - factors) * blue
	pixels[:] = colors.tolist()
