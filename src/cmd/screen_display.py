"""Show a fullscreen picture and play screen glitch effects on the host.

The `display_image` helper puts an attached picture on the primary
display with OpenCV and the `play_glitch` helper paints the screen with
the GDI API of Windows. Both of them run their blocking work in a worker
thread, so the bot keeps answering messages while an effect is playing.
"""

import asyncio
import ctypes
import math
import random
import tempfile
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable
from uuid import uuid4

import cv2
import numpy as np
from discord.ext import commands
from discord.ext.commands import Context

# The raster operations of the GDI.
# PATCOPY paints a rectangle with the brush that is selected in the device
# context, so it is used to draw the coloured shapes of the effects.
PATCOPY = 0x00F00021
# PATINVERT flips the colours of every pixel it covers, which is what the
# inverting effects of the screen need.
PATINVERT = 0x005A0049

# The style of the pens that draw the lines of the effects.
PS_SOLID = 0

# The names of the effects that `play_glitch` understands.
GLITCH_EFFECTS: list[str] = [
    "invert",
    "noise",
    "lines",
    "invert_squares",
    "color_squares",
    "diagonal_lines",
    "snowfall",
    "hypnotic_spirals",
    "random_lines",
]

# The shortest and the longest time a picture stays on the screen.
MIN_DISPLAY_SECONDS = 1
MAX_DISPLAY_SECONDS = 600

# The shortest and the longest time an effect is played.
MIN_GLITCH_SECONDS = 1
MAX_GLITCH_SECONDS = 60

# The image formats that OpenCV is able to show.
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

# The biggest attachment that is downloaded.
MAX_IMAGE_BYTES = 15 * 1024 * 1024

# The size of the squares of the noise effect.
NOISE_SQUARE_SIZE = 100
# The amount of squares the noise effect draws in one frame.
NOISE_SQUARE_COUNT = 100

# The distance and the thickness of the lines of the lines effect.
LINE_SPACING = 5
LINE_THICKNESS = 2

# The amount of rectangles the invert squares effect flips in one frame.
INVERT_SQUARE_COUNT = 200

# The size of the squares of the colour squares effect.
COLOR_SQUARE_SIZE = 20
# The amount of colours the colour squares effect mixes.
COLOR_PALETTE_SIZE = 16

# The distance between the diagonal lines.
DIAGONAL_SPACING = 10

# The amount of dots of the snowfall effect and their size.
SNOWFALL_DOT_COUNT = 100
SNOWFALL_DOT_SIZE = 3
# The time between two moves of the snowfall dots and the distance they
# travel while they move.
SNOWFALL_INTERVAL = 0.5
SNOWFALL_SPEED = 12

# The amount of lines of the spiral effect, the angle between them and the
# angle they rotate by in every frame.
SPIRAL_LINE_COUNT = 36
SPIRAL_ANGLE_STEP = 10
SPIRAL_ROTATION = 1.5

# The amount of lines the random lines effect draws in one frame.
RANDOM_LINE_COUNT = 50

# The pause between two frames of an effect.
FRAME_DELAY_MS = 10

# The Windows API that paints on the screen.
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
# The pause between two frames lives in the kernel and not in the user API.
kernel32 = ctypes.windll.kernel32

# The prototypes are written down so the handles of the 64 bit Windows are
# not truncated into 32 bit integers.
user32.GetDC.argtypes = [ctypes.c_void_p]
user32.GetDC.restype = ctypes.c_void_p
user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.ReleaseDC.restype = ctypes.c_int
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
kernel32.Sleep.argtypes = [ctypes.c_uint]
kernel32.Sleep.restype = None
gdi32.PatBlt.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_ulong,
]
gdi32.PatBlt.restype = ctypes.c_int
gdi32.CreateSolidBrush.argtypes = [ctypes.c_ulong]
gdi32.CreateSolidBrush.restype = ctypes.c_void_p
gdi32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
gdi32.CreatePen.restype = ctypes.c_void_p
gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.SelectObject.restype = ctypes.c_void_p
gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
gdi32.DeleteObject.restype = ctypes.c_int
gdi32.MoveToEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_void_p,
]
gdi32.MoveToEx.restype = ctypes.c_int
gdi32.LineTo.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
gdi32.LineTo.restype = ctypes.c_int
gdi32.SetDIBitsToDevice.restype = ctypes.c_int
gdi32.SetDIBitsToDevice.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_ulong,
    ctypes.c_ulong,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_uint,
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_ulong,
]
user32.InvalidateRect.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_int,
]
user32.InvalidateRect.restype = ctypes.c_int

