from __future__ import annotations

import asyncio
import copy
import os
import sys
import time
import traceback
from dataclasses import asdict

import yaml
from dotenv import load_dotenv
from strmdck.device import ButtonAction
from strmdck.device_manager import auto_connect
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .configuration import Configuration
from .elements import InteractionType, PageElement
from .enums import SleepStatus
from .event_bus import EventName, event_bus
from .home_assistant import HomeAssistantWebSocket
from .utils import deep_merge

load_dotenv()
HA_HOST = os.getenv('HA_HOST')
HA_ACCESS_TOKEN = os.getenv('HA_ACCESS_TOKEN')


class HomeDeck:
    class ConfigurationFileChangeHandler(FileSystemEventHandler):
        def __init__(self, deck: HomeDeck):
            self._deck = deck
            self._file_path = os.path.abspath('assets/configuration.yml')
            self._last_modified = 0

        def on_modified(self, event):
            if event.src_path == self._file_path:
                # Ignore events within 1 seconds
                now = time.time()
                if now - self._last_modified >= 1:
                    self._last_modified = now
                    self._deck._need_reload_all = True

        '''
        def on_created(self, event):
            if event.src_path == self._file_path:
                self._device.reload_all()

        def on_deleted(self, event):
            if event.src_path == self._file_path:
                raise ValueError('configuration.yml file deleted')
        '''

    def __init__(self, vendor_id: int = 0x2207, product_id: int = 0x0019):
        self._vendor_id = vendor_id
        self._product_id = product_id

        self._configuration_observer = None
        script_dir = os.path.dirname(os.path.realpath(__file__))
        with open(os.path.join(script_dir, 'yaml', 'configuration.base.yml'), 'r') as fp:
            self._base_configuration_dict = yaml.safe_load(fp.read())

    async def connect(self, retries: int = -1):
        await self._setup()

    def reload_all(self) -> bool:
        if not self._ha:
            return False

        self._need_reload_all = False

        try:
            with open(os.path.join('assets', 'configuration.yml'), 'r', encoding='utf-8') as fp:
                configuration_dict = yaml.safe_load(fp.read())
                configuration_dict = deep_merge(copy.deepcopy(self._base_configuration_dict), configuration_dict)

                new_configuration = Configuration(device=self._device, source_dict=configuration_dict, all_states=self._ha.all_states)

            if not new_configuration or not new_configuration.is_valid():
                # Crash app if the configuration file is invalid on startup
                if not self._configuration:
                    sys.exit(1)

                return

            # Check configuration changed
            print('✅ Configuration changed!')
            self._configuration = new_configuration
            self._wake_up()
        except Exception:
            traceback.print_exc()
            return False

        configuration = self._configuration
        # await self._write_packet(b'\x01')  # Not sure what this is for
        self._device.set_brightness(configuration.brightness)
        self._device.set_label_style(asdict(configuration.label_style))

        self.page_go_to('$root', 1, append_stack=True)
        return True

    async def call_ha_service(self, *, domain: str, service: str, service_data: dict):
        try:
            await self._ha.call_service(domain=domain, service=service, service_data=service_data)
        except Exception:
            pass

    def reload_current_page(self, *, force=False) -> bool:
        return self.reload_page(self._current_page_id, force=force)

    def force_reload_current_page(self) -> bool:
        return self.reload_page(self._current_page_id, force=True)

    def reload_page(self, page_id: str, *, force=False) -> bool:
        if not self._ha:
            return False

        is_sub_page = self._current_page_id != '$root'
        page = self._configuration.get_page_element(page_id)
        changed = page.render_buttons(system_buttons=self._configuration.system_buttons, page_number=self._current_page_number, is_sub_page=is_sub_page, buttons_per_page=self._device.BUTTON_COUNT, all_states=self._ha.all_states)

        # Don't render the same page
        if not force and self._current_page_element == page and not changed:
            return

        if force or self._current_page_element != page:
            # Update full page
            buttons = PageElement.generate(page.buttons)
            self._device.set_buttons(buttons)
        else:
            # Only update changed buttons
            buttons = PageElement.generate(page.changed_buttons)
            self._device.set_buttons(buttons, update_only=True)

        self._current_page_element = page
        return True

    async def _read_packets(self):
        button_index = None
        button_state = None

        is_holding = False
        hold_threshold = 0.5
        hold_timer = None

        press_index = -1
        press_time = 0

        def set_timeout(callback, delay):
            async def wrapper():
                await asyncio.sleep(delay)
                await callback()

            return asyncio.create_task(wrapper())

        async def hold_timer_callback():
            nonlocal is_holding, press_time, hold_timer

            current_time = time.time()
            diff_time = current_time - press_time
            if diff_time >= hold_threshold:
                is_holding = True
                hold_timer = None

                await self._on_interacted(InteractionType.HOLD, button_index, button_state)

        async for command in self._device.read_packet():
            if isinstance(command, ButtonAction):
                self._last_action_time = time.time()

                button_index = command.index
                button_state = command.state

                # Clear hold_timer
                if hold_timer:
                    hold_timer.cancel()
                    hold_timer = None

                sleep_config = self._configuration.sleep
                if sleep_config and self._sleep_status != SleepStatus.WAKE:
                    if self._sleep_status == SleepStatus.DIM:
                        self._wake_up()
                    elif self._sleep_status == SleepStatus.SLEEP:
                        # Only wake the device up on releasing button
                        if not is_holding and not command.pressed:
                            # Wake up first
                            self._wake_up()
                            # Reload small window
                            self._device.restore_small_window()
                            # Reload page
                            self.force_reload_current_page()

                        # Don't accept current action
                        is_holding = False
                        continue

                if command.pressed:
                    press_time = time.time()
                    is_holding = False

                    # Setup hold_timer
                    hold_timer = set_timeout(hold_timer_callback, hold_threshold)

                    if press_index != button_index:
                        press_index = button_index
                else:
                    if not is_holding:
                        await self._on_interacted(InteractionType.TAP, button_index, button_state)

                    is_holding = False

    async def _keep_alive(self):
        while True:
            if not self._is_ready:
                break

            await asyncio.sleep(1)
            # Keep alive
            self._device.keep_alive()

            # Update sleep status
            if self._sleep_status == SleepStatus.SLEEP or self._last_action_time <= 0:
                continue

            sleep_config = self._configuration.sleep
            if not sleep_config:
                continue

            diff = time.time() - self._last_action_time
            if sleep_config.sleep_timeout > 0 and diff > sleep_config.sleep_timeout:
                self._sleep()
            elif sleep_config.dim_timeout > 0 and self._sleep_status != SleepStatus.DIM and diff > sleep_config.dim_timeout:
                # Dim device
                self._sleep_status = SleepStatus.DIM
                self._device.set_brightness(sleep_config.dim_brightness)

    def _wake_up(self):
        if self._sleep_status != SleepStatus.WAKE:
            self._device.set_brightness(self._configuration.brightness)

        # Sleep device
        self._sleep_status = SleepStatus.WAKE
        self._last_action_time = time.time()

    def _sleep(self):
        # Sleep device
        self._device.set_brightness(0)
        self._sleep_status = SleepStatus.SLEEP
        self._last_action_time = time.time()

    async def _on_interacted(self, interaction: InteractionType, index: int, state: object):
        # Get button info for better logging
        button = self._configuration.get_button(self._current_page_id, index) if self._configuration else None
        button_name = button.name if button and hasattr(button, 'name') else 'Unknown'

        print(f'👆 Button pressed: Position={index}, Name="{button_name}", Action={interaction.value}, Page="{self._current_page_id}"')

        # Small window button
        if index == 13:
            if interaction == InteractionType.TAP:
                self._device.set_small_window_mode(state)
            elif interaction == InteractionType.HOLD:
                # Sleep
                self._sleep()
                # Restore to the previous mode
                self._device.restore_small_window()
            return

        if button:
            await button.trigger_action(self, interaction)

    def _reset(self):
        self._is_ready = False

        if hasattr(self, '_device') and self._device:
            self._device.close()
        self._device = None

        self._ha = HomeAssistantWebSocket(HA_HOST, HA_ACCESS_TOKEN)

        self._current_page_element = None
        self._pages_stack = []

        self._need_reload_all = True
        self._configuration = None

        self._sleep_status = SleepStatus.WAKE
        self._last_action_time = time.time()

        # Debounce timer for HA state changes
        self._ha_reload_timer = None

    async def _setup(self):
        # Setup event bus
        event_bus.subscribe(EventName.DECK_RELOAD, self.reload_current_page)
        event_bus.subscribe(EventName.DECK_FORCE_RELOAD, self.force_reload_current_page)

        reconnect_delay = 3
        while True:
            self._reset()

            try:
                # Setup device
                device = None
                while True:
                    try:
                        device = auto_connect()
                        if device:
                            self._device = device
                            print('Device connected')
                            break

                        print('Could not find any device')
                        await asyncio.sleep(reconnect_delay)
                    except Exception as e:
                        try:
                            device.close()
                        except Exception:
                            pass

                        print('Could not open the device:', e)
                        await asyncio.sleep(reconnect_delay)

                # Setup Home Assistant
                async with self._ha.connect():
                    await self._ha.get_all_states()
                    self._ha.on_event('state_changed', self._ha_on_state_changed)
                    await self._ha.subscribe_events('state_changed')

                    self._is_ready = True
                    await asyncio.gather(
                        self._ha.listen(),
                        self._read_packets(),
                        self._keep_alive(),
                        self._setup_hot_reload(),
                    )
            except Exception:
                traceback.print_exc()

                # Crash app if error on startup
                if not self._is_ready:
                    sys.exit(1)

                self._is_ready = False
            finally:
                try:
                    self._device.close()
                except Exception:
                    pass

                try:
                    await self._ha.disconnect()
                except Exception:
                    pass

                await asyncio.sleep(reconnect_delay)

    async def _ha_on_state_changed(self, _):
        # Only reload page when it's not sleeping
        if self._sleep_status != SleepStatus.SLEEP:
            # Cancel existing timer if any
            if self._ha_reload_timer:
                self._ha_reload_timer.cancel()

            # Create new debounced reload timer (100ms)
            async def debounced_reload():
                await asyncio.sleep(0.1)
                self._ha_reload_timer = None
                self.reload_current_page()

            self._ha_reload_timer = asyncio.create_task(debounced_reload())

    async def _setup_hot_reload(self):
        print('Setting up hot reload')

        if not self._configuration_observer:
            event_handler = self.ConfigurationFileChangeHandler(self)
            observer = Observer()
            observer.schedule(event_handler, path='./assets', recursive=False)

            observer.start()
            self._configuration_observer = observer

        while True:
            if self._need_reload_all:
                self.reload_all()

            await asyncio.sleep(1)

    def page_go_to(self, page_id: str, page_number: int = 1, append_stack=True):
        if not self._configuration.has_page(page_id):
            print('Invalid page:', page_id)
            return

        if append_stack:
            self._pages_stack.append((page_id, page_number))

        self._current_page_id = page_id
        self._current_page_number = page_number
        self.reload_current_page()

    def page_go_back(self):
        # Remove current page
        if self._pages_stack:
            self._pages_stack.pop()

        # Get last page
        target_page, page_number = self._pages_stack[-1] if self._pages_stack else ('$root', 1)
        print(target_page, page_number)
        self.page_go_to(target_page, page_number=page_number, append_stack=False)

    def page_go_previous(self):
        # Update page number in stack
        target_page, page_number = self._pages_stack[-1]
        page_number = max(1, self._current_page_number - 1)
        self._pages_stack[-1] = (target_page, page_number)

        self._current_page_number = page_number
        self.reload_current_page()

    def page_go_next(self):
        # Update page number in stack
        target_page, page_number = self._pages_stack[-1]
        page_number = self._current_page_number + 1
        self._pages_stack[-1] = (target_page, page_number)

        self._current_page_number = page_number
        self.reload_current_page()
