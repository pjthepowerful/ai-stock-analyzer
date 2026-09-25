"""Recut the Paula 5 launch video into a fast commercial.

Run: python3 docs/launch-video/build.py  (needs ffmpeg and Pillow). Put
Geist-500/700/800.ttf next to this file first (from Google Fonts). Writes
paula5-commercial.mp4 here; copy it to desktop/frontend-v2/public/launch/paula5.mp4.

Word flashes -> punched-in app shots with big captions -> quick montage ->
end card. Source: the existing 25s promo (app screen at x142-1782, y252-938).
"""
import os
import subprocess
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "source-promo.mp4")
OUT = os.path.join(HERE, "paula5-commercial.mp4")
W, H, FPS = 1920, 1080, 30
BG = (7, 7, 8)
GREEN = (16, 185, 129)
INK = (237, 237, 239)
DIM = (140, 140, 150)
TAGLINE = "Know before you trade."

os.makedirs(os.path.join(HERE, "parts"), exist_ok=True)


def font(size, weight=800):
    return ImageFont.truetype(os.path.join(HERE, f"Geist-{weight}.ttf"), size)


def centered(draw, y, text, f, fill):
    w = draw.textlength(text, font=f)
    draw.text(((W - w) / 2, y), text, font=f, fill=fill)


def card(name, word, bg=BG, fg=INK, size=260):
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    f = font(size)
    box = d.textbbox((0, 0), word, font=f)
    d.text(((W - (box[2] - box[0])) / 2 - box[0], (H - (box[3] - box[1])) / 2 - box[1]), word, font=f, fill=fg)
    p = os.path.join(HERE, "parts", name + ".png")
    img.save(p)
    return p


def caption(name, text):
    """Transparent overlay: dark fade at the bottom, big caption bottom-left."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(420):
        gd.line([(0, y), (W, y)], fill=(7, 7, 8, int(235 * (y / 420) ** 1.6)))
    img.alpha_composite(grad, (0, H - 420))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((120, 880, 132, 990), radius=6, fill=GREEN)
    d.text((164, 870), text, font=font(104), fill=INK)
    p = os.path.join(HERE, "parts", name + ".png")
    img.save(p)
    return p


def end_card():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    s = 120
    x0, y0 = (W - s) // 2, 250
    d.rounded_rectangle((x0, y0, x0 + s, y0 + s), radius=22, fill=GREEN)
    f = font(80, 800)
    bw = d.textlength("P", font=f)
    d.text((x0 + (s - bw) / 2, y0 + 12), "P", font=f, fill=(4, 20, 14))
    centered(d, 410, "Paula 5", font(190), INK)
    centered(d, 640, TAGLINE, font(64, 500), DIM)
    centered(d, 760, "Live now.", font(56, 700), GREEN)
    p = os.path.join(HERE, "parts", "end.png")
    img.save(p)
    return p


def run(args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


ENC = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-preset", "slow", "-crf", "20", "-an"]
parts = []


def still(png, dur, name, fade_in=0.0):
    out = os.path.join(HERE, "parts", name + ".mp4")
    vf = f"scale={W}:{H},format=yuv420p"
    if fade_in:
        vf += f",fade=in:st=0:d={fade_in}"
    run(["-loop", "1", "-t", str(dur), "-i", png, "-vf", vf, *ENC, out])
    parts.append(out)


def shot(name, start, end, speed, crop, cap=None, pan=40):
    """Source [start,end) sped up, punched in on crop=(w,h,x,y) with a slow
    sideways drift, sharpened back up, caption laid over."""
    cw, ch, cx, cy = crop
    out = os.path.join(HERE, "parts", name + ".mp4")
    dur = (end - start) / speed
    drift = f"{cx}+{pan}*t/{dur:.3f}"
    chain = (f"[0:v]trim={start}:{end},setpts=(PTS-STARTPTS)/{speed},fps={FPS},"
             f"crop={cw}:{ch}:'{drift}':{cy},scale={W}:{H}:flags=lanczos,unsharp=5:5:0.7[v]")
    args = ["-i", SRC]
    if cap:
        args += ["-i", cap]
        chain += ";[v][1:v]overlay=0:0:shortest=0[o]"
        label = "[o]"
    else:
        label = "[v]"
    run([*args, "-filter_complex", chain, "-map", label, "-t", f"{dur:.3f}", *ENC, out])
    parts.append(out)


# 1. Word flashes
still(card("w1", "Stocks."), 0.4, "w1")
still(card("w2", "Signals.", bg=GREEN, fg=(4, 20, 14)), 0.4, "w2")
still(card("w3", "Trades."), 0.4, "w3")
still(card("w4", "Meet Paula 5.", size=200), 0.75, "w4")

# 2. App shots, sped up and punched in
shot("chat", 2.2, 5.4, 2.0, (1120, 630, 520, 400), caption("c1", "Ask anything."))
shot("reply", 6.3, 8.0, 2.0, (1200, 675, 560, 300), caption("c2", "Get a straight answer."))
shot("confirm", 8.0, 9.8, 2.0, (1000, 562, 640, 460), caption("c3", "You confirm every trade."))
shot("light", 10.6, 12.6, 2.5, (1280, 720, 380, 250), caption("c4", "Dark. Or light."), pan=-40)
shot("analyze", 13.0, 16.0, 2.0, (1280, 720, 440, 250), caption("c5", "One clear signal."))
shot("earnings", 17.0, 20.0, 2.5, (1400, 788, 360, 200), caption("c6", "Every earnings date."), pan=-40)
shot("cmdk", 20.0, 22.5, 2.0, (1000, 562, 480, 240), caption("c7", "Find anything. Fast."))

# 3. Montage: tight quick cuts
for i, (t, crop) in enumerate([
    (6.6, (800, 450, 700, 330)),
    (15.2, (800, 450, 1000, 380)),
    (18.4, (800, 450, 900, 600)),
    (11.8, (800, 450, 640, 520)),
]):
    shot(f"m{i}", t, t + 0.5, 2.0, crop, pan=20)

# 4. Flash to the end card
white = Image.new("RGB", (W, H), (255, 255, 255))
white.save(os.path.join(HERE, "parts", "white.png"))
still(os.path.join(HERE, "parts", "white.png"), 2 / FPS, "flash")
still(end_card(), 3.0, "end", fade_in=0.25)

lst = os.path.join(HERE, "parts", "list.txt")
with open(lst, "w") as f:
    for p in parts:
        f.write(f"file '{p}'\n")
run(["-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
     "-preset", "slow", "-crf", "21", "-movflags", "+faststart", "-an", OUT])
print(OUT)
