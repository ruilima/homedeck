import asyncio
import logging
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import fields
from typing import Dict, List, Tuple, Union

import cairosvg
import httpx
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from .dataclasses import ICON_FIELDS, TEXT_ICON_FIELDS, PageButtonConfig
from .enums import IconSource, MaterialYouScheme, PhosphorIconVariant
from .event_bus import EventName, event_bus
from .utils import (
    generate_material_you_palette,
    hex_to_rgb,
    normalize_hex_color,
    normalize_tuple,
    optimize_image,
)

logging.basicConfig(level=logging.INFO)

ENV_ENABLE_CACHE = int(os.getenv('ENABLE_CACHE', 1)) != 0
CACHE_ICONS_DIR = os.path.join('.cache', 'icons')
CACHE_GENERATED_DIR = os.path.join(CACHE_ICONS_DIR, '_generated')
# Keep generated icons cache to improve performance on restart
# Cache is automatically updated when icon configuration changes


class Icon:
    def __init__(self, max_width: int, max_height: int, layers: List[Dict]):
        icon_img = Image.new('RGBA', (max_width, max_height), (0, 0, 0, 0))

        # Sort layers by "z_index"
        layers = sorted(layers, key=lambda val: (val.get('z_index', 0)), reverse=False)

        self._icon_layers: List[IconLayer] = []
        for layer in layers:
            if not layer:
                continue

            layer['max_width'] = max_width
            layer['max_height'] = max_height

            # Material You
            material_you_palette = None
            material_you_color = normalize_hex_color(layer.get('material_you_color'))
            if material_you_color:
                material_you_palette = generate_material_you_palette(layer.get('material_you_scheme'), material_you_color)

            self._normalize_icon(layer, material_you_palette=material_you_palette)

            icon = None
            icon_source = layer['icon_source']
            if icon_source == IconSource.MATERIAL_DESIGN:
                icon = MaterialDesignIconLayer(layer)
            elif icon_source == IconSource.PHOSPHOR:
                icon = PhosphorIconLayer(layer)
            elif icon_source == IconSource.TEXT:
                icon = TextIconLayer(layer)
            elif icon_source == IconSource.URL:
                icon = UrlIconLayer(layer)
            elif icon_source == IconSource.BLANK:
                icon = LocalIconLayer(layer, file_path=None)
            elif icon_source == IconSource.LOCAL:
                file_path = layer['icon_name']
                layer['icon_name'] = os.path.basename(file_path)
                icon = LocalIconLayer(layer, file_path=file_path)

            if not icon:
                continue

            if isinstance(icon, RemoteIconLayer) and icon.is_available():
                icon = LocalIconLayer(layer, icon.original_file_path)

            self._icon_layers.append(icon)

        os.makedirs(CACHE_GENERATED_DIR, exist_ok=True)
        self._generated_path = os.path.join(CACHE_GENERATED_DIR, self.generated_filename())

        if not os.path.exists(self._generated_path):
            for icon in self._icon_layers:
                layer_img = icon.get_image()
                if layer_img:
                    icon_img.paste(layer_img, (0, 0), layer_img)

            # Save image
            icon_img.save(self._generated_path, 'PNG')

            # Optimize image
            optimize_image(self._generated_path, optimize_level=5)

    def _normalize_icon(self, icon: dict, material_you_palette=None):
        icon['icon_source'] = IconSource.BLANK
        if icon.get('icon'):
            # Set `icon_name` from `icon`
            try:
                source, name = icon['icon'].split(':', 1)
                icon['icon_name'] = name
                icon['icon_source'] = IconSource(source)
            except Exception:
                icon['icon_source'] = IconSource.BLANK
        elif icon.get('text'):
            icon['icon_source'] = IconSource.TEXT
            icon['icon_name'] = ''

            icon.setdefault('text_align', 'center')
            icon.setdefault('text_font', 'Roboto-SemiBold')
            icon.setdefault('text_size', 20)
            icon.setdefault('text_offset', (0, 0))

            if material_you_palette:
                icon.setdefault('text_color', 'on-primary-container')
                if icon['text_color'] in material_you_palette:
                    icon['text_color'] = material_you_palette[icon['text_color']]
            else:
                icon.setdefault('text_color', 'FFFFFF')

            icon['text_offset'] = normalize_tuple(icon['text_offset'])
            icon['text_color'] = normalize_hex_color(icon['text_color'])

        icon.setdefault('icon_source', IconSource.BLANK)

        # Set default properties
        if icon['icon_source'] != IconSource.TEXT:
            icon.setdefault('icon_variant', None)
            icon.setdefault('icon_padding', 0)
            icon.setdefault('icon_offset', (0, 0))
            icon.setdefault('icon_border_radius', 0)
            icon.setdefault('icon_border_width', 0)
            icon.setdefault('icon_brightness', None)

            icon.setdefault('icon_color', 'FFFFFF')
            icon.setdefault('icon_background_color', None)
            icon.setdefault('icon_border_color', None)

            if material_you_palette:
                if icon['icon_color'] in material_you_palette:
                    icon['icon_color'] = material_you_palette[icon['icon_color']]

                if icon['icon_background_color'] in material_you_palette:
                    icon['icon_background_color'] = material_you_palette[icon['icon_background_color']]

                if icon['icon_border_color'] in material_you_palette:
                    icon['icon_border_color'] = material_you_palette[icon['icon_border_color']]

            icon['icon_color'] = normalize_hex_color(icon['icon_color'])
            icon['icon_background_color'] = normalize_hex_color(icon['icon_background_color'])
            icon['icon_border_color'] = normalize_hex_color(icon['icon_border_color'] or icon['icon_color'] or icon['icon_background_color'] or 'FFFFFF')

            icon.setdefault('icon_size', (icon['max_width'], icon['max_height']))
            icon['icon_size'] = normalize_tuple(icon['icon_size'])
            if icon['icon_size'][0] == 0:
                icon['icon_size'] = (icon['max_width'], icon['icon_size'][1])
            if icon['icon_size'][1] == 0:
                icon['icon_size'] = (icon['icon_size'][0], icon['max_height'])

            icon['icon_offset'] = normalize_tuple(icon['icon_offset'])

    def generated_filename(self):
        return f'test-{hash(tuple(self._icon_layers))}.png'