# The index of the screen width and the screen height in GetSystemMetrics.
SM_CXSCREEN = 0
SM_CYSCREEN = 1


class BITMAPINFOHEADER(ctypes.Structure):
    """The header of the bitmap that is painted onto the screen."""

    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


@dataclass
class _EffectState:
    """The values an effect keeps between two frames of itself."""

    # The positions of the dots of the snowfall effect.
    dots: list[list[int]] = field(default_factory=list)
    # The moment the dots of the snowfall effect move again.
    next_move: float = 0.0
    # The angle the lines of the spiral effect rotated to.
    angle: float = 0.0


# The signature every effect of the screen follows.
EffectFunction = Callable[[int, int, int, _EffectState], None]


def _rgb(red: int, green: int, blue: int) -> int:
    """Pack the three channels of a colour into the COLORREF of Windows."""
    return red | (green << 8) | (blue << 16)


def _random_colour() -> int:
    """Return a random colour in the COLORREF format of Windows."""
    return _rgb(
        random.randrange(256),
        random.randrange(256),
        random.randrange(256),
    )


def _fill_rect(
    hdc: int, x: int, y: int, width: int, height: int, colour: int
) -> None:
    """Fill a rectangle of the screen with a solid colour."""
    if width <= 0 or height <= 0:
        return

    brush = gdi32.CreateSolidBrush(colour)
    if not brush:
        return

    previous = gdi32.SelectObject(hdc, brush)
    try:
        gdi32.PatBlt(hdc, x, y, width, height, PATCOPY)
    finally:
        # The brush can only be deleted once it is no longer selected.
        gdi32.SelectObject(hdc, previous)
        gdi32.DeleteObject(brush)


def _draw_line(
    hdc: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    colour: int,
    width: int = 2,
) -> None:
    """Draw a line on the screen with the given colour."""
    pen = gdi32.CreatePen(PS_SOLID, width, colour)
    if not pen:
        return

    previous = gdi32.SelectObject(hdc, pen)
    try:
        gdi32.MoveToEx(hdc, x1, y1, None)
        gdi32.LineTo(hdc, x2, y2)
    finally:
        # The pen can only be deleted once it is no longer selected.
        gdi32.SelectObject(hdc, previous)
        gdi32.DeleteObject(pen)


def _effect_invert(
    hdc: int, width: int, height: int, state: _EffectState
) -> None:
    """Flip the colours of the whole screen."""
    gdi32.PatBlt(hdc, 0, 0, width, height, PATINVERT)


def _effect_noise(
    hdc: int, width: int, height: int, state: _EffectState
) -> None:
    """Scatter random coloured squares over the screen."""
    for _ in range(NOISE_SQUARE_COUNT):
        x = random.randint(0, max(width - NOISE_SQUARE_SIZE, 0))
        y = random.randint(0, max(height - NOISE_SQUARE_SIZE, 0))
        _fill_rect(
            hdc, x, y, NOISE_SQUARE_SIZE, NOISE_SQUARE_SIZE, _random_colour()
        )


def _effect_lines(
    hdc: int, width: int, height: int, state: _EffectState
) -> None:
    """Draw inverted horizontal lines over the whole screen."""
    for y in range(0, height, LINE_SPACING):
        gdi32.PatBlt(hdc, 0, y, width, LINE_THICKNESS, PATINVERT)


def _effect_invert_squares(
    hdc: int, width: int, height: int, state: _EffectState
) -> None:
    """Flip random rectangles of the screen."""
    for _ in range(INVERT_SQUARE_COUNT):
        x = random.randint(0, max(width - 1, 0))
        y = random.randint(0, max(height - 1, 0))
        rect_width = random.randint(10, 200)
        rect_height = random.randint(10, 200)
        gdi32.PatBlt(hdc, x, y, rect_width, rect_height, PATINVERT)


