# Participant attendance card maker

For participants of NASA Space Apps Kumasi 2026 (14 and 15 November, KNUST).

Open https://phidlarkson.github.io/spaceapps-kumasi-participants/, choose a photo, fit your face in the circle, type your name, and download the card as a 1080 × 1350 feed post.

Photos are processed in the browser only. Nothing is uploaded.

This is the participant edition. The volunteer card maker is a separate site:
https://phidlarkson.github.io/spaceapps-kumasi-volunteer/

## How it is built

White card on the 2026 brand guide. The photo leads: a 500px circle on the centre
axis inside a Navy holding ring and one Electric Blue orbit ring, with a single Neon
Yellow planet. Above it the statement "See you at the NASA Space Apps Kumasi" in Fira
Sans Black; below it the name, the role label and the eight collaborators in a single row. No build step is needed to publish: the site is plain HTML.

| File | What it is |
|---|---|
| `index.html` | The whole app: page, CSS, canvas logic |
| `assets/layer-participant.png` | The static card art (header, orbits, role label, collaborator rows, foot band) |
| `tools/layer.html` | Source for that art |
| `tools/build_layer.py` | Renders `layer.html` → `assets/layer-participant.png` |
| `tools/preview.html`, `tools/build_preview.py` | The 1200 × 630 social preview |
| `tools/serve.py` | Local server with live reload |

The canvas draws the photo and the name on top of `layer-participant.png`. To change
anything static on the card, edit `tools/layer.html` and run:

```
python3 tools/build_layer.py
```

To work locally with live reload:

```
python3 tools/serve.py
```

then open http://127.0.0.1:8123/. The page reloads on save.

## Colours

| Name | Hex | Use |
|---|---|---|
| Deep Blue | `#07173F` | Name, body type |
| Electric Blue | `#0042A6` | Orbits, rules, eyebrows |
| Neon Blue | `#0960E1` | Foot band, links |
| Neon Yellow | `#EAFE07` | The participant chip and buttons |
| Slate | `#4A5878` | Secondary text |

## Credits

Fira Sans and Overpass, per the NASA Space Apps brand guide. Collaborator logos
belong to their respective organisations.

An official local edition of the NASA Space Apps Challenge, run in Kumasi by the
local host team.
