"""Build assets/app.ico (multi-size) and assets/app.png from assets/icon_source.jpg.

The source is the generated artwork: a blue rounded square on a white
background. We find the square, crop it, and make everything outside the
rounded corners transparent.
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "icon_source.jpg")
ICO = os.path.join(ROOT, "assets", "app.ico")
PNG = os.path.join(ROOT, "assets", "app.png")
CORNER_RATIO = 0.208  # corner radius / square side, measured on the source art
INSET = 3             # px trimmed inside the edge to avoid a white fringe


def find_square(im):
    w, h = im.size
    dark = lambda p: sum(p) < 600  # noqa: E731 - "not white"
    xs = [x for x in range(w) if dark(im.getpixel((x, h // 2)))]
    ys = [y for y in range(h) if dark(im.getpixel((w // 2, y)))]
    return xs[0], ys[0], xs[-1] + 1, ys[-1] + 1


def main():
    im = Image.open(SRC).convert("RGB")
    left, top, right, bottom = find_square(im)
    box = (left + INSET, top + INSET, right - INSET, bottom - INSET)
    sq = im.crop(box).convert("RGBA")
    side = sq.size[0]
    big = 4  # supersample the mask for smooth corners
    mask = Image.new("L", (side * big, side * big), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, side * big - 1, side * big - 1), radius=int(side * CORNER_RATIO * big), fill=255)
    sq.putalpha(mask.resize((side, side), Image.LANCZOS))

    # small padding so the icon does not touch the edge of its canvas
    canvas_side = int(side * 1.04)
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    off = (canvas_side - side) // 2
    canvas.paste(sq, (off, off), sq)

    canvas.resize((256, 256), Image.LANCZOS).save(PNG)
    canvas.resize((256, 256), Image.LANCZOS).save(
        ICO, sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64),
                    (128, 128), (256, 256)])
    print("wrote", ICO, "and", PNG)


if __name__ == "__main__":
    main()