def _effect_color_squares(
    hdc: int, width: int, height: int, state: _EffectState
) -> None:
    """Fill the screen with a grid of random coloured squares."""
    # A small palette keeps the amount of GDI calls per frame low.
    brushes = [
        brush
        for brush in (
            gdi32.CreateSolidBrush(_random_colour())
            for _ in range(COLOR_PALETTE_SIZE)
        )
        if brush
    ]

    if not brushes:
        return

    try:
        for grid_y in range(0, height, COLOR_SQUARE_SIZE):
            for grid_x in range(0, width, COLOR_SQUARE_SIZE):
                previous = gdi32.SelectObject(hdc, random.choice(brushes))
                try:
                    gdi32.PatBlt(
                        hdc,
                        grid_x,
                        grid_y,
                        COLOR_SQUARE_SIZE,
                        COLOR_SQUARE_SIZE,
                        PATCOPY,
                    )
                finally:
                    gdi32.SelectObject(hdc, previous)
    finally:
        for brush in brushes:
            gdi32.DeleteObject(brush)


def _effect_diagonal_lines(
    hdc: int, width: int, height: int, state: _EffectState
) -> None:
    """Draw parallel diagonal lines over the screen."""
    for offset in range(-height, width, DIAGONAL_SPACING):
        _draw_line(
            hdc,
            offset,
            0,
            offset + height,
            height,
            _random_colour(),
            1,
        )


def _effect_snowfall(
    hdc: int, width: int, height: int, state: _EffectState
) -> None:
    """Let white dots drift down the screen."""
    now = time.time()

    if not state.dots:
        state.dots = [
            [
                random.randint(0, max(width - 1, 0)),
                random.randint(0, max(height - 1, 0)),
            ]
            for _ in range(SNOWFALL_DOT_COUNT)
        ]
        state.next_move = now

    if now < state.next_move:
        return

    state.next_move = now + SNOWFALL_INTERVAL

    for dot in state.dots:
        dot[1] += SNOWFALL_SPEED

        # A dot that left the screen starts again at the top of it.
        if dot[1] > height:
            dot[0] = random.randint(0, max(width - 1, 0))
            dot[1] = 0

        _fill_rect(
            hdc,
            dot[0],
            dot[1],
            SNOWFALL_DOT_SIZE,
            SNOWFALL_DOT_SIZE,
            _rgb(255, 255, 255),
        )


def _effect_hypnotic_spirals(
    hdc: int, width: int, height: int, state: _EffectState
) -> None:
    """Draw lines from the centre of the screen outwards while they turn."""
    state.angle += SPIRAL_ROTATION

    centre_x = width // 2
    centre_y = height // 2
    radius = max(width, height)

    for step in range(SPIRAL_LINE_COUNT):
        angle = state.angle + step * SPIRAL_ANGLE_STEP
        end_x = int(centre_x + radius * math.cos(math.radians(angle)))
        end_y = int(centre_y + radius * math.sin(math.radians(angle)))
        _draw_line(hdc, centre_x, centre_y, end_x, end_y, _random_colour(), 1)


def _effect_random_lines(
    hdc: int, width: int, height: int, state: _EffectState
) -> None:
    """Draw random coloured lines over the screen."""
    for _ in range(RANDOM_LINE_COUNT):
        start_x = random.randint(0, max(width - 1, 0))
        start_y = random.randint(0, max(height - 1, 0))
        end_x = random.randint(0, max(width - 1, 0))
        end_y = random.randint(0, max(height - 1, 0))
        _draw_line(hdc, start_x, start_y, end_x, end_y, _random_colour(), 2)


# The drawing function of every effect of the screen.
_EFFECTS: dict[str, EffectFunction] = {
    "invert": _effect_invert,
    "noise": _effect_noise,
    "lines": _effect_lines,
    "invert_squares": _effect_invert_squares,
    "color_squares": _effect_color_squares,
    "diagonal_lines": _effect_diagonal_lines,
    "snowfall": _effect_snowfall,
    "hypnotic_spirals": _effect_hypnotic_spirals,
    "random_lines": _effect_random_lines,
}


def _run_effect(effect: str, seconds: int) -> None:
    """Play a glitch effect on the screen for the given number of seconds."""
    hdc = user32.GetDC(0)
    if not hdc:
        raise ctypes.WinError()

    try:
        width = user32.GetSystemMetrics(SM_CXSCREEN)
        height = user32.GetSystemMetrics(SM_CYSCREEN)
        draw = _EFFECTS[effect]
        state = _EffectState()
        deadline = time.time() + seconds

        while time.time() < deadline:
            draw(hdc, width, height, state)
            kernel32.Sleep(FRAME_DELAY_MS)
    finally:
        # The device context of the screen has to be given back, otherwise
        # the desktop keeps a handle on it forever.
        user32.ReleaseDC(0, hdc)


