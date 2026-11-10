"""Render the static card art (tools/layer.html) to assets/layer-participant.png.

Run:  python3 tools/build_layer.py

The layer holds everything that never changes: header logos, orbit rings, the
participant chip, the collaborator strip and the foot band. The canvas draws
the photo and the name on top of it.
"""
import pathlib
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = HERE / "layer.html"
OUT = ROOT / "assets" / "layer-participant.png"
W, H = 1080, 1350
SCALE = 2  # render at 2x then downsample, so hairlines and logos stay crisp


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
        page.goto(SRC.as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready.then(() => true)")
        page.screenshot(path=str(OUT), clip={"x": 0, "y": 0, "width": W, "height": H})
        browser.close()

    img = Image.open(OUT).convert("RGB")
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)
    img.save(OUT, optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)}  {img.size[0]}x{img.size[1]}  {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    sys.exit(main())
