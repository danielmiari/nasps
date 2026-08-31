"""Tar bort vit bakgrund och mjuk slagskugga ur en produktbild.

    python3 tools/cutout.py bild.png ut.png [min_lum] [max_sat]

Standardvärdena 210/20 är inställda för produktrenderingarna i assets/images.
Högre min_lum sparar mer av skuggan, lägre börjar äta av metallen.

Bakgrunden hittas som den sammanhängande ljusa, färglösa ytan som når
bildkanten. Reflexer inuti produkten rörs inte, eftersom de inte hänger ihop
med kanten. Kanten mjukas upp och den vita inblandningen räknas bort så att
bilden inte får någon ljus kantlinje mot sidbakgrunden.
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

src, dst = sys.argv[1], sys.argv[2]
min_lum = float(sys.argv[3]) if len(sys.argv) > 3 else 225.0   # så mörk får bakgrunden bli
max_sat = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0    # bakgrunden är färglös

im = Image.open(src).convert('RGB')
w, h = im.size
rgb = np.asarray(im).astype(np.float32)

lum = rgb.mean(axis=2)
sat = rgb.max(axis=2) - rgb.min(axis=2)
eligible = (lum >= min_lum) & (sat <= max_sat)

# Sammanhängande ljus yta som når bildkanten = bakgrund + slagskugga
# .copy() ger bilden en egen buffert - annars delar den minne med numpy-
# arrayen och fyllningen syns inte när vi läser tillbaka den.
marker = Image.fromarray(np.where(eligible, 255, 0).astype('uint8')).copy()
for x in range(0, w, 4):
    for y in (0, h - 1):
        if marker.getpixel((x, y)) == 255:
            ImageDraw.floodfill(marker, (x, y), 128, thresh=0)
for y in range(0, h, 4):
    for x in (0, w - 1):
        if marker.getpixel((x, y)) == 255:
            ImageDraw.floodfill(marker, (x, y), 128, thresh=0)
background = np.array(marker) == 128

alpha = Image.fromarray(np.where(background, 0, 255).astype('uint8'))
alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))
a = np.asarray(alpha).astype(np.float32) / 255.0

# C = a*F + (1-a)*vitt  ->  F = (C - (1-a)*255) / a
edge = (a > 0.02) & (a < 0.98)
recovered = (rgb - (1.0 - a)[..., None] * 255.0) / np.maximum(a, 0.02)[..., None]
rgb = np.where(edge[..., None], np.clip(recovered, 0, 255), rgb)

out = Image.fromarray(np.dstack([rgb, a * 255.0]).astype('uint8'), 'RGBA')
# Palett-PNG som de övriga produktbilderna: ungefär en fjärdedel av storleken
# mot RGBA, och de mjuka kanterna klarar sig.
out.quantize(colors=255, method=Image.Quantize.FASTOCTREE).save(dst, optimize=True)
print(f'{dst.split("/")[-1]}: {w}x{h}, {(a > 0.5).mean() * 100:.1f}% behållet')
