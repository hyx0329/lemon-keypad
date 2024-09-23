import board
import neopixel
import storage
import os

pixel_pin = board.GP7
num_pixels = 6


# load neopixel and set all led to green to indicate that it's safe mode.
color = (0, 0x20, 0)
pixels = neopixel.NeoPixel(pixel_pin, num_pixels)

pixels.fill(color)

# change drive label, up to 11 chars
DRIVE_LABEL = os.getenv('drive_label')
if DRIVE_LABEL is None:
	DRIVE_LABEL = "LEMONKEYPAD"
if DRIVE_LABEL != storage.getmount("/").label:
	storage.remount("/", readonly=False)
	m = storage.getmount("/")
	m.label = DRIVE_LABEL
	storage.remount("/", readonly=True)

# Remount USB drive to make sure it's writable by host.
# Actually this is not necessary.
# If USB drive is read-only when in safemode, run a partition check and fix the errors.
storage.remount('/', readonly=True)  # This means read-only by CircuitPython and read-write by host.