class IconLayer(ABC):
    def __init__(self, icon: dict, file_path: str = None):
        self._is_generated = False
        self._icon = icon
        self._hash = None

        # Set default name
        if not hasattr(self, '_name'):
            self._name = icon.get('icon_name', '')

        self._original_file_path = file_path
        if file_path:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

        os.makedirs(CACHE_GENERATED_DIR, exist_ok=True)
        self._generated_path = os.path.join(CACHE_GENERATED_DIR, self.generated_filename())

    def is_available(self) -> bool:
        # Blank icon
        if self._original_file_path is None:
            return True

        return os.path.exists(self._original_file_path)

    def __hash__(self):
        if not self._hash:
            icon_fields = list(self._icon.keys())
            sorted_fields = {key: self._icon[key] for key in icon_fields}
            joined = '-'.join([f'{key}{str(value).upper()}' for key, value in sorted_fields.items()])
            self._hash = hash('-'.join([self._icon['icon_source'].value, self._name, joined]))

        return self._hash * (1 if self.is_available() else -1)

    def generated_filename(self) -> str:
        return f'{self._icon["icon_source"].value}-{self._name}-{self.__hash__()}.png'

    @property
    def original_file_path(self):
        return self._original_file_path

    @property
    def id(self):
        return self.__hash__()

    def get_image(self):
        if self._is_generated or ENV_ENABLE_CACHE and os.path.exists(self._generated_path):
            try:
                return Image.open(self._generated_path).convert('RGBA')
            except Exception:
                return None

        self._is_generated = True
        return self.rasterize()

    @abstractmethod
    def rasterize(self):
        pass


