import board
from busio import I2C

from neopixel import NeoPixel
from adafruit_lsm6ds.lsm6ds3trc import LSM6DS3TRC

from adafruit_hid.consumer_control_code import ConsumerControlCode
from adafruit_hid.keycode import Keycode


# board consts
I2C_SCL = board.GP9
I2C_SDA = board.GP8
PIXEL_PIN = board.GP7
BUTTON_PINS = [board.GP0, board.GP1, board.GP2, board.GP3, board.GP4, board.GP5]

# initialize hardware except buttons/keys
pixels = NeoPixel(PIXEL_PIN, 6)
pixels.fill((0, 0, 0))
i2c = I2C(I2C_SCL, I2C_SDA)
imu = LSM6DS3TRC(i2c, 0x6a)

# Pull code for lemon keypad
from lemon_keypad import LemonKeypad
from lemon_keypad import CompositeAction as Act
from lemon_keypad import ConsumerCode as CC
from lemon_keypad import KeySequence as KS
from lemon_keypad import KeyCombination as KC
from lemon_keypad import TapDance as TD
from lemon_keypad.keycode_helper import *
# from lemon_keypad.playground.level_gauge import level_gauge
from lemon_keypad.playground.gyro_mouse import gyro_mouse

# basic keypad configuration
keypad = LemonKeypad()
keypad.keys = BUTTON_PINS
keypad.key_active_value = False  # all pins are low active
keypad.imu = imu
keypad.pixels = pixels

# verbose logging
keypad.debug = True

# well you CAN change the default keymap layer id
# but make sure it exists
#keypad.default_layer = 0

# enable watchdog if you'd like to
# MCU will reset itself if watchdog timed out
#keypad.enable_watchdog()

# Your key map
# The default keymap is indexed as "0"(integer)(yet can be changed)
# key actions:
# - integer: raw keyboard keycode sent though keyboard hid interface
# - string: text sent though keyboard hid interface
# - Mouse(int): mouse buttons
# - ConsumerCode(int): consumer control key(aka. media key, like MUTE, PAUSE)
# - KeySequence(*): sequence of keys/actions to perform
# - KeyCombination(*): combination of keys/actions to perform
# - TapDance(*): tap to determine which key/action to perform
keymap = {
    0: [
        C_PLAY_PAUSE,
        Act(C_SCAN_NEXT_TRACK, C_FAST_FORWARD),
        C_VOLUME_INCREMENT,
        TD(C_MUTE, None, gyro_mouse),
        C_VOLUME_DECREMENT,
        Act(C_SCAN_PREVIOUS_TRACK, C_REWIND),
    ],
}

# set keymap
keypad.keymap = keymap

keypad.run()
