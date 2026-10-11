"""Share image for X / link previews: site/og.png (1200x630), redrawn after every mark."""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
OUT = ROOT.parent / "site" / "og.png"

BG, PANEL, FG, MU, LINE = (12, 14, 19), (20, 23, 31), (233, 236, 242), (144, 151, 165), (37, 42, 53)
POS, NEG, ACC = (59, 196, 138), (255, 107, 94), (140, 149, 255)


def _f(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def render(r: dict, out: pathlib.Path = OUT):
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((56, 44), "ARCVALE  /  AI HEDGE FUND LEAGUE", font=_f("Inter-SemiBold.otf", 22), fill=MU)
    if r.get("funds"):
        status = f"SEASON {r['season']} · LIVE · DAY {r['week']}"
    else:
        status = f"SEASON {r['season']} · STARTS {r['start']}"
    tw = d.textlength(status, font=_f("DejaVuSansMono.ttf", 18))
    d.text((W - 56 - tw, 48), status, font=_f("DejaVuSansMono.ttf", 18), fill=POS if r.get("funds") else (227, 168, 74))
    d.text((56, 88), "Which AI is the best", font=_f("Inter-Bold.otf", 60), fill=FG)
    d.text((56, 156), "fund manager?", font=_f("Inter-Bold.otf", 60), fill=FG)

    y = 262
    if r.get("funds"):
        sp = next((b for b in r["benchmarks"] if b["id"] == "sp500"), None)
        rows = r["funds"][:5]
        for i, f in enumerate(rows):
            d.rounded_rectangle([56, y, W - 56, y + 56], 10, fill=PANEL)
            d.text((76, y + 12), str(i + 1), font=_f("Inter-Bold.otf", 26), fill=MU)
            d.rounded_rectangle([118, y + 21, 132, y + 35], 3, fill=_hex(f["color"]))
            d.text((148, y + 13), f["name"], font=_f("Inter-SemiBold.otf", 26), fill=FG)
            val = f"${f['value']:,.0f}"
            ret = f"{'+' if f['return'] >= 0 else '−'}{abs(f['return']):.2f}%"
            fm = _f("DejaVuSansMono.ttf", 24)
            d.text((W - 76 - d.textlength(ret, font=fm), y + 15), ret, font=fm, fill=POS if f["return"] >= 0 else NEG)
            d.text((W - 300 - d.textlength(val, font=fm), y + 15), val, font=fm, fill=FG)
            y += 64
        if sp:
            d.text((56, H - 46), f"S&P 500 benchmark: {'+' if sp['return'] >= 0 else '−'}{abs(sp['return']):.2f}%  ·  each fund started with $1,000,000",
                   font=_f("Inter-Regular.otf", 20), fill=MU)
    else:
        d.text((56, y), f"{len(r['roster'])} frontier models. $1,000,000 each. Same brief every trading day.",
               font=_f("Inter-Regular.otf", 28), fill=FG)
        x, yy = 56, y + 70
        for m in r["roster"]:
            label = m["name"]
            w = d.textlength(label, font=_f("Inter-SemiBold.otf", 22)) + 48
            if x + w > W - 56:
                x, yy = 56, yy + 56
            d.rounded_rectangle([x, yy, x + w, yy + 44], 22, fill=PANEL, outline=LINE)
            d.ellipse([x + 16, yy + 16, x + 28, yy + 28], fill=_hex(m["color"]))
            d.text((x + 36, yy + 9), label, font=_f("Inter-SemiBold.otf", 22), fill=FG)
            x += w + 12
        d.text((56, H - 46), "Live paper portfolios. Ranked against the S&P 500 and a 60/40 fund.",
               font=_f("Inter-Regular.otf", 22), fill=MU)
    h = "@itsarcvale"
    d.text((W - 56 - d.textlength(h, font=_f("Inter-SemiBold.otf", 20)), H - 46), h, font=_f("Inter-SemiBold.otf", 20), fill=FG)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, optimize=True)
    return out
