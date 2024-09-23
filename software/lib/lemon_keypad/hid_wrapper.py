# adafruit_hid but modified

from adafruit_hid.keyboard import Keyboard as KB
from adafruit_hid.mouse import Mouse as MS
from adafruit_hid.consumer_control import ConsumerControl as CC

try:
	from typing import Sequence
	import usb_hid
except:  # pylint: disable=bare-except
	pass


def find_device(
	devices: Sequence[object],
	*,
	usage_page: int,
	usage: int,
) -> object:
	if hasattr(devices, "send_report"):
		devices = [devices]  # type: ignore
	device = None
	for dev in devices:
		if (
			dev.usage_page == usage_page
			and dev.usage == usage
			and hasattr(dev, "send_report")
		):
			device = dev
			break
	if device is None:
		raise ValueError("Could not find matching HID device.")

	return device


class Keyboard(KB):
	def __init__(self, devices: Sequence[usb_hid.Device], timeout: int = None) -> None:
		self._keyboard_device = find_device(
			devices, usage_page=0x1, usage=0x06
		)

		# Reuse this bytearray to send keyboard reports.
		self.report = bytearray(8)

		# report[0] modifiers
		# report[1] unused
		# report[2:8] regular key presses

		# View onto byte 0 in report.
		self.report_modifier = memoryview(self.report)[0:1]

		# List of regular keys currently pressed.
		# View onto bytes 2-7 in report.
		self.report_keys = memoryview(self.report)[2:]

		# No keyboard LEDs on.
		self._led_status = b"\x00"


class Mouse(MS):
	def __init__(self, devices: Sequence[usb_hid.Device], timeout: int = None) -> None:
		self._mouse_device = find_device(
			devices, usage_page=0x1, usage=0x02
		)

		# Reuse this bytearray to send mouse reports.
		# report[0] buttons pressed (LEFT, MIDDLE, RIGHT)
		# report[1] x movement
		# report[2] y movement
		# report[3] wheel movement
		self.report = bytearray(4)


class ConsumerControl(CC):
	def __init__(self, devices: Sequence[usb_hid.Device], timeout: int = None) -> None:
		self._consumer_device = find_device(
			devices, usage_page=0x0C, usage=0x01
		)

		# Reuse this bytearray to send consumer reports.
		self._report = bytearray(2)
