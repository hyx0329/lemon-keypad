import board
import digitalio
import microcontroller
import os
import supervisor
import storage
import usb_hid

# easy board customization
supervisor.set_usb_identification(manufacturer="Potato Lab", product="Lemon Keypad")
usb_hid.set_interface_name("Lemon Keypad")

# change drive label, up to 11 chars
DRIVE_LABEL = os.getenv('drive_label')
if DRIVE_LABEL is None:
	DRIVE_LABEL = "LEMONKEYPAD"
if DRIVE_LABEL != storage.getmount("/").label:
	storage.remount("/", readonly=False)
	m = storage.getmount("/")
	m.label = DRIVE_LABEL
	storage.remount("/", readonly=True)

# All pins except the one for key1(GP0, the one to enter bootloader), total 5 keys.
# Use pin IDs for best compatibility(i.e. user can upgrade to a compatible firmware without compiling it manually/changing source code)
button_pins = [board.GP1, board.GP2, board.GP3, board.GP4, board.GP5]

# the physical value when a button is pressed.
button_active_value = False

# our array of button objects
buttons = []

# make all pin objects, make them inputs w/pulls
for pin in button_pins:
	button = digitalio.DigitalInOut(pin)
	button.direction = digitalio.Direction.INPUT
	button.pull = digitalio.Pull.DOWN if button_active_value else digitalio.Pull.UP
	buttons.append(button)

# count active buttons
active_buttons = 0
for button in buttons:
	if button.value == button_active_value: # buttons are low active
		active_buttons += 1

# if 3 or more buttons pressed simultaneously, enter safe mode.
# This is useful when something needs change or goes wrong.
if active_buttons >= 3:
	microcontroller.on_next_reset(microcontroller.RunMode.SAFE_MODE)
	microcontroller.reset()

# Disable mass storage interface, so almost looks like a regular keypad.
# But only when configured.
if os.getenv('disable_usb_drive') or ('disable_usb_drive.txt' in os.listdir('/')):
	storage.disable_usb_drive()
if os.getenv('lock_usb_drive') or ('lock_usb_drive.txt' in os.listdir('/')):
	# make it read-write for CPY, so it'll become read-only for host because of the concurrent write protection
	storage.remount('/', readonly=False)

# Disable serial console. NOT RECOMMENDED FOR ROOKIES.
# Read https://learn.adafruit.com/customizing-usb-devices-in-circuitpython/circuitpy-midi-serial#usb-serial-console-repl-and-data-3096590-12
if os.getenv('disable_serial_console'):
	import usb_cdc
	usb_cdc.disable()
