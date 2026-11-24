#!/usr/bin/env python3
# The package's pictures. When the assets dir holds cover.jpg (the N64 box art) and screenshot.jpg
# (a gameplay shot), they are used as in the template's original design; otherwise the pictures are
# drawn from the port's own cow (OS launcher icon), which is what the released packages ship.
#   sce_sys/icon0.png  512x512, the home screen tile
#   sce_sys/pic1.png   1920x1080, the background behind it
import sys
import os

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

assets, out = sys.argv[1], sys.argv[2]
cow_app_png = sys.argv[3] if len(sys.argv) > 3 else None  # the source tree's icons/app.png

# The project's own pictures (drawn from the cow): used as-is when present.
if os.path.exists(f"{assets}/icon0.png") and os.path.exists(f"{assets}/pic1.png"):
    import shutil
    shutil.copy(f"{assets}/icon0.png", f"{out}/icon0.png")
    shutil.copy(f"{assets}/pic1.png", f"{out}/pic1.png")
    sys.exit(0)

cover_path = f"{assets}/cover.jpg"
shot_path = f"{assets}/screenshot.jpg"

if os.path.exists(cover_path) and os.path.exists(shot_path):
    cover = Image.open(cover_path).convert("RGB")
    shot = Image.open(shot_path).convert("RGB")

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

# Drawn from the port's own cow (no external art): the tile on the console's dark blue, and a
# 1920x1080 pic1 with the game's name.
cow = Image.open(cow_app_png).convert("RGBA")

icon = Image.new("RGB", (512, 512), (26, 36, 54))
top, bottom = (34, 48, 73), (16, 22, 34)
draw = ImageDraw.Draw(icon)
for y in range(512):
    t = y / 511
    draw.line([(0, y), (511, y)], fill=tuple(int(s + (b - s) * t) for s, b in zip(top, bottom)))
side = 400
c = cow.resize((side, side), Image.LANCZOS)
icon.paste(c, ((512 - side) // 2, (512 - side) // 2 + 6), c)
icon.save(f"{out}/icon0.png")

W, H = 1920, 1080
bg = Image.new("RGB", (W, H), (14, 19, 29))
draw = ImageDraw.Draw(bg)
for y in range(H):
    t = y / (H - 1)
    c1, c2 = (30, 42, 64), (14, 19, 29)
    draw.line([(0, y), (W, y)], fill=tuple(int(s + (b - s) * t) for s, b in zip(c1, c2)))
c = cow.resize((640, 640), Image.LANCZOS)
bg.paste(c, (170, (H - 640) // 2), c)
font_path = f"{os.path.dirname(cow_app_png)}/../assets/Suplexmentary Comic NC.ttf"
font_big = ImageFont.truetype(font_path, 108)
font_small = ImageFont.truetype(font_path, 44)
draw.text((930, 390), "Harvest Moon 64", font=font_big, fill=(245, 245, 240))
draw.text((930, 520), "Recompiled for PS4", font=font_small, fill=(247, 199, 92))
draw.text((930, 610), "a fan project, personal use only", font=font_small, fill=(140, 155, 180))
bg.save(f"{out}/pic1.png")
