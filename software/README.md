# Software part for lemon keypad

Here is the program for lemon keypad running on top the CircuitPython firmware.

Using any Pico compatible cpy firmware variant is OK.

Aha! It's not KMK, but an original multi-layer keyboard implementation :D

## Quick package deploy

1. Install circup and ensure a good internet connection
2. Run the script with target folder as parameter: `./scripts/distribute.sh distribution`

Then the full distributable program package is the `distribution` folder.

## User documentation

Currently only zh-cn available.

## Possible flaws

- Not support key matrix natively, for it's using keypad directly without a mapping matrix.
  But it should be easy to implement.
- Not support bluetooth hid interface, need bt hid wrapper.
- Part of multi-layer support is not designed to be robust/not fully tested,
  so it may be not stable with too many/particular layer switch.
