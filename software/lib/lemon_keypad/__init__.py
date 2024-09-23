from micropython import const
from microcontroller import Pin
from microcontroller import watchdog as wdt
from watchdog import WatchDogMode
import supervisor
from supervisor import ticks_ms
import gc

import usb_hid
import keypad
from collections import namedtuple

import asyncio
from neopixel import NeoPixel


from .hid_wrapper import Keyboard, Mouse, ConsumerControl
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS

import adafruit_logging as logging

try:
	from typing import Sequence
except ImportError:
	pass


logger = logging.getLogger("LemonKeypad")
logger.setLevel(logging.WARNING)

# default values
WDT_TIMEOUT = const(5) # seconds
WDT_INTERVAL = const(2) # seconds


def is_coroutine(obj):
	# This is the only we have on CircuitPython
	if obj.__class__.__name__ == "coroutine":
		return True
	return False


def no_fail_tag(tag: str):
	def no_fail(func):
		def wrapper(*args, **kwargs):
			try:
				return func(*args, **kwargs)
			except Exception as e:
				logger.debug('Ignore exception(%s): %s: %s', tag, e.__class__.__name__, e)
				return None
		return wrapper
	return no_fail


def no_fail(func):
	def wrapper(*args, **kwargs):
		try:
			return func(*args, **kwargs)
		except Exception as e:
			logger.debug('Ignore exception: %s: %s', e.__class__.__name__, e)
			return None
	return wrapper


class AsyncEventQueue:
	# Helper class which moves the polling burden from Python code to underlying C code
	# Reference: https://github.com/adafruit/circuitpython/pull/6712
	# and https://github.com/adafruit/circuitpython/issues/8412

	def __init__(self, events):
		self._events = events

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		pass

	async def __await__(self):
		await asyncio.core._io_queue.queue_read(self._events)
		return self._events.get()

	def __aiter__(self):
		return self

	async def __anext__(self):
		await asyncio.core._io_queue.queue_read(self._events)
		return self._events.get()


class CompositeAction:
	def __init__(
			self,
			tap = None, # tap
			hold = None, # hold
			layer = None, # hold
			long_hold = None, # long hold
			tap_term_ms = 200,
			hold_term_ms = 2000,
			long_hold_start_ms = 5000,
			tap_preferred = False,
		) -> None:
		if not (tap_term_ms < hold_term_ms <= long_hold_start_ms):
			raise ValueError("tap_term_ms < hold_term_ms <= long_hold_start_ms must be satisfied")
		self.tap = tap
		self.hold = hold
		self.layer = layer
		self.long_hold = long_hold
		self.tap_term_ms = tap_term_ms
		self.hold_term_ms = hold_term_ms
		self.long_hold_start_ms = long_hold_start_ms
		self.tap_preferred = tap_preferred
		# short path
		if self.tap is not None and self.layer is None and self.hold is None:
			self.tap_preferred = True
		elif self.tap is None:
			self.tap_preferred = False


# Use type to mark key type
class Delay:
	def __init__(self, delay: float) -> None:
		self.delay = delay

class ConsumerCode(int): pass
class MouseCode(int): pass

class KeyTuple(tuple):
	def __init__(self, *args, delay=0) -> None:
		super().__init__(args)
		self.delay = delay

class KeySequence(KeyTuple): pass
class KeyCombination(KeyTuple): pass

class TapDance(tuple):
	def __init__(self, *args, tap_term_ms: int = 200):
		super().__init__(args)
		self.tap_term_ms = tap_term_ms

# This is used internally, users should ONLY use CompositeAction for complex actions
LayerAction = namedtuple("LayerAction", ["layer", "action"])


