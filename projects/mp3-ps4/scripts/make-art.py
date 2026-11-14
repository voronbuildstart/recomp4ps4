#!/usr/bin/env python3
# The package's pictures. When the assets dir holds cover.jpg (the N64 box art) and screenshot.jpg
# (a gameplay shot), they are used as in the template's original design; otherwise the pictures are
# the ones drawn for the port (the star under the party lights).
#   sce_sys/icon0.png  512x512, the home screen tile
#   sce_sys/pic1.png   1920x1080, the background behind it
import sys
import os

from PIL import Image, ImageEnhance, ImageFilter
import shutil

assets, out = sys.argv[1], sys.argv[2]

# The port's own pictures (drawn): used as-is when present.
if os.path.exists(f"{assets}/icon0.png") and os.path.exists(f"{assets}/pic1.png"):
    shutil.copy(f"{assets}/icon0.png", f"{out}/icon0.png")
    shutil.copy(f"{assets}/pic1.png", f"{out}/pic1.png")
    sys.exit(0)

if os.path.exists(f"{assets}/cover.jpg") and os.path.exists(f"{assets}/screenshot.jpg"):
    cover = Image.open(f"{assets}/cover.jpg").convert("RGB")
    shot = Image.open(f"{assets}/screenshot.jpg").convert("RGB")

    art = cover.crop((14, 6, 286, 246))
    art.paste((0, 0, 0), (0, 0, 64, 106))
    side = max(art.size)
    tile = Image.new("RGB", (side, side), (0, 0, 0))
    tile.paste(art, ((side - art.width) // 2, (side - art.height) // 2))
    tile.resize((512, 512), Image.LANCZOS).save(f"{out}/icon0.png")

    W, H = 1920, 1080
    scale = max(W / shot.width, H / shot.height)
    bg = shot.resize((round(shot.width * scale), round(shot.height * scale)), Image.LANCZOS)
    left, top = (bg.width - W) // 2, (bg.height - H) // 2
    bg = bg.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(6))
    bg = ImageEnhance.Brightness(bg).enhance(0.6)
    box_h = 860
    box = cover.resize((round(cover.width * box_h / cover.height), box_h), Image.LANCZOS)
    shadow = Image.new("RGB", (box.width + 24, box.height + 24), (0, 0, 0))
    x, y = W - box.width - 140, (H - box_h) // 2
    bg.paste(shadow, (x - 12 + 10, y - 12 + 10))
    bg.paste(box, (x, y))
    bg.save(f"{out}/pic1.png")
    sys.exit(0)

raise SystemExit("no art: assets/icon0.png + assets/pic1.png (or cover.jpg + screenshot.jpg) required")
