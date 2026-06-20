"""Build Roxy mascot animation assets from the generated sprite sheet.

Outputs:
- assets/mascot/frames/*.png: transparent per-frame PNGs
- assets/mascot/roxy-mage-preview.gif: looping preview animation
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SPRITE = ROOT / "assets" / "mascot" / "roxy-mage-sprite-sheet.png"
OUT_DIR = ROOT / "assets" / "mascot" / "frames"
GIF = ROOT / "assets" / "mascot" / "roxy-mage-preview.gif"

FRAME_NAMES = [
    "idle",
    "blink",
    "magic",
    "typing",
    "thinking",
    "hop",
]

KEY = (0, 255, 0)
KEY_TOLERANCE = 24


def is_key(pixel: tuple[int, int, int]) -> bool:
    return all(abs(pixel[i] - KEY[i]) <= KEY_TOLERANCE for i in range(3))


def chroma_to_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if is_key((r, g, b)):
                pixels[x, y] = (r, g, b, 0)

    return rgba


def crop_to_content(image: Image.Image, padding: int = 8) -> Image.Image:
    bbox = image.getbbox()
    if bbox is None:
        return image

    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image.width, right + padding)
    bottom = min(image.height, bottom + padding)
    return image.crop((left, top, right, bottom))


def main() -> None:
    sheet = Image.open(SPRITE).convert("RGB")
    frame_count = len(FRAME_NAMES)
    frame_w = sheet.width // frame_count
    frame_h = sheet.height

    if sheet.width % frame_count != 0:
        raise SystemExit(f"Sprite width {sheet.width} is not divisible by {frame_count}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gif_frames: list[Image.Image] = []

    for i, name in enumerate(FRAME_NAMES):
        frame = sheet.crop((i * frame_w, 0, (i + 1) * frame_w, frame_h))
        transparent = chroma_to_alpha(frame)
        transparent.save(OUT_DIR / f"roxy_{i:02d}_{name}.png")

        preview = crop_to_content(transparent, padding=16)
        preview.thumbnail((160, 160), Image.Resampling.NEAREST)

        canvas = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
        canvas.alpha_composite(
            preview,
            ((canvas.width - preview.width) // 2, (canvas.height - preview.height) // 2),
        )
        gif_frames.append(canvas)

    gif_frames[0].save(
        GIF,
        save_all=True,
        append_images=gif_frames[1:],
        duration=[700, 180, 280, 360, 500, 280],
        loop=0,
        disposal=2,
    )

    print(f"Wrote {len(FRAME_NAMES)} frames to {OUT_DIR}")
    print(f"Wrote preview GIF to {GIF}")


if __name__ == "__main__":
    main()
