# HomeDeck

A lightweight Python library to control Home Assistant using Stream Deck-like devices. It's designed to run on a less powerful Linux SBC (like Raspberry Pi Zero 2W, OrangePi Zero 2W...) with a deck connected so you can put it anywhere in the house.

## Quick Start (Systemd Service)

For automatic installation on Raspberry Pi / Orange Pi:

```bash
# 1. Clone the repository
git clone https://github.com/ruilima/homedeck.git
cd homedeck

# 2. Run diagnostics to check your system
sudo ./diagnose.sh

# 3. Configure your deck layout
cp assets/configuration.yml.example assets/configuration.yml
nano assets/configuration.yml

# 4. Install and start the service (will guide you through configuration)
sudo ./install-service.sh
```

The installer will guide you through:
- ✅ Environment variable configuration (HA_HOST, HA_ACCESS_TOKEN)
- ✅ Virtual environment setup (Python 3.12+ compatible)
- ✅ Secure credential storage in `/etc/homedeck/homedeck.env`
- ✅ Automatic service installation and startup

**Configuration:** Environment variables are stored securely in `/etc/homedeck/homedeck.env` (readable only by root). See [ENVIRONMENT.md](ENVIRONMENT.md) for details.

**View logs:** `sudo journalctl -u homedeck.service -f`

**Edit configuration:** `sudo nano /etc/homedeck/homedeck.env` then `sudo systemctl restart homedeck.service`

See [SYSTEMD_INSTALL.md](SYSTEMD_INSTALL.md) for detailed installation guide and troubleshooting.