class TextIconLayer(IconLayer):
    def is_available(self):
        return True

    def rasterize(self):
        icon_styles = self._icon

        img = Image.new('RGBA', (icon_styles['max_width'], icon_styles['max_height']), (0, 0, 0, 0))
        img = IconEditor.draw_texts(img, text=icon_styles['text'], color=icon_styles['text_color'], align=icon_styles['text_align'], font=icon_styles['text_font'], size=icon_styles['text_size'], offset=icon_styles['text_offset'])

        # Save image
        img.save(self._generated_path, 'PNG')

        # Optimize image
        optimize_image(self._generated_path, optimize_level=5)

        return img


class LocalIconLayer(IconLayer):
    def __init__(self, icon: dict, file_path: str = None):
        super().__init__(icon, file_path=file_path)

    def rasterize(self):
        icon_styles = self._icon
        icon_width, icon_height = icon_styles['icon_size']

        button_width = icon_styles['max_width']
        button_height = icon_styles['max_height']

        if self._original_file_path:
            # SVG to PNG
            is_svg = self._original_file_path.endswith('svg')
            if is_svg:
                tmp_file = os.path.join(CACHE_ICONS_DIR, f'.tmp-{self.generated_filename()}')
                cairosvg.svg2png(url=self._original_file_path, write_to=tmp_file, output_width=icon_width, output_height=icon_height)
                img = Image.open(tmp_file)
                os.remove(tmp_file)

                # Apply color overlay
                img = IconEditor.apply_color(img, icon_styles['icon_color'])
            else:
                img = Image.open(self.original_file_path).convert('RGBA')
                img = IconEditor.resize(img, icon_styles['icon_size_mode'], icon_styles['icon_size'])
        else:
            # Blank icon
            img = Image.new('RGBA', (icon_width, icon_height), 0)

        # Apply icon's padding
        img = IconEditor.apply_padding(img, icon_styles['icon_padding'])

        # Apply icon's background color
        img = IconEditor.apply_background_color(img, icon_styles['icon_background_color'])

        # Icon's border
        img = IconEditor.apply_border(img, width=icon_styles['icon_border_width'], color=icon_styles['icon_border_color'], radius=icon_styles['icon_border_radius'])

        # Shift icon
        img = IconEditor.move(img, icon_styles['icon_offset'])

        # Adjust brightness
        img = IconEditor.adjust_brightness(img, icon_styles['icon_brightness'])

        # Crop
        img = IconEditor.crop(img, width=button_width, height=button_height)

        # Save image
        img.save(self._generated_path, 'PNG')

        # Optimize image
        optimize_image(self._generated_path, optimize_level=5)

        return img


class RemoteIconLayer(IconLayer):
    @property
    @abstractmethod
    def download_url(self) -> str:
        pass

    def rasterize(self):
        if not self.is_available():
            # Download icon
            icon_provider._request_icon(self)
            return None

        return None


class UrlIconLayer(RemoteIconLayer):
    def __init__(self, icon: dict):
        self._url = icon['icon_name']
        icon['icon_name'] = f'{hash(self._url):0x}'
        self._name = icon['icon_name']

        file_path = os.path.join(CACHE_ICONS_DIR, icon['icon_source'].value, f'{self._name}.png')
        super().__init__(icon, file_path=file_path)

    @property
    def download_url(self):
        return self._url


class RemoteSvgIconLayer(RemoteIconLayer):
    def __init__(self, icon: dict):
        file_path = os.path.join(CACHE_ICONS_DIR, icon['icon_source'].value, f'{icon["icon_name"]}.svg')
        super().__init__(icon, file_path=file_path)


class MaterialDesignIconLayer(RemoteSvgIconLayer):
    @property
    def download_url(self):
        return f'https://raw.githubusercontent.com/Templarian/MaterialDesign/refs/heads/master/svg/{self._name}.svg'


