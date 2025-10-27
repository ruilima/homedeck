from __future__ import annotations

import json
import os
import shutil
from copy import deepcopy
from typing import Dict

from .dataclasses import (
    PageButtonActionConfig,
    PageButtonConfig,
    PageConfig,
    SystemButtonConfig,
)
from .enums import ButtonElementAction, InteractionType
from .icons import icon_provider
from .template import render_template
from .utils import deep_merge


def _fast_compare(obj1, obj2) -> bool:
    """Fast comparison using JSON serialization. Returns True if equal."""
    if obj1 is None and obj2 is None:
        return True
    if obj1 is None or obj2 is None:
        return False
    try:
        # Convert to JSON strings for fast comparison
        return json.dumps(obj1, sort_keys=True, default=str) == json.dumps(obj2, sort_keys=True, default=str)
    except (TypeError, ValueError):
        # Fallback to simple equality
        return obj1 == obj2


class ButtonElement:
    def __init__(self, button_config: PageButtonConfig):
        self._config: PageButtonConfig = button_config
        self._actions: Dict[InteractionType, PageButtonActionConfig] = {}

        if button_config.tap_action:
            self._actions[InteractionType.TAP] = button_config.tap_action

        if button_config.hold_action:
            self._actions[InteractionType.HOLD] = button_config.hold_action

        self._name = button_config.name

    @property
    def name(self):
        return self._config.name

    def get_icon(self):
        return icon_provider.get_icon(self._config)

    async def trigger_action(self, deck: 'HomeDeck', interaction: InteractionType) -> bool:  # type: ignore
        if interaction not in self._actions:
            return False

        main_action = self._actions[interaction]
        print('⚠️', interaction.value, main_action)

        action = main_action.action
        if action == ButtonElementAction.PAGE_BACK.value:
            deck.page_go_back()
        elif action == ButtonElementAction.PAGE_PREVIOUS.value:
            deck.page_go_previous()
        elif action == ButtonElementAction.PAGE_NEXT.value:
            deck.page_go_next()
        elif action == ButtonElementAction.PAGE_GO_TO.value:
            deck.page_go_to(main_action.data)
        else:
            domain, action = action.split('.')
            await deck.call_ha_service(domain=domain, service=action, service_data=main_action.data)
        return True


