import asyncio
import math
from ulab.numpy.linalg import norm
from lemon_keypad.keycode_helper import M_LEFT, M_RIGHT, M_MIDDLE

try:
	from lemon_keypad import LemonKeypad
except ImportError:
	pass


async def gyro_mouse(dev: LemonKeypad):

	# set pixels, indicated program is running

	dev.pixels.fill((0, 0x16, 0x16))
	imu = dev.imu
	event_queue = dev.key_scanner.events

	sensitivity = 1.5

	while True:
		await asyncio.sleep(0)

		new_event = event_queue.get()
		if new_event is not None:
			# make mouse key inputs
			if new_event.pressed:
				if new_event.key_number == 4:
					await dev.trigger_key_press_action(M_LEFT)
				elif new_event.key_number == 3:
					await dev.trigger_key_press_action(M_MIDDLE)
				elif new_event.key_number == 2:
					await dev.trigger_key_press_action(M_RIGHT)
				elif new_event.key_number == 1:
					# increase sensitivity
					sensitivity += 0.1
					sensitivity = min(3, sensitivity)
				elif new_event.key_number == 5:
					# decrease sensitivity
					sensitivity -= 0.1
					sensitivity = max(0.3, sensitivity)
				elif new_event.key_number == 0:
					# clear pixels and quit
					dev.pixels.fill((0, 0, 0))
					return
			else:
				if new_event.key_number == 4:
					await dev.trigger_key_release_action(M_LEFT)
				elif new_event.key_number == 3:
					await dev.trigger_key_release_action(M_MIDDLE)
				elif new_event.key_number == 2:
					await dev.trigger_key_release_action(M_RIGHT)

		# The gyro only gives angular rates, not absolute values to original position
		dx, _, dz = imu.gyro

		# linear values
		# mouse_x = -dz * 10 * sensitivity
		# mouse_y = -dx * 10 * sensitivity

		# dynamic accleration, log
		# ensure x y acceleration same
		accel = math.log(abs(norm((dz, dx))) + 1)
		# clamp
		accel = min(40, accel)
		accel = max(1, accel)
		mouse_x = -dz * 10 * sensitivity * accel
		mouse_y = -dx * 10 * sensitivity * accel

		dev.move_mouse(int(mouse_x), int(mouse_y))

		# print("dz: %.2f, dx: %.2f, mouse_x: %.2f, mouse_y: %.2f, accel: %.2f, sensitivity: %.2f" % (dz, dx, mouse_x, mouse_y, accel, sensitivity))
