"""Build per-state mascot GIFs from the six transparent mascot frames.

The generated sprite sheet contains six different poses, not one continuous
motion. This script treats them as state keyframes and creates small looping
animations for each state with simple pixel-safe transforms.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "assets" / "mascot" / "frames"
OUT_DIR = ROOT / "assets" / "mascot" / "actions"

CANVAS = (192, 192)


def load_frame(name: str) -> Image.Image:
    image = Image.open(FRAMES / name).convert("RGBA")
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    image.thumbnail((156, 156), Image.Resampling.NEAREST)
    return image


def on_canvas(sprite: Image.Image, dx: int = 0, dy: int = 0) -> Image.Image:
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    x = (CANVAS[0] - sprite.width) // 2 + dx
    y = (CANVAS[1] - sprite.height) // 2 + dy
    canvas.alpha_composite(sprite, (x, y))
    return canvas


def brighten(sprite: Image.Image, factor: float) -> Image.Image:
    rgb = ImageEnhance.Brightness(sprite.convert("RGB")).enhance(factor)
    out = Image.merge("RGBA", (*rgb.split(), sprite.getchannel("A")))
    return out


def glow(sprite: Image.Image, color: tuple[int, int, int], strength: int = 2) -> Image.Image:
    alpha = sprite.getchannel("A")
    blurred = alpha.filter(ImageFilter.GaussianBlur(radius=strength))
    glow_img = Image.new("RGBA", sprite.size, (*color, 0))
    glow_img.putalpha(blurred.point(lambda p: min(90, p // 3)))
    glow_img.alpha_composite(sprite)
    return glow_img


def save_gif(name: str, frames: list[Image.Image], duration: list[int] | int = 180) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"roxy_{name}.gif"
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
    )
    print(f"Wrote {path}")


def main() -> None:
    idle = load_frame("roxy_00_idle.png")
    blink = load_frame("roxy_01_blink.png")
    magic = load_frame("roxy_02_magic.png")
    typing = load_frame("roxy_03_typing.png")
    thinking = load_frame("roxy_04_thinking.png")
    hop = load_frame("roxy_05_hop.png")

    save_gif(
        "idle",
        [on_canvas(idle, dy=y) for y in (0, -1, -2, -1, 0, 1)],
        [220, 180, 180, 180, 220, 180],
    )

    save_gif(
        "blink",
        [on_canvas(idle), on_canvas(blink), on_canvas(blink), on_canvas(idle)],
        [900, 120, 120, 500],
    )

    save_gif(
        "magic",
        [
            on_canvas(magic),
            on_canvas(glow(magic, (72, 220, 255), 2)),
            on_canvas(glow(brighten(magic, 1.08), (72, 220, 255), 4)),
            on_canvas(glow(magic, (72, 220, 255), 2)),
        ],
        [160, 160, 220, 160],
    )

    save_gif(
        "typing",
        [on_canvas(typing, dy=y) for y in (0, 0, -1, 0, -1, 0)],
        [160, 120, 120, 160, 120, 180],
    )

    save_gif(
        "thinking",
        [on_canvas(thinking, dy=y) for y in (0, -1, 0, 0, 1, 0)],
        [260, 220, 220, 260, 220, 220],
    )

    save_gif(
        "hop",
        [on_canvas(hop, dy=y) for y in (0, -5, -12, -5, 0, 1)],
        [120, 120, 160, 120, 160, 120],
    )


if __name__ == "__main__":
    main()
