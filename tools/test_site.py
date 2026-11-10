"""Browser checks for the participant card maker.

    python3 tools/test_site.py

Serves the repo on a random port, drives it in headless Chrome and exercises the
things that actually break: missing assets, console errors, the download, the
photo framing, the share button, long names and the mobile layout.
Exits non-zero if anything fails.
"""
import functools
import http.server
import io
import pathlib
import socketserver
import sys
import threading

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
TMP = pathlib.Path("/tmp/opencode")
TMP.mkdir(parents=True, exist_ok=True)

COLABS = ["KNUST E-Learning Centre", "Open Foundation West Africa", "DIPPER Lab, KNUST",
          "Federated Commodities PLC", "AstroXMat Research Laboratory", "Ghana Space Conference",
          "She Code Africa, Greater Accra Chapter", "Ladies in Design Network",
          "Ghana Institution of Engineering", "Pixova Ghana"]

fails = []


def check(ok, label, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + label + ("" if ok or not detail else f"   ({detail})"))
    if not ok:
        fails.append(label)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(ROOT)))
    httpd.allow_reuse_address = True
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def photo(path, w=800, h=1200, colour=(11, 110, 79)):
    img = Image.new("RGB", (w, h), colour)
    d = img.load()
    for y in range(h):                      # a gradient, so rotation/zoom is visible
        for x in range(0, w, 8):
            v = int(40 * y / h)
            for xx in range(x, min(x + 8, w)):
                r, g, b = colour
                d[xx, y] = (r + v // 4, g + v // 6, b + v // 5)
    img.save(path, quality=92)
    return path


def hook_errors(page):
    log = {"console": [], "pageerror": [], "failed": [], "http": []}
    page.on("console", lambda m: log["console"].append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: log["pageerror"].append(str(e)))
    page.on("requestfailed", lambda r: log["failed"].append(r.url))
    page.on("response", lambda r: log["http"].append((r.status, r.url)) if r.status >= 400 else None)
    return log


def load(page, base):
    page.goto(base, wait_until="networkidle")
    page.evaluate("document.fonts.ready.then(() => true)")
    page.wait_for_function("document.getElementById('c') && document.getElementById('c').getContext('2d')")


def wrong_pixels(page, points, colour=(237, 242, 252)):
    """Return the circle-edge sample points that still show the empty placeholder."""
    out = []
    for x, y in points:
        px = page.evaluate("""([x, y]) => {
          const g = document.getElementById('c').getContext('2d');
          return Array.from(g.getImageData(Math.round(x), Math.round(y), 1, 1).data.slice(0, 3));
        }""", [x, y])
        if all(abs(px[i] - colour[i]) < 10 for i in range(3)):
            out.append((x, y, px))
    return out


def main():
    httpd, base = serve()
    shot = TMP / "site"
    shot.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])

        # ---------------------------------------------------------------- desktop
        page = b.new_page(viewport={"width": 1366, "height": 900}, accept_downloads=True)
        log = hook_errors(page)
        load(page, base)
        page.screenshot(path=str(shot / "desktop.png"), full_page=True)

        print("page")
        check(not log["pageerror"], "no uncaught page errors", "; ".join(log["pageerror"]))
        check(not log["console"], "no console errors", "; ".join(log["console"]))
        check(not log["http"], "no 4xx/5xx responses", str(log["http"][:3]))
        check(not log["failed"], "no failed requests", str(log["failed"][:3]))
        check(page.title() == "Participant card · NASA Space Apps Kumasi 2026", "title")
        h1 = page.inner_text("h1").replace("\n", " ")
        check("NASA" in h1.upper() and "KUMASI" in h1.upper(), "headline carries NASA and Kumasi", h1)
        check("official local edition" in page.inner_text(".fine").lower(), "footer disclaimer")

        print("assets")
        imgs = page.evaluate("""() => Array.from(document.images).map(i => ({
            src: i.getAttribute('src'), ok: i.complete && i.naturalWidth > 0,
            w: i.naturalWidth, h: i.naturalHeight, alt: i.alt}))""")
        broken = [i["src"] for i in imgs if not i["ok"]]
        check(not broken, f"all {len(imgs)} images decode", str(broken))
        check(all(i["w"] > 0 for i in imgs), "every image has pixels")
        urls = page.evaluate("""() => [...document.querySelectorAll('[src],[href]')]
            .map(e => e.getAttribute('src') || e.getAttribute('href'))
            .filter(u => u && !/^(https?:|#|mailto:)/.test(u))""")
        missing = [u for u in set(urls) if page.request.get(base + u.lstrip("./")).status != 200]
        check(not missing, f"all {len(set(urls))} local links return 200", str(missing))
        og = page.get_attribute('meta[property="og:image"]', "content")
        check(og.endswith("/assets/preview.jpg"), "og:image points at the preview", og)
        check((ROOT / "assets/preview.jpg").exists(), "og:image file exists locally")

        print("collaborators")
        strip = page.evaluate("""() => Array.from(document.querySelectorAll('.logos img'))
            .map(i => ({alt: i.alt, ok: i.complete && i.naturalWidth > 0, h: i.getBoundingClientRect().height}))
            """)
        check(len(strip) == 10, "ten logos in the footer strip", f"{len(strip)}")
        check([s["alt"] for s in strip] == COLABS, "strip order matches the card and the banner")
        check(all(s["ok"] for s in strip), "every collaborator logo loads")
        check(all(s["h"] <= 40.5 for s in strip), "no logo taller than its 40px rule",
              str(max((s["h"] for s in strip), default=0)))
        cols = page.evaluate("getComputedStyle(document.querySelector('.logos')).gridTemplateColumns.split(' ').length")
        check(cols == 5, "five logos per row on desktop", str(cols))

        print("share button")
        check(not page.is_visible("#share"), "hidden when the browser cannot share files")

        print("name")
        check(page.is_disabled("#dl") and page.is_disabled("#zoom"), "download and zoom start disabled")
        page.fill("#name", "Ama Mensah")
        page.dispatch_event("#name", "input")
        drawn = page.evaluate("""() => {
            const g = document.getElementById('c').getContext('2d');
            const d = g.getImageData(80, 1080, 720, 80).data;
            let dark = 0;
            for (let i = 0; i < d.length; i += 4) if (d[i] < 120 && d[i+1] < 120 && d[i+2] < 140) dark++;
            return dark;
        }""")
        check(drawn > 400, "the name is painted on the card", f"{drawn} dark px")
        fit = page.evaluate("""() => {
            const g = document.getElementById('c').getContext('2d');
            const nm = 'W'.repeat(26);
            let size = CARD.nameSize;
            do {
              g.letterSpacing = (size * 0.05).toFixed(2) + 'px';
              g.font = `900 ${size}px "Fira Sans"`;
              if (g.measureText(nm).width <= CARD.nameBox) break;
              size -= 2;
            } while (size > 26);
            const w = g.measureText(nm).width; g.letterSpacing = '0px';
            return {size, w, box: CARD.nameBox};
        }""")
        check(fit["w"] <= fit["box"], "a 26-character name still fits the text column", str(fit))
        check(fit["size"] >= 26, "the name never shrinks past 26px", str(fit))
        check(page.evaluate("document.getElementById('name').maxLength") == 26, "name input capped at 26")

        print("card art")
        art = np.array(Image.open(ROOT / "assets" / "layer-participant.png").convert("RGB")).astype(int)
        band = art[1206:1264]
        inks = ((band.min(axis=2) < 235) | ((band.max(axis=2) - band.min(axis=2)) > 40)).any(axis=0)
        xs = np.where(inks)[0]
        runs, start, prev = 0, xs[0], xs[0]
        for x in xs[1:]:
            if x - prev > 10:
                runs += 1
            prev = x
        runs += 1
        check(runs == 10, "the baked card art carries ten logos", f"{runs} marks")
        check(xs.min() >= 79 and xs.max() <= 1000, "the card strip stays inside the 80px margins",
              f"{xs.min()}-{xs.max()}")

        print("photo")
        src = photo(TMP / "test-photo.jpg")
        page.set_input_files("#file", str(src))
        page.wait_for_function("!document.getElementById('dl').disabled")
        check(not page.is_disabled("#zoom") and not page.is_disabled("#fit"), "controls unlock once a photo is in")
        check(page.evaluate("+document.getElementById('zoom').value") > 0, "zoom slider sits on the fit scale")
        edge = page.evaluate("""() => {
            const pts = [];
            for (let i = 0; i < 16; i++) {
              const a = i * Math.PI / 8;
              pts.push([CARD.cx + Math.cos(a) * (CARD.r - 2), CARD.cy + Math.sin(a) * (CARD.r - 2)]);
            }
            return pts;
        }""")
        check(not wrong_pixels(page, edge), "the photo covers the whole circle after fitting",
              str(wrong_pixels(page, edge)[:2]))

        # drag hard and make sure the circle can never show through
        box = page.locator("#c").bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] / 2 + 600, box["y"] + box["height"] / 2 + 600, steps=8)
        page.mouse.up()
        check(not wrong_pixels(page, edge), "dragging cannot pull the photo off the circle",
              str(wrong_pixels(page, edge)[:2]))
        page.click("#fit")
        check(not wrong_pixels(page, edge), "fit to circle restores coverage")

        print("download")
        with page.expect_download() as dl_info:
            page.click("#dl")
        dl = dl_info.value
        out = TMP / "downloaded-card.png"
        dl.save_as(str(out))
        card = Image.open(out)
        check(card.size == (1080, 1350), "download is 1080 x 1350", str(card.size))
        check(card.format == "PNG", "download is a PNG", card.format)
        check(dl.suggested_filename == "SpaceAppsKumasi-participant-Ama-Mensah.png", "download file name",
              dl.suggested_filename)
        arr = np.array(card.convert("RGB"))
        check(arr[720 - 250 + 3, 540 - 250 + 3].tolist() != [237, 242, 252], "card photo is baked into the PNG")

        print("bad file")
        bad = TMP / "not-a-photo.png"
        bad.write_bytes(b"this is not an image")
        page.set_input_files("#file", str(bad))
        page.wait_for_selector("#err:not([hidden])", timeout=3000)
        check(page.is_visible("#err"), "an unreadable file shows a message")
        check("could not be opened" in page.inner_text("#err"), "the message says what went wrong")
        page.set_input_files("#file", str(src))
        page.wait_for_function("document.getElementById('err').hidden")
        check(not page.is_visible("#err"), "the message clears on the next good photo")

        # ------------------------------------------------------------- phone
        print("phone 360 x 740")
        phone = b.new_page(viewport={"width": 360, "height": 740}, accept_downloads=True)
        plog = hook_errors(phone)
        load(phone, base)
        phone.screenshot(path=str(shot / "phone.png"), full_page=True)
        check(not plog["pageerror"] and not plog["console"], "no console errors on phone",
              str(plog["pageerror"] + plog["console"]))
        overflow = phone.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        check(overflow <= 1, "no horizontal overflow", f"{overflow}px")
        check(phone.evaluate("getComputedStyle(document.querySelector('.logos')).gridTemplateColumns.split(' ').length") == 2,
              "two logos per row on phone")
        check(phone.is_visible("#c") and phone.is_visible(".file"), "canvas and photo button are on screen")
        r = phone.evaluate("""() => {
            const b = document.getElementById('dl').getBoundingClientRect();
            return {left: b.left, right: b.right, w: b.width};
        }""")
        check(r["left"] >= 0 and r["right"] <= 360 and r["w"] > 100, "download button fits the phone width", str(r))

        print("width sweep")
        for w in (320, 414, 600, 768, 900, 1024, 1440, 1920):
            page.set_viewport_size({"width": w, "height": 900})
            page.wait_for_timeout(60)
            over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            cols = page.evaluate("getComputedStyle(document.querySelector('.logos')).gridTemplateColumns.split(' ').length")
            want = 2 if w <= 600 else 5
            rows = page.evaluate("""() => getComputedStyle(document.querySelector('.logos'))
                .gridTemplateRows.split(' ').filter(Boolean).length""")
            check(over <= 1, f"{w}px: no horizontal overflow", f"{over}px")
            check(cols == want, f"{w}px: {want} logos per row", str(cols))
            check(rows == (10 + want - 1) // want, f"{w}px: strip wraps to {rows} rows", str(rows))
        page.set_viewport_size({"width": 1366, "height": 900})

        # --------------------------------------------------------- share path
        print("share supported")
        ctx = b.new_context(viewport={"width": 1366, "height": 900})
        ctx.add_init_script("""
            Object.defineProperty(navigator, 'canShare', {value: () => true});
            Object.defineProperty(navigator, 'share', {value: d => { window.__shared = d; return Promise.resolve(); }});
        """)
        sp = ctx.new_page()
        slog = hook_errors(sp)
        load(sp, base)
        check(sp.is_visible("#share"), "share button shows when the browser can share files")
        sp.set_input_files("#file", str(src))
        sp.wait_for_function("!document.getElementById('dl').disabled")
        sp.click("#share")
        sp.wait_for_timeout(400)
        shared = sp.evaluate("""() => window.__shared ? {
            n: window.__shared.files.length, type: window.__shared.files[0].type,
            text: (window.__shared.text || '').slice(0, 40)
        } : null""")
        check(shared is not None and shared["n"] == 1 and shared["type"] == "image/png",
              "share hands over one PNG file", str(shared))
        check(not slog["pageerror"] and not slog["console"], "no errors on the share path",
              str(slog["pageerror"] + slog["console"]))

        print("share probe that throws")
        ctx2 = b.new_context(viewport={"width": 1366, "height": 900})
        ctx2.add_init_script("Object.defineProperty(navigator, 'canShare', {value: () => { throw new Error('nope'); }});")
        tp = ctx2.new_page()
        tlog = hook_errors(tp)
        load(tp, base)
        check(not tp.is_visible("#share"), "share stays hidden when the probe throws")
        check(not tlog["pageerror"], "a throwing canShare does not break the page", str(tlog["pageerror"]))
        tp.set_input_files("#file", str(src))
        tp.wait_for_function("!document.getElementById('dl').disabled")
        check(not tp.is_disabled("#dl"), "download still works after a throwing probe")

        b.close()
    httpd.shutdown()

    print()
    if fails:
        print(f"{len(fails)} failed: " + "; ".join(fails))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