class LemonKeypad:
	def __init__(self) -> None:
		# the objects to interact with the HID interface
		self.keyboard = None
		self.keyboard_layout = None  # keyboard with layout, provide an easy way to send text
		self.mouse = None
		self.consumer_control = None

		# the resources are decoupled, it's user's duty to initialize most hardwares
		self._imu = None  # inertial sensor, provides property interfaces: gyro, acceleration
		self._pixels = None  # neopixel object
		self._keys = None  # a list of gpios in the order of key numbers
		self._key_active_value = True  # the active value of the keys, also indicate the pull direction
		self._default_layer = 0

		# Ah, the key map
		# TODO: keymap format/content verification
		self.keymap = None

		# internal shared states
		self.key_scanner = None
		self.undetermined_key_index = -1
		self.undetermined_key_timestamp = 0
		self.undetermined_key_action = None
		self.undetermined_tap_dance_action_index = 0
		self.undetermined_tap_dance_pressed = False
		self.key_actions = None  # currently triggered key actions
		self.layer_tracker = None

		# extra async tasks
		# must be corroutine functions(functions that create coroutines, i.e. async def)
		self.user_tasks = None

	@property
	def imu(self) -> None:
		return self._imu

	@imu.setter
	def imu(self, value):
		if hasattr(value, 'gyro') and hasattr(value, 'acceleration'):
			self._imu = value
		else:
			raise ValueError('The IMU object must have gyro and acceleration properties')

	@property
	def pixels(self):
		return self._pixels

	@pixels.setter
	def pixels(self, value):
		if isinstance(value, NeoPixel):
			self._pixels = value
		else:
			raise ValueError('The pixels object must be a NeoPixel object')

	@property
	def keys(self):
		return self._keys

	@keys.setter
	def keys(self, value: Sequence[Pin]):
		if len(value) > 0:
			for key in value:
				if not isinstance(key, Pin):
					break
			else:
				self._keys = value
				return

		raise ValueError('The keys object must be a non-empty list of Pin objects')

	@property
	def key_active_value(self):
		return self._key_active_value

	@key_active_value.setter
	def key_active_value(self, value: bool):
		if isinstance(value, bool):
			self._key_active_value = value
		else:
			raise ValueError('The key_active_value must be a boolean')

	@property
	def debug(self):
		return logger.getEffectiveLevel <= logging.DEBUG

	@debug.setter
	def debug(self, value: bool):
		if value:
			logger.setLevel(logging.DEBUG)
		else:
			logger.setLevel(logging.WARNING)

	@property
	def default_layer(self):
		if self.layer_tracker is not None and len(self.layer_tracker) > 0:
			return self.layer_tracker[0]
		else:
			return self._default_layer

	@default_layer.setter
	def default_layer(self, value):
		self._default_layer = value
		if self.layer_tracker is not None and len(self.layer_tracker) > 0:
			self.layer_tracker[0] = value

	### Entry ###

	def run(self) -> None:
		asyncio.run(self.run_async())

	async def run_async(self) -> None:
		# create an event loop and run all tasks
		tasks = [
			asyncio.create_task(self.watchdog_feeder()),
			asyncio.create_task(self.load_hid_devices()),
		]

		if self.keys is not None:
			logger.info("Enable key event processing")
			tasks.append(asyncio.create_task(self.key_event_processer()))
		if self.imu is not None:
			logger.info("Enable IMU")
			tasks.append(asyncio.create_task(self.imu_data_processor()))
		if self.pixels is not None:
			logger.info("Enable NeoPixel")
			tasks.append(asyncio.create_task(self.pixel_animation_control()))

		if self.user_tasks is not None:
			logger.info("Enable %d user defined tasks", len(self.user_tasks))
			for task in self.user_tasks:
				tasks.append(asyncio.create_task(task()))

		await asyncio.gather(*tasks)

	### Tasks to run in the event loop ###

	async def watchdog_feeder(self):
		while True:
			wdt.feed()
			await asyncio.sleep(WDT_INTERVAL)

	async def key_event_processer(self):

		self.setup_env_key_event_processer()
		event_queue = self.key_scanner.events

		while True:
			await asyncio.sleep(0)  # switch task

			new_event = event_queue.get()
			current_timestamp = ticks_ms()

			if new_event is None:
				await self.process_undetermined_action(current_timestamp)
				continue

			logger.debug("KEY EVENT: index %d, %s", new_event.key_number, 'Pressed' if new_event.pressed else 'Released')

			if new_event.pressed:
				await self.process_undetermined_action(current_timestamp, new_press_index=new_event.key_number)
			else:
				await self.process_undetermined_action(current_timestamp)
			await self.process_new_key_event(new_event.key_number, new_event.pressed, current_timestamp)

	async def imu_data_processor(self):
		while True:
			await asyncio.sleep(1)  # switch task

	async def pixel_animation_control(self):
		while True:
			await asyncio.sleep(1)  # switch task

	async def load_hid_devices(self):
		while True:
			if not supervisor.runtime.usb_connected:
				# disconnected
				self.mouse = None
				self.keyboard = None
				self.consumer_control = None
				await asyncio.sleep(1)
				continue
			elif (self.mouse is not None
				and self.keyboard is not None
				and self.consumer_control is not None):
				# connected and working
				await asyncio.sleep(5)

			# connected and not working
			if not self.load_keyboard() or not self.load_mouse() or not self.load_consumer_control():
				# break to parent loop and re-enumerate
				break

	### Internal APIs ###

	def verify_keymap(self) -> None:
		if not isinstance(self.keymap, dict):
			raise ValueError('keymap must be a dict')
		key_count = len(self.keys)
		for k, v in self.keymap.items():
			if not isinstance(v, list) and not isinstance(v, tuple):
				raise ValueError('keymap layers must be a list or tuple, however layer %s is not' % (k,))
			if len(v) != key_count:
				raise ValueError('keymap layers must strictly define %d key actions, however layer %s is not' % (key_count, k))
		if self.default_layer not in self.keymap.keys():
			raise ValueError("default layer(which now is `%s') must be defined in keymap" % (self.default_layer,))

	def setup_env_key_event_processer(self):
		# do not modify self.keys during runtime

		if self.keymap is None:
			self.keymap = {
				self.default_layer: ('1', '2', '3', '4', '5', '6')
			}

		self.verify_keymap()

		# initialize key_scanner
		if self.key_scanner is None:
			self.key_scanner = keypad.Keys(self.keys, value_when_pressed=self.key_active_value, pull=True)

		# initialize/reset key_actions
		if self.key_actions is None:
			self.key_actions = [None] * self.key_scanner.key_count
		else:
			for i in range(len(self.key_actions)):
				self.key_actions[i] = None

		# initialize/reset layer_tracker
		if self.layer_tracker is None:
			self.layer_tracker = [0] * self.key_scanner.key_count
		self.layer_tracker.clear()
		self.layer_tracker.append(self.default_layer)

		# There's only one undetermined key at most
		# The undetermined key has a special action defined by `Action' class
		self.undetermined_key_index = -1
		self.undetermined_key_timestamp = 0

	async def process_new_key_event(self, key_index, pressed, current_timestamp) -> None:
		logger.debug("Layer tracker: %s", self.layer_tracker)
		current_layer = self.layer_tracker[-1]
		action = self.keymap[current_layer][key_index]
		if pressed:
			if isinstance(action, CompositeAction):
				logger.debug("CompositeAction pending")
				self.undetermined_key_index = key_index
				self.undetermined_key_timestamp = current_timestamp
				self.undetermined_key_action = action
			elif isinstance(action, TapDance):
				if self.undetermined_key_index == key_index:
					self.undetermined_tap_dance_action_index += 1
					logger.debug("TapDance pending and index increased to %d", self.undetermined_tap_dance_action_index)
					if len(action) <= self.undetermined_tap_dance_action_index:
						logger.debug("TapDance limit reached, trigger last keycode")
						await self.trigger_key_action(key_index, pressed, action[-1])
						self.undetermined_key_index = -1
				else:
					logger.debug("TapDance pending, this is first tap")
					self.undetermined_key_index = key_index
					self.undetermined_key_action = action
					self.undetermined_tap_dance_action_index = 0
				self.undetermined_key_timestamp = current_timestamp
				self.undetermined_tap_dance_pressed = True
			else:
				logger.debug("trigger key %d's action directly", key_index)
				await self.trigger_key_action(key_index, pressed, action)
		else:
			logger.debug("releasing key %d", key_index)
			if self.undetermined_key_index == key_index:
				if isinstance(self.undetermined_key_action, CompositeAction):
					logger.debug("trigger CompositeAction")
					await self.process_undetermined_action(current_timestamp, pressed=pressed)
				if isinstance(self.undetermined_key_action, TapDance):
					logger.debug("TapDance released")
					self.undetermined_tap_dance_pressed = False
					await self.process_undetermined_action(current_timestamp, pressed=pressed)
			else:
				await self.trigger_key_action(key_index, pressed)

	async def process_undetermined_action(self, current_timestamp, *, new_press_index=-1, pressed=True) -> None:
		# this function maintain the following internal states:
		# - undetermined_key_index
		# - undetermined_key_layer
		if self.undetermined_key_index < 0:
			return  # no undetermined action
		action = self.undetermined_key_action
		time_delta = current_timestamp - self.undetermined_key_timestamp
		if isinstance(action, CompositeAction):
			if new_press_index >= 0:
				# it's determined by a new key press
				if (time_delta < action.tap_term_ms
						and action.tap is not None
						and action.tap_preferred):
					# trigger tap action if defined and preferred
					logger.debug("trigger CompositeAction tap")
					await self.trigger_key_action(self.undetermined_key_index, pressed, action.tap)
					self.undetermined_key_index = -1
				elif time_delta < action.hold_term_ms:
					# switch layer and activate layer+hold action if they are defined
					# trigger hold action if layer is not defined
					# layer change only happens HERE and it's on-demand
					# layer change will be triggered here if action.tap is not defined
					layer_action = LayerAction(action.layer, action.hold)
					logger.debug("trigger CompositeAction layer+hold")
					await self.trigger_key_action(self.undetermined_key_index, pressed, layer_action)
					self.undetermined_key_index = -1
				elif time_delta < action.long_hold_start_ms:
					# no action for this key
					logger.debug("no action for CompositeAction")
					self.undetermined_key_index = -1
				# long press action shouldn't be determined by a new key press
				# so not processed here
			else:
				# regularly check the time since key with composite action pressed
				if not pressed:
					# now key action determined by a release event
					if time_delta < action.tap_term_ms:
						# trigger tap action
						logger.debug("trigger CompositeAction tap")
						await self.trigger_key_action(self.undetermined_key_index, True, action.tap)
						await self.trigger_key_action(self.undetermined_key_index, False)
						self.undetermined_key_index = -1
					elif time_delta < action.hold_term_ms:
						# trigger hold action
						# no need to change layer, since no combo key
						logger.debug("trigger CompositeAction hold, no change layer")
						await self.trigger_key_action(self.undetermined_key_index, True, action.hold)
						await self.trigger_key_action(self.undetermined_key_index, False)
						self.undetermined_key_index = -1
					else:
						# simply no action
						logger.debug("no action for CompositeAction")
						self.undetermined_key_index = -1
				else:
					# check if (long) hold action should be triggered
					if (action.long_hold is None) and (time_delta > action.tap_term_ms):
						logger.debug("trigger Composite action hold+layer")
						layer_action = LayerAction(action.layer, action.hold)
						await self.trigger_key_action(self.undetermined_key_index, pressed, layer_action)
						self.undetermined_key_index = -1
					elif time_delta > action.long_hold_start_ms:
						# trigger long hold action
						logger.debug("trigger Composite action long hold")
						await self.trigger_key_action(self.undetermined_key_index, pressed, action.long_hold)
						self.undetermined_key_index = -1
		elif isinstance(action, TapDance):
			if (new_press_index >= 0) and (new_press_index != self.undetermined_key_index):
				# determined by new press
				logger.debug("trigger TapDance key #%d", self.undetermined_tap_dance_action_index)
				tap_dance_action = action[self.undetermined_tap_dance_action_index]
				if self.undetermined_tap_dance_pressed:
					# press down
					await self.trigger_key_action(self.undetermined_key_index, True, tap_dance_action)
				else:
					# click once
					await self.trigger_key_action(self.undetermined_key_index, True, tap_dance_action)
					await self.trigger_key_action(self.undetermined_key_index, False)
				self.undetermined_key_index = -1
			else:
				# check regularly if time since last press exceeds tap_term_ms
				if time_delta > action.tap_term_ms:
					logger.debug("trigger TapDance key #%d", self.undetermined_tap_dance_action_index)
					tap_dance_action = action[self.undetermined_tap_dance_action_index]
					# trigger action
					if self.undetermined_tap_dance_pressed:
						# press down
						await self.trigger_key_action(self.undetermined_key_index, True, tap_dance_action)
					else:
						# click once
						await self.trigger_key_action(self.undetermined_key_index, True, tap_dance_action)
						await self.trigger_key_action(self.undetermined_key_index, False)
					self.undetermined_key_index = -1
		else:
			logger.warning("Unknown undetermined action: `%s'", action)

	async def trigger_key_action(self, key_index, pressed, action=None) -> None:
		# the specific action is passed/selected by other part of the code
		# this function maintains the following internal states:
		# - key_actions
		# - layer_tracker
		# Note: here all actions are raw actions, among None, string, number, and callable
		if pressed:
			if isinstance(action, LayerAction):
				if action.layer is not None:
					logger.debug("Switching to layer: `%s'", action.layer)
					self.push_layer(action.layer)
				real_action = action.action
				await self.trigger_key_press_action(real_action)
				self.key_actions[key_index] = action
			else:
				self.key_actions[key_index] = await self.trigger_key_press_action(action)
		else:
			# use recorded action
			if action is None:
				action = self.key_actions[key_index]
			if isinstance(action, LayerAction):
				if action.layer is not None:
					logger.debug("Removing layer: `%s'", action.layer)
					self.pop_layer(action.layer)
				real_action = action.action
				await self.trigger_key_release_action(real_action)
				self.key_actions[key_index] = None
			else:
				self.key_actions[key_index] = await self.trigger_key_release_action(action)

	async def trigger_key_press_action(self, action) -> object:
		if callable(action):
			logger.debug("Triggering function call")
			self.release_and_clear_queue()
			# run the function
			try:
				result = action(self)
				# check if result is a coroutine, await it if so(it's an async function)
				if is_coroutine(result):
					result = await result
				logger.debug("Function call result: %s", result)
			except Exception as e:
				logger.error("Function call raised an exception: %s: %s", e.__class__.__name__, e)
			self.release_and_clear_queue()
			# we can no longer track key release events occured when executing the user funcion
			self.reset_layer_tracker()
			gc.collect()
			return None
		elif isinstance(action, str):
			logger.debug("Sending string: %s", action)
			self.release_all_hid()
			self.send_text(action)
			return None
		elif isinstance(action, ConsumerCode):
			logger.debug("Triggering consumer control keycode: %s", action)
			self.press_cc_key(action)
			return action
		elif isinstance(action, MouseCode):
			logger.debug("Trigger pressing mouse action: %s", action)
			self.press_mouse_key(int(action))
			return action
		elif isinstance(action, int):
			logger.debug("Triggering raw keycode: %s", action)
			self.press_kbd_key(action)
			return action
		elif isinstance(action, KeySequence):
			delay = Delay(action.delay)
			for act in action:
				await self.trigger_key_press_action(act)
				await self.trigger_key_release_action(act)
				await self.trigger_key_press_action(delay)
		elif isinstance(action, KeyCombination):
			for act in action:
				await self.trigger_key_press_action(act)
			delay = Delay(action.delay)
			await self.trigger_key_press_action(delay)
			for act in action:
				await self.trigger_key_release_action(act)
		elif isinstance(action, Delay):
			if action.delay > 0:
				await asyncio.sleep(action.delay)
		elif action is not None:
			logger.debug("Unhandled key press action: %s/%s", action.__class__.__name__, action)

	async def trigger_key_release_action(self, action) -> object:
		if isinstance(action, ConsumerCode):
			self.release_cc_key()
		elif isinstance(action, MouseCode):
			self.release_mouse_key(action)
		elif isinstance(action, int):
			self.release_kbd_key(action)
		elif action is not None:
			logger.debug("Unhandled key release action: %s/%s", action.__class__.__name__, action)
		return None

	@no_fail_tag('push_layer')
	def push_layer(self, layer):
		self.layer_tracker.append(layer)

	@no_fail_tag('pop_layer')
	def pop_layer(self, layer):
		# FIXME: this is not robust if multiple sequencial keys point to the same layer
		if len(self.layer_tracker) > 1:
			self.layer_tracker.remove(layer)

	def release_and_clear_queue(self) -> None:
		self.release_all_hid()
		self.clear_queue()

	@no_fail
	def release_all_hid(self) -> None:
		self.keyboard.release_all()
		self.consumer_control.release()
		self.mouse.release_all()

	def clear_queue(self) -> None:
		self.key_scanner.events.clear()

	def reset_layer_tracker(self) -> None:
		if self.layer_tracker is not None:
			self.layer_tracker.clear()
			self.layer_tracker.append(self.default_layer)

	@no_fail
	def press_kbd_key(self, *keycodes: int) -> None:
		# keycode may be eaten if USB has problem Ψ(╹◡╹)Ψ
		self.keyboard.press(*keycodes)

	@no_fail
	def release_kbd_key(self, *keycodes: int) -> None:
		self.keyboard.release(*keycodes)

	@no_fail
	def tap_kbd_key(self, keycode: int) -> None:
		self.keyboard.press(keycode)
		self.keyboard.release(keycode)

	@no_fail
	def press_cc_key(self, consumer_code: int) -> None:
		self.consumer_control.press(consumer_code)

	@no_fail
	def release_cc_key(self) -> None:
		# Consumer control can only be pressed one key at a time
		self.consumer_control.release()

	@no_fail
	def tap_cc_key(self, consumer_code: int) -> None:
		self.consumer_control.send(consumer_code)

	@no_fail
	def press_mouse_key(self, buttons: int) -> None:
		self.mouse.press(buttons)

	@no_fail
	def release_mouse_key(self, buttons: int) -> None:
		self.mouse.release(buttons)

	@no_fail
	def move_mouse(self, x: int = 0, y: int = 0, wheel: int = 0) -> None:
		self.mouse.move(x, y, wheel)

	# no blocking delay/timeout, as we are in async context

	def load_keyboard(self) -> bool:
		try:
			if self.keyboard is None:
				self.keyboard = Keyboard(usb_hid.devices)
				self.keyboard_layout = KeyboardLayoutUS(self.keyboard)
				logger.debug("Keyboard HID interface loaded")
			return True
		except OSError:
			logger.warning("USB not ready yet")
			self.keyboard = None
		except ValueError:
			logger.warning("Keyboard HID interface not found")
			self.keyboard = None
		return False

	def load_mouse(self) -> bool:
		try:
			if self.mouse is None:
				self.mouse = Mouse(usb_hid.devices)
				logger.debug("Mouse HID interface loaded")
			return True
		except OSError:
			logger.debug("USB not ready yet")
			self.mouse = None
		except ValueError:
			logger.debug("Mouse HID interface not found")
			self.mouse = None
		return False

	def load_consumer_control(self) -> bool:
		try:
			if self.consumer_control is None:
				self.consumer_control = ConsumerControl(usb_hid.devices)
				logger.debug("Consumer Control HID interface loaded")
			return True
		except OSError:
			logger.debug("USB not ready yet")
			self.consumer_control = None
		except ValueError:
			logger.debug("Consumer Control HID interface not found")
			self.consumer_control = None
		return False

	### APIs for custom functions ###

	@no_fail
	def send_text(self, text: str, delay: float = None):
		self.keyboard_layout.write(text, delay)

	def get_key_event(self):
		return self.key_scanner.events.get()

	def disable_watchdog(self):
		wdt.mode = None

	def enable_watchdog(self, timeout = WDT_TIMEOUT):
		wdt.timeout = max(timeout, WDT_TIMEOUT)
		try:
			# This is not supported on RP2040 yet (´；ω ；｀)
			# The hardware watchdog simply resets the MCU after a timeout.
			# Maximum timeout ~8 seconds on RP2040.
			wdt.mode = WatchDogMode.RAISE
		except NotImplementedError:
			wdt.mode = WatchDogMode.RESET
		wdt.feed()
