"""Draw the saved picks on top of the thumbnail so we can compare with the
canvas overlay rendered by the React PP tab. Run after the playwright test
has written image-thumbnail.png and report.json.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw

SHOTS = Path(__file__).parent / 'screenshots' / 'topaz-00018ex'
thumb_path = SHOTS / 'image-thumbnail.png'
report_path = SHOTS / 'report.json'

if not thumb_path.exists():
    raise SystemExit(f'missing {thumb_path}')
if not report_path.exists():
    raise SystemExit(f'missing {report_path}')

report = json.loads(report_path.read_text())
particles = report['sample_coords']  # only have 8 here — we want them all.
# Need full coords — re-fetch from the API. The report only carries a sample.
# So fetch from backend if available.

import urllib.request
import os

# Pull full data_json from the backend
api = 'http://127.0.0.1:8000'
img = report['image']['name']
import urllib.parse
url = f"{api}/web/particle-pickings?img_name={urllib.parse.quote(img)}"
# Need auth — read token written by test if present, else login.
def login():
    req = urllib.request.Request(
        f"{api}/auth/login",
        data=json.dumps({
            'username': os.environ.get('MAGELLON_E2E_USERNAME', 'super'),
            'password': os.environ.get('MAGELLON_E2E_PASSWORD', ''),
        }).encode(),
        headers={'Content-Type': 'application/json'},
    )
    return json.loads(urllib.request.urlopen(req).read())['access_token']

token = login()
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
ipps = json.loads(urllib.request.urlopen(req).read())
# Latest IPP
ipp = sorted(ipps, key=lambda i: i.get('name', ''), reverse=True)[0]
picks = ipp.get('data_json') or []
print(f'using ipp={ipp["name"]} with {len(picks)} picks')

img_pil = Image.open(thumb_path).convert('RGBA')
W, H = img_pil.size
print(f'thumbnail size: {W} x {H}')

# Bbox of picks
xs = [p['x'] for p in picks]
ys = [p['y'] for p in picks]
print(f'pick bbox: x [{min(xs):.0f}, {max(xs):.0f}], y [{min(ys):.0f}, {max(ys):.0f}]')

# Picks are in raw MRC pixel space (~4096 x 4096). Need to scale to thumbnail.
# The frontend's canvas sizes its viewBox to the same coord space (imageShape),
# so the overlay alignment in the UI depends on imageShape being correct.
# Here we assume the thumbnail is a uniform scaling of the MRC.
mrc_w = max(xs) * 1.02 + 50
mrc_h = max(ys) * 1.02 + 50
sx = W / mrc_w
sy = H / mrc_h
print(f'assumed mrc dims: {mrc_w:.0f} x {mrc_h:.0f} -> scale {sx:.3f}, {sy:.3f}')

overlay = Image.new('RGBA', img_pil.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)
r = 10
for p in picks:
    cx = p['x'] * sx
    cy = p['y'] * sy
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 255, 64, 220), width=2)

out = Image.alpha_composite(img_pil, overlay)
out_path = SHOTS / 'server-side-overlay.png'
out.convert('RGB').save(out_path)
print(f'wrote {out_path}')
