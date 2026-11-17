"""Draw the Timely Ride Log app icons (ride-log/icons/*.png) in the style of the simulator mark. Needs Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw
OUT = Path(__file__).resolve().parent.parent / 'ride-log' / 'icons'
def icon(size, pad=0.0, rounded=True):
    S = size * 4; im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    bg = (10, 18, 26, 255)
    if rounded: d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * .22), fill=bg)
    else: d.rectangle([0, 0, S, S], fill=bg)
    u = lambda v: int(pad * S + v * S * (1 - 2 * pad))   # 0..1 inside the safe zone
    w = max(4, int(S * (1 - 2 * pad) * .085))
    for y, x1, col in ((.30, .66, (47, 158, 79)), (.50, .82, (147, 51, 196)), (.70, .52, (255, 201, 40))):
        d.line([(u(.18), u(y)), (u(x1), u(y))], fill=col, width=w); 
        for x in (u(.18), u(x1)): d.ellipse([x - w / 2, u(y) - w / 2, x + w / 2, u(y) + w / 2], fill=col)
    r = int(S * (1 - 2 * pad) * .075)
    for cx, cy in ((.70, .30), (.60, .70)):
        d.ellipse([u(cx) - r, u(cy) - r, u(cx) + r, u(cy) + r], fill=bg, outline=(79, 216, 255), width=max(3, w // 2))
    return im.resize((size, size), Image.LANCZOS)
OUT.mkdir(parents=True, exist_ok=True)
icon(192).save(OUT / 'icon-192.png'); icon(512).save(OUT / 'icon-512.png')
icon(512, pad=.12, rounded=False).save(OUT / 'icon-maskable-512.png')
icon(180, rounded=False).save(OUT / 'apple-touch-icon.png')
print('icons written to', OUT)
