"""Build the 1200 x 630 social preview from tools/preview.html.

    python3 tools/build_preview.py
"""
import pathlib

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "assets" / "preview.jpg"
W, H = 1200, 630


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        page.goto((HERE / "preview.html").as_uri())
        page.wait_for_load_state("networkidle")
        page.evaluate("document.fonts.ready.then(() => true)")
        page.screenshot(path=str(OUT.with_suffix(".png")), clip={"x": 0, "y": 0, "width": W, "height": H})
        browser.close()

    img = Image.open(OUT.with_suffix(".png")).convert("RGB").resize((W, H), Image.LANCZOS)
    img.save(OUT, quality=88, optimize=True, progressive=True)
    OUT.with_suffix(".png").unlink()
    print(f"wrote {OUT.relative_to(ROOT)}  {W}x{H}  {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
