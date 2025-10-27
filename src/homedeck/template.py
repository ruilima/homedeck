import functools as ft
import traceback
from functools import lru_cache
from typing import Union

import jinja2

env = jinja2.Environment()


@lru_cache(maxsize=256)
def _compile_template(template_string: str):
    """Cache compiled Jinja2 templates to avoid recompilation."""
    return env.from_string(template_string)


def _to_float(s: str) -> Union[float, bool]:
    try:
        return float(s)
    except ValueError:
        return False


def _to_int(s: str) -> Union[int, bool]:
    try:
        return int(s)
    except ValueError:
        return False


def _auto_cast(s: str, *, rounded: bool = False) -> Union[int, float, str]:
    if not isinstance(s, str):
        return s

    if s == 'true':
        return True
    elif s == 'false':
        return False

    num = _to_int(s)
    if num is False:
        num = _to_float(s)

    if num is not False:
        return rounded(num) if rounded else num

    return s


def _states(entity_id: str, *, with_unit: bool = False, rounded: bool = False, all_states: Union[dict, None] = None):
    assert all_states is not None

    entity_state = all_states.get(entity_id, {})
    if not entity_state:
        return None

    state = entity_state['state']
    if state == 'unavailable':
        return ''

    state = _auto_cast(state, rounded=rounded)
    if with_unit:
        unit = entity_state.get('attributes', {}).get('unit_of_measurement')
        if unit:
            state = f'{state} {unit}'

    return state


def _self_states(*, with_unit: bool = False, rounded: bool = False, entity_id: str, all_states: Union[dict, None] = None):
    return _states(with_unit=with_unit, rounded=rounded, entity_id=entity_id, all_states=all_states)


def _state_attr(entity_id: str, attr: str, all_states: dict):
    attrs = all_states.get(entity_id, {}).get('attributes', {})
    state_attr = attrs.get(attr)

    return _auto_cast(state_attr)


def _self_state_attr(attr: str, entity_id: str, all_states: dict):
    return _state_attr(entity_id, attr, all_states=all_states)


def _is_state(entity_id: str, state: str, all_states: dict) -> bool:
    return _states(entity_id, all_states=all_states) == _auto_cast(state)


def _self_is_state(state: str, entity_id: str, all_states: dict) -> bool:
    return _is_state(entity_id, state, all_states)


def _binary_text(entity_id: str, on_text: str, off_text: str, all_states: dict) -> bool:
    is_on = _is_state(entity_id, 'on', all_states)
    return on_text if is_on else off_text


def _self_binary_text(on_text: str, off_text: str, entity_id: str, all_states: dict) -> bool:
    return _binary_text(entity_id, on_text, off_text, all_states)


def render_template(source, all_states: dict, entity_id=None):
    if isinstance(source, dict):
        return {k: render_template(v, all_states, entity_id=entity_id) for k, v in source.items()}
    elif isinstance(source, list):
        return [render_template(v, all_states, entity_id=entity_id) for v in source]
    elif isinstance(source, str):
        try:
            # Use cached compiled template
            template = _compile_template(source)
            return template.render(
                state_attr=ft.partial(_state_attr, all_states=all_states),
                is_state=ft.partial(_is_state, all_states=all_states),
                states=ft.partial(_states, all_states=all_states),
                binary_text=ft.partial(_binary_text, all_states=all_states),

                self_state_attr=ft.partial(_self_state_attr, entity_id=entity_id, all_states=all_states),
                self_is_state=ft.partial(_self_is_state, entity_id=entity_id, all_states=all_states),
                self_states=ft.partial(_self_states, entity_id=entity_id, all_states=all_states),
                self_binary_text=ft.partial(_self_binary_text, entity_id=entity_id, all_states=all_states),
            ).strip()
        except Exception:
            print('⚠️', source)
            traceback.print_exc()
            return '#BUG'

    return source


def has_jinja_template(d: dict):
    if isinstance(d, dict):
        return any(has_jinja_template(v) for v in d.values())
    elif isinstance(d, list):
        return any(has_jinja_template(v) for v in d)
    elif isinstance(d, str):
        return '{{' in d or '{%' in d or '{#' in d

    return False