class PhosphorIconLayer(RemoteSvgIconLayer):
    def __init__(self, icon: dict):
        name = icon['icon_name']
        if not icon['icon_variant']:
            icon['icon_variant'] = PhosphorIconVariant.REGULAR

        # Append variant to icon's name
        if icon['icon_variant'] != PhosphorIconVariant.REGULAR:
            name += '-' + icon['icon_variant']

        icon['icon_name'] = name
        super().__init__(icon)

    @property
    def download_url(self):
        return f'https://raw.githubusercontent.com/phosphor-icons/core/refs/heads/main/raw/{self._icon["icon_variant"]}/{self._name}.svg'


class IconProvider:
    def __init__(self):
        self._queue = asyncio.Queue()
        self._requested = set()

    async def _create_download_task(self, icon: dict):
        self._requested.add(icon.download_url)
        await self._queue.put(icon)
        await self._worker()

    def _request_icon(self, icon: dict):
        if icon.download_url in self._requested:
            return

        # Start downloading
        loop = asyncio.get_running_loop()
        loop.create_task(self._create_download_task(icon))

    def get_icon(self, button_config: PageButtonConfig) -> Union[IconLayer, None]:
        # Extract main icon's fields from PageButtoConfig
        main_icon = {}
        main_text_icon = {}

        button_fields = [field.name for field in fields(button_config)]
        for key in button_fields:
            value = getattr(button_config, key)
            # Don't set None values so we could set the default values later
            if value is None:
                continue

            if key in ICON_FIELDS:
                main_icon[key] = value
            elif key in TEXT_ICON_FIELDS:
                main_text_icon[key] = value

        layers = []
        if main_icon:
            layers.append(main_icon)
        if main_text_icon:
            layers.append(main_text_icon)

        additional_icons = button_config.additional_icons or []
        if additional_icons:
            layers += additional_icons

        if layers:
            return Icon(button_config.max_width, button_config.max_height, layers)

        return None

    async def _worker(self):
        """Worker task that processes the queue."""
        icon: IconLayer = await self._queue.get()
        if icon.is_available():
            self._queue.task_done()
            return

        try:
            if isinstance(icon, RemoteIconLayer):
                async with httpx.AsyncClient() as client:
                    url = icon.download_url
                    logging.info(f'Downloading icon: {url}')

                    response = await client.get(url, timeout=5)
                    if response.status_code == 200:
                        with open(icon.original_file_path, 'wb') as fp:
                            fp.write(response.content)

                        # Reload deck
                        await event_bus.publish(EventName.DECK_FORCE_RELOAD)
        finally:
            if icon.id in self._requested:
                self._requested.remove(icon.id)
            self._queue.task_done()