class PageElement:
    def __init__(self, page_config: PageConfig):
        self._page_config = page_config
        self._button_elements: Dict[ButtonElement] = {}
        self._button_raws = {}
        self._changed_button_elements = {}

    @property
    def buttons(self) -> Dict[int, ButtonElement]:
        return self._button_elements

    @property
    def changed_buttons(self) -> Dict[int, ButtonElement]:
        return self._changed_button_elements

    @property
    def page_config(self):
        return self._page_config

    @property
    def button_raws(self):
        return self._button_raws

    def _to_button_element(self, button):
        button_element = None
        if button:
            button_config = PageButtonConfig(**deepcopy(button))
            button_element = ButtonElement(button_config)

        return button_element

    def _shift_index_right(self, buttons: dict, start_index: int):
        return {k + (1 if k >= start_index else 0): v for k, v in buttons.items()}

    def _insert_button_at(self, button: dict, index: int):
        # Shift buttons
        self._button_raws = self._shift_index_right(self._button_raws, index)
        self._button_elements = self._shift_index_right(self._button_elements, index)

        self._button_raws[index] = button
        self._button_elements[index] = self._to_button_element(button)

    def render_buttons(self, *, system_buttons: Dict[ButtonElementAction, SystemButtonConfig], page_number: int = 1, is_sub_page: bool = False, buttons_per_page=0, all_states=dict) -> bool:
        old_raws = self._button_raws
        new_raws = {}
        self._button_elements = {}

        total_skipped = 0
        for index, button in enumerate(deepcopy(self._page_config.buttons_raw)):
            if not button:
                new_raws[index] = None
                continue

            # Get entity_id for self_*() mixins
            entity_id = None
            if 'entity_id' in button:
                entity_id = button['entity_id']
                states = all_states.get(entity_id)
                if states:
                    if 'icon' not in button:
                        # Use icon in states
                        icon = states.get('attributes', {}).get('icon')
                        if icon:
                            button['icon'] = icon

                    # Apply presets based on state
                    state = states.get('state')
                    if state and 'states' in button and state in button['states']:
                        button = deep_merge(button, button['states'][state])

                    # Get default name
                    if 'name' not in button:
                        button['name'] = states.get('attributes', {}).get('friendly_name')

            # Render templates
            if button.get('is_dynamic'):
                button = render_template(button, entity_id=entity_id, all_states=all_states)

            # Check visibility
            visibility = button.get('visibility', True)
            is_hidden = visibility is False or visibility == 'False' or visibility == 'hidden'
            is_gone = visibility is None or visibility == 'None' or visibility == 'gone'

            if is_hidden:
                # Hide button
                button = None
            if is_gone:
                # Skip button
                total_skipped += 1
                continue

            # Save button element
            real_index = index - total_skipped
            new_raws[real_index] = button
            self._button_elements[real_index] = self._to_button_element(button)

        # Save current buttons
        self._button_raws = new_raws

        start = 0
        tmp_page_number = 1
        while start < len(new_raws):
            if is_sub_page and tmp_page_number == 1:
                # Insert Back button for page #1
                back_button = system_buttons[ButtonElementAction.PAGE_BACK]
                if back_button.position > 0:
                    self._insert_button_at(back_button.button, start + (back_button.position - 1))

            if tmp_page_number > 1:
                previous_button = system_buttons[ButtonElementAction.PAGE_PREVIOUS]
                if previous_button.position > 0:
                    self._insert_button_at(previous_button.button, start + (previous_button.position - 1))

            if start + buttons_per_page < len(new_raws):
                next_button = system_buttons[ButtonElementAction.PAGE_NEXT]
                self._insert_button_at(next_button.button, start + (next_button.position - 1))

            new_raws = self._button_raws
            start += buttons_per_page
            tmp_page_number += 1

        # self._insert_button_at(system_buttons[ButtonElementAction.PAGE_NEXT], 12)
        # new_raws = self._button_raws
        buttons_range = range((page_number - 1) * buttons_per_page, page_number * buttons_per_page)

        # Find changed buttons
        self._changed_button_elements = {}
        for index in range(buttons_per_page):
            old_button = old_raws.get(index)
            new_button = new_raws.get(index + (page_number - 1) * buttons_per_page)

            # Fast comparison - if equal, no change
            if _fast_compare(old_button, new_button):
                continue

            # Set changed button
            self._changed_button_elements[index] = self._to_button_element(new_button)

        # Limit number of buttons
        self._button_elements = {(index % buttons_per_page): value for index, value in self._button_elements.items() if index in buttons_range}
        self._button_raws = {(index % buttons_per_page): value for index, value in self._button_raws.items() if index in buttons_range}

        return bool(self._changed_button_elements)

    def get_button_at(self, button_index: int) -> ButtonElement:
        return self._button_elements.get(button_index)

    def __eq__(self, other: PageElement):
        # Compare configs and buttons_raw
        if not other or self._page_config != other.page_config:
            return False

        # Fast comparison of button_raws
        return _fast_compare(self.button_raws, other.button_raws)

    @staticmethod
    def generate(buttons: Dict[int, ButtonElement]):
        output = {}

        for index, button in buttons.items():
            if not button:
                output[index] = None
                continue

            output[index] = {}
            if button.name and len(button.name) > 0:
                output[index]['name'] = button.name.strip()

            icon = button.get_icon()
            icon_name = icon.generated_filename()
            icon_path = os.path.join('.cache', 'icons', '_generated', icon_name)
            if os.path.exists(icon_path):
                # Copy icon
                icons_build_path = os.path.join('.build', 'page', 'icons')
                os.makedirs(icons_build_path, exist_ok=True)
                shutil.copyfile(icon_path, os.path.join(icons_build_path, icon_name))
                output[index]['icon'] = icon_name

        print('page', output)
        return output