def _show_fullscreen(image_path: str, seconds: int) -> None:
    """Show the picture fullscreen for the given number of seconds."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"OpenCV could not open {image_path}.")

    cv2.namedWindow("display", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(
        "display", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN
    )

    try:
        cv2.imshow("display", image)

        deadline = time.time() + seconds
        while time.time() < deadline:
            cv2.waitKey(30)
    finally:
        cv2.destroyAllWindows()


def _paint_fullscreen(image_path: str, seconds: int) -> None:
    """Paint the picture over the whole screen without opening a window.

    This is the fallback for the machines where OpenCV cannot open a
    window, the picture is drawn straight onto the screen of the desktop.
    """
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"OpenCV could not open {image_path}.")

    height, width = image.shape[:2]

    # OpenCV reads the picture in blue, green, red order and the screen
    # expects the colours of a bitmap in the same order.
    bitmap = np.zeros((height, width, 4), dtype=np.uint8)
    bitmap[:, :, :3] = image

    header = BITMAPINFOHEADER()
    header.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    header.biWidth = width
    # A negative height tells the GDI that the rows are stored top down.
    header.biHeight = -height
    header.biPlanes = 1
    header.biBitCount = 32
    header.biCompression = 0

    bits = ctypes.create_string_buffer(bitmap.tobytes())
    hdc = user32.GetDC(0)

    if not hdc:
        raise ctypes.WinError()

    try:
        gdi32.SetDIBitsToDevice(
            hdc,
            0,
            0,
            width,
            height,
            0,
            0,
            0,
            height,
            ctypes.cast(bits, ctypes.c_void_p),
            ctypes.byref(header),
            0,
        )

        time.sleep(seconds)
    finally:
        user32.ReleaseDC(0, hdc)

        # The desktop paints itself again over the picture.
        user32.InvalidateRect(None, None, True)


async def display_image(ctx: Context[commands.Bot], seconds: int = 10) -> None:
    """Show an attached picture fullscreen on the primary display."""
    attachment = next(
        (
            item
            for item in ctx.message.attachments
            if item.content_type and item.content_type.startswith("image/")
        ),
        None,
    )

    if attachment is None:
        await ctx.reply("Please attach an image to your message.")
        return

    suffix = Path(attachment.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        await ctx.reply(
            "Please attach a JPG, JPEG, PNG, BMP, GIF or WEBP image."
        )
        return

    if attachment.size > MAX_IMAGE_BYTES:
        await ctx.reply("The image must be smaller than 15 MB.")
        return

    seconds = max(MIN_DISPLAY_SECONDS, min(seconds, MAX_DISPLAY_SECONDS))
    path = Path(tempfile.gettempdir()) / f"discord_display_{uuid4().hex}{suffix}"

    try:
        await attachment.save(path)
    except Exception as exc:
        print(f"Image download error: {exc}")
        path.unlink(missing_ok=True)
        await ctx.reply("Could not download the attached image.")
        return

    try:
        await ctx.reply(f"Displaying the image for {seconds} seconds.")
    except Exception as exc:
        # The picture has to stay on the screen even when Discord refuses
        # the reply of the command.
        print(f"Reply error: {exc}")

    try:
        await asyncio.to_thread(_show_fullscreen, str(path), seconds)
    except Exception as exc:
        print(f"Display error: {exc}")

        # A machine without a usable window still has to see the picture.
        try:
            await asyncio.to_thread(_paint_fullscreen, str(path), seconds)
        except Exception as fallback_exc:
            print(f"Display fallback error: {fallback_exc}")
            await ctx.reply("Could not show the image on the screen.")
    finally:
        path.unlink(missing_ok=True)


async def play_glitch(
    ctx: Context[commands.Bot], effect: str, seconds: int = 5
) -> None:
    """Play a screen glitch effect on the primary display."""
    name = effect.strip().lower()

    if name not in GLITCH_EFFECTS:
        await ctx.reply(
            f"Unknown effect `{effect}`. "
            f"Available effects: {', '.join(GLITCH_EFFECTS)}."
        )
        return

    seconds = max(MIN_GLITCH_SECONDS, min(seconds, MAX_GLITCH_SECONDS))

    await ctx.reply(f"Playing the `{name}` effect for {seconds} seconds.")

    try:
        await asyncio.to_thread(_run_effect, name, seconds)
    except Exception as exc:
        print(f"Glitch error: {exc}")
        await ctx.reply("Could not play the effect on the screen.")