class IconEditor:
    _cached_fonts = {}

    @staticmethod
    def apply_color(img: Image, color: str) -> Image:
        if not color:
            return img

        color = hex_to_rgb(color)
        data = img.getdata()
        new_data = [
            (color[0], color[1], color[2], pixel[3]) if pixel[3] > 0 else (0, 0, 0, 0)
            for pixel in data
        ]
        img.putdata(new_data)

        return img

    @staticmethod
    def apply_background_color(img: Image, color: str) -> Image:
        if not color:
            color = '000000'
            alpha = 0
        else:
            alpha = 255

        bg_color = Image.new('RGBA', img.size, hex_to_rgb(color, alpha=alpha))
        bg_color.paste(img, (0, 0), img)
        img = bg_color

        return img

    @staticmethod
    def apply_padding(img: Image, padding: int) -> Image:
        if not padding or padding <= 0:
            return img

        new_size = (img.width + 2 * padding, img.height + 2 * padding)
        padded_img = Image.new('RGBA', new_size, (0, 0, 0, 0))

        # Paste original image onto the center of the new canvas
        padded_img.paste(img, (padding, padding))
        return padded_img

    @staticmethod
    def move(img: Image, offset: Tuple[int, int]):
        if offset[0] == 0 and offset[1] == 0:
            return img

        width, height = img.size
        new_width = width + abs(offset[0])
        new_height = height + abs(offset[1])

        # Create new image with padding and paste the original image
        new_image = Image.new('RGBA', (new_width, new_height), (0, 0, 0, 0))

        x_position = 0 if offset[0] < 0 else offset[0]
        y_position = 0 if offset[1] < 0 else offset[1]
        new_image.paste(img, (x_position, y_position))

        return new_image

    @staticmethod
    def apply_border(img, *, width: int, color: str, radius: int) -> Image:
        # Border width & color
        if width is not None and color is not None:
            # Add padding with the size of border
            img = IconEditor.apply_padding(img, padding=width)

            # Create an out mask and an in mask
            border_mask = Image.new('L', img.size, 0)
            draw = ImageDraw.Draw(border_mask)
            draw.rounded_rectangle(
                [0, 0, img.width - 1, img.height - 1], radius=radius, fill=255
            )

            mask = Image.new('L', img.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.rounded_rectangle(
                [
                    width,
                    width,
                    img.width - width - 1,
                    img.height - width - 1,
                ],
                radius=max(0, radius - width),
                fill=255,
            )

            border_image = Image.new('RGBA', img.size, color=hex_to_rgb(color, alpha=255))
            new_image = Image.new('RGBA', img.size, color=0)
            # Add the border by pasting the border images onto the new image
            new_image.paste(border_image, (0, 0), mask=border_mask)
            new_image.paste(img, mask=mask)

            img = new_image

        # Border radius
        if radius is not None:
            border_mask = Image.new('L', img.size, 0)
            mask_draw = ImageDraw.Draw(border_mask)
            mask_draw.rounded_rectangle((0, 0, img.width, img.height), radius, fill=255)

            img.paste(img, mask=border_mask)

        return img

    @staticmethod
    def adjust_brightness(img: Image, brightness: int):
        if not brightness or brightness > 100 or brightness < 0:
            return img

        # Create an ImageEnhance object for brightness
        enhancer = ImageEnhance.Brightness(img)

        # Dim the image by reducing brightness (factor < 1 dims the image)
        return enhancer.enhance(brightness / 100)

    @staticmethod
    def draw_texts(img: Image, *, text: str, color: str, align: str, font: str, size: int, offset: int):
        if not text or not color or not font or not size:
            return img

        font_key = f'{font}-{size}'
        if font_key not in IconEditor._cached_fonts:
            font = ImageFont.truetype(f'assets/fonts/{font}.ttf', size)
            IconEditor._cached_fonts[font_key] = font
        else:
            font = IconEditor._cached_fonts[font_key]

        draw = ImageDraw.Draw(img)

        text_width, text_height = draw.textbbox((0, 0), text, font=font)[2:]

        x = (img.width - text_width) // 2
        if align == 'top':
            y = 0
        elif align == 'center':
            y = (img.height - text_height) // 2
        else:
            y = img.height - text_height

        # Adjust offsets
        x += offset[0]
        y += offset[1]

        draw.text((x, y), text, font=font, fill=hex_to_rgb(color))

        return img

    @staticmethod
    def crop(img: Image, width: int, height: int) -> Image:
        new_img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        new_img.paste(img, ((width - img.width) // 2, (height - img.height) // 2))
        return new_img

    @staticmethod
    def resize(img: Image, mode: str, size: Tuple[int, int]) -> Image:
        icon_width, icon_height = size
        img_aspect = img.width / img.height
        target_aspect = icon_width / icon_height

        if mode == 'cover':
            # Scale image to cover entire box while keeping aspect ratio
            if img_aspect > target_aspect:
                new_height = icon_height
                new_width = int(icon_height * img_aspect)
            else:
                new_width = icon_width
                new_height = int(icon_width / img_aspect)

            # Resize
            img = img.resize((new_width, new_height), Image.LANCZOS)

            # Crop
            img = IconEditor.crop(img, width=icon_width, height=icon_height)
        elif mode == 'contain':
            img.thumbnail(size, Image.LANCZOS)
            new_img = Image.new('RGBA', size, (0, 0, 0, 0))
            x_offset = (icon_width - img.width) // 2
            y_offset = (icon_height - img.height) // 2
            new_img.paste(img, (x_offset, y_offset))
            img = new_img
        elif mode == 'stretch':
            img = img.resize(size, Image.LANCZOS)

        return img


icon_provider = IconProvider()