### Features
- ✅ Easy to use, syntax is similar to Home Assistant and CSS
- 🛠️ Highly customizable with YAML configuration
- 📝 Template support for advanced customization
- 🧩 [Home Assistant Add-on support](https://github.com/redphx/homedeck-home-assistant-addon)

### Supported decks

| Name  | Features | Price | Where to buy |
|-------|----------|-------|--------------|
| [Ulanzi D200](https://www.ulanzi.com/products/stream-controller-d200) | 13 physical buttons, 1 info window | ~$55 | [Aliexpress](https://www.aliexpress.com/item/1005007809064199.html), [Tmall](https://detail.tmall.com/item.htm?id=835654847615)  |

### Other hardwares

| SBC   | Price | Where to buy |
|-------|-------|--------------|
| Orange Pi Zero 2W 1GB (or more) | ~$16 | [Aliexpress](https://www.aliexpress.com/item/1005006016211902.html), [Taobao](https://item.taobao.com/item.htm?id=739803125913) |
| Raspberry Pi 2W |  |  |

**SD Card:** minimum 8GB

### Configuration

1. Rename a `.env.example` to `.env` and follow the instructions in the file.
2. Rename a `assets/configuration.yml.example` to `assets/configuration.yml` and start editing.

> [!IMPORTANT]  
> Check [`configuration.base.yml`](/redphx/homedeck/blob/main/src/homedeck/yaml/configuration.base.yml) for the base configuration. You can override any of them if you want in your own configuration file.  
> Check [`configuration.yml.example`](/redphx/homedeck/blob/main/assets/configuration.yml.example) for working examples.


| Property          | Description | Default   | Type |
|:------------------|:------------|:----------|:-----|
| `brightness`      | The default brightness level of the buttons | 80 | `int` (1-100) |
| `sleep`           | Sleep mode configuration when inactive | | `Sleep` |
| `label_style`     | Label's style | | `LabelStyle` |
| `system_buttons`  | Setup the position of system buttons (back, previous, next) | | `Dict[String, SystemButton]` |
| `presets`         | Preset definitions | | `Dict[String, Preset]` |
| `pages`           | Define deck's layout | | `Dict[String, Page]` |

#### `Sleep`

| Property          | Description | Default   | Type |
|:------------------|:------------|:----------|:-----|
| `dim_brightness`  | Brightness when dimming | 10 | `int` (0-100) |
| `dim_timeout`     | Start dimming after X second(s) | 30 | `int` (>= 1) |
| `sleep_timeout`   | Start dimming after X second(s) | 300 | `int` (>= 1) |

#### `LabelStyle`

| Property      | Description | Default   | Type |
|:--------------|:------------|:----------|:-----|
| `align`       | Label's position | bottom | top/center/bottom |
| `color`       | Label's color | FFFFFF | `Color` |
| `font`        | Font's ID | 8 | `Font` (1-8) |
| `show_title`  | Show label or not | true | `bool` |
| `size`        | Font's size | 9 | `int` |
| `weight`      | Font's weight | 80 | `int` (unused?) |

#### `Preset`

A set of `Button`'s  properties so you can reuse them as many times as you want.  
Example:
```yaml
presets:
  red_button:
    icon_background_color: FF0000
  green_text:
    text_color: 00FF00
    text_size: 20

# Later
pages:
  $root:
    buttons:
      # This button will have a red background and green text
      - name: Red button
        presets:
          - red_button
          - green_text
        icon: mdi:sofa
        text: Couch
```

#### `Font`

Value from 1 to 8.

- 1: Source Han Sans SC
- 2: FZShuSong-Z01
- 3: DejaVu Sans
- 4: Bareona
- 5: Crimson Text
- 6: Magiera
- 7: Syke
- 8: Roboto


#### `Color`

Hex color, can be either string or number (must be 6 characters long)

Examples

```yaml
FFFFFF
123456
```

For colors that start with number `0`, you must add quotes around it. Or you can add a `/` symbol at the beginning.

Examples:
```yaml
# Invalid
012ABC
# Valid
"012ABC"
/012ABC
# Also valid
/FF0000
```


#### `SystemButton`

Example
```yaml
system_buttons:
  $page.back:
    position: 1
    button:
      presets: $page
      tap_action:
        action: $page.back
      icon: mdi:arrow-up-left
  $page.previous:
    position: 2
    #...
  $page.next:
    position: 3
    # ..
```

Available buttons:
- $page.back
- $page.previous
- $page.next

| Property      | Description | Default   | Type |
|:--------------|:------------|:----------|:-----|
| `position`    | Position of the button | | `Optional[int]` |
| `button`      | Style of the button | | `Optional[Button]` |

#### `Page`

Example:
```yml
pages:
  $root:
    buttons:
      - name: Living Room
        presets: room
        tap_action:
          action: $page.go_to
          data: living-room
        icon: mdi:sofa-outline
        icon_background_color: b9003e
  living-room:
    buttons:
      ...
```

Each button can take the following configuration

| Property      | Description | Default   | Type |
|:--------------|:------------|:----------|:-----|
| `position`    | Position of the button, starting with 1 | | `Optional[int]` |
| `button`      | Style of the button | | `Button` |


#### `Button`

Define content of the button

> All properties are optional

| Property      | Description | Default   | Type | Template support |
|:--------------|:------------|:----------|:-----|:-----------------|
| `presets`     | Preset name or a list of preset names | | - `Preset`<br>- `List[Preset]` | ❌ |
| `entity_id`   | Device's `entity_id` in HA | | `str` | ❌ |
| `domain`      | Device's `domain` in HA. Leave empty = automatically detect from `entity_id` | | `str` | ❌ |
| `name`        | Button's label | | `str` | ✅ |
| `tap_action`  | Action when pressing the button | `null` | - `ButtonAction`<br>- `null` (do nothing) |  |
| `hold_action` | Action when holding the button for `0.5s` | `null` | - `ButtonAction`<br>- `null` (do nothing) |  |
| `visibility`  | Controls button's visibility | `true` | - `true`/`visible`: show button's content<br>- `false`/`hidden`: show an empty button<br>- `null`/`gone`: not showing the button at all (skip it) | ✅ |
| `states`      | Overrides for the button appearance per entity state | | `ButtonState` | ❌ |
| `icon`<br>`icon_variant`<br>`icon_size`<br>`icon_padding`<br>`icon_offset`<br>`icon_border_radius`<br>`icon_border_width`<br>`icon_border_color`<br>`icon_brightness`<br>`icon_color`<br>`icon_background_color`<br>`icon_size_mode`<br>`z_index` | Icon's properties | | `ButtonIcon` |  |
| `text`<br>`text_color`<br>`text_align`<br>`text_font`<br>`text_size`<br>`text_offset`<br>`z_index`<br> | Text icon's properties | | `ButtonTextIcon` |  |
| `additional_icons` | List of additional icon layers | [] | `List[ButtonIcon \| ButtonTextIcon]` | ❌ |
| `states`      | Overrides for the button appearance per entity state | | `ButtonState` |  |

#### `ButtonAction`

For `tap_action` and `hold_action` properties.
Defines what happens when a button is pressed or held.

| Property      | Description | Type | Template support |
|:--------------|:------------|:-----|:-----------------|
| `action`      | Home Assistant's action/service name or one of HomeDeck's actions:<br>- `$page.go_to`<br>- `$page.back`<br>- `$page.previous`<br>- `$page.next` | `str` | ❌ |
| `data`        | Action's data, either string or object | `Optional[str \| dict]` | ❌ |

How to go to a different page (`living-room` in this example):
```yaml
tap_action:
  action: $page.go_to
  data: living-room
```

#### Icons

1. `ButtonIcon`

| Property      | Description | Default   | Type | Template support |
|:--------------|:------------|:----------|:-----|:-----------------|
| `icon`        | - `none`: no icon<br>- `local:<path>`: path to the local icon file. It can be either an absolute path (e.g. `local:/icons/test.png`) or a relative path to the `assets/icons` folder (e.g. `local:test.png`)<br>- `url:<url>`: URL to the external image<br>- `mdi:<icon>`: icon from [Material Design Icons](https://pictogrammers.com/library/mdi/), e.g. `mdi:lightbulb`<br>- `pi:<icon>`: icon from [Phosphor Icons](https://phosphoricons.com), e.g. `pi:lightbulb`  | `none` | `str` | ✅ |
| `icon_variant` | Icon's variant. Only available when using [Phosphor Icons](https://phosphoricons.com). | `regular` | - `thin`<br>- `light`<br>- `regular`<br>- `bold`<br>- `fill`<br>- `duotone` | ✅ |
| `icon_size`   | Icon's size, in pixel<br>-`<width> <height>`: set width and height, e.g. `icon_size: 100 120` <br>- `<size>`: set both width and height to the same value, e.g. `icon_size: 100` is the same as `icon_size: 100 100`<br>- When width or height is `0`, its value will be calculated based on the image's ratio | `0` | `int`<br>`str` | ✅ |
| `icon_padding` | Padding around the icon | `0` | `int` | ✅ |
| `icon_offset` | X/Y offset position of the icon relative to the original position | | `Offset` | ✅ |
| `icon_border_radius` | Radius for rounding the icon corners | `0` | `int` | ✅ |
| `icon_border_width` | Width of the icon border | `0` | `int` | ✅ |
| `icon_border_color` | Color of the icon border | `FFFFFF` | `Color` | ✅ |
| `icon_brightness`   | Brightness adjustment for the icon | `100` | `int` | ✅ |
| `icon_color`        | Main color of the icon | `FFFFFF` | `Color` | ✅ |
| `icon_background_color` | Background color behind the icon | `null` | `Color` | ✅ |
| `icon_size_mode`    | How the icon fits inside its designated space | `cover` | - `cover`<br>- `contain`<br>- `stretch` | ✅ |
| `z_index`     | Similar to [CSS `z-index`](https://developer.mozilla.org/en-US/docs/Web/CSS/z-index). Rendering order: Highest -> lowest. | 0 | `int` | ✅ |

2. `ButtonTextIcon`

| Property      | Description | Default   | Type | Template support |
|:--------------|:------------|:----------|:-----|:-----------------|
| `text`        | Text to display | | `str` | ✅ |
| `text_color`  | Text's color | | `Color` | ✅ |
| `text_align`  | Vertical alignment of the text | `center` | `top`<br>`center`<br>`bottom` | ✅ |
| `text_font`   | Text's font. It's the name of the TTF font (without `.ttf` extension) inside the `assets/fonts` folder. | | `str` | ✅ |
| `text_size`   | Font size of the text | | `int` | ✅ |
| `text_offset` | X/Y offset position of the text relative to the original position | | `Offset` | ✅ |
| `z_index`     | Similar to [CSS `z-index`](https://developer.mozilla.org/en-US/docs/Web/CSS/z-index). Rendering order: Highest -> lowest. | 0 | `int` | ✅ |

#### `ButtonState`

Overrides for the button appearance per entity state. It can override every properties in the `Button` type, except for `states`

Example:
```yaml
buttons:
  - entity_id: light.living_room_light
    name: 'Off'
    icon: mdi:lightbulb-outline
    states:
      'on':
        name: 'On'
        icon: mdi:lightbulb
```

It's the same as using this template

```yaml
buttons:
  - entity_id: light.living_room_light
    name: "{{ self_binary_text('On', 'Off') }}"
    icon: "{{ self_binary_text('mdi:lightbulb', 'mdi:lightbulb-outline') }}"
```

#### Supported template functions

| Function      | Description |
|:--------------|:------------|
| `states(entity_id)` | Get state of an entity |
| `state_attr(entity_id, attribute)` | Get attribute value of an entity |
| `is_state(entity_id, state)` | Check whether current state of an entity is `state` or not |
| `binary_text(entity_id, on_text, off_text)` | Return `on_text` when state is `on`, and `off_text` when state is `off` |

If the current button has a `entity_id` property, you can use `self_<function>` to skip passing `entity_id` to the function altogether.

Example:
```yaml
buttons:
  - entity_id: light.living_room_light
    name: {{ self_states() }}
```
is the same as
```yaml
buttons:
  - name: {{ states("light.living_room_light") }}
```


### TODO
- Docker container
- Support `spotify:` icon
- Support `ring:` icon
- Support other decks:
    - [ ] MiraBox
    - [ ] Elgato Stream Deck
