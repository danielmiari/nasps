"""Hämtar produktsidornas specifikationstabeller från den publicerade sajten.

Framer-exporten innehåller bara den storlek som var server-renderad; resten
ritas av embed-koden i webbläsaren och följde därför aldrig med. Det här
skriptet öppnar sidorna, klickar igenom varje storleksflik och sparar den
renderade markupen per flik.

    python3 tools/scrape_specs.py        # -> tools/extracted/specs.json

Körs sällan - bara om tabellerna ändras på nasps.se.
"""
import asyncio
import json
import os
import sys

from playwright.async_api import async_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://www.nasps.se/'
SIDOR = ['product-r-thread', 'product-t-thread']

# Flikarna ligger i .tdt-tabs; allt övrigt i roten är sektionerna för den
# valda storleken.
PANEL = """() => {
  const root = document.querySelector('.tdt-root');
  return [...root.children]
      .filter(el => !el.classList.contains('tdt-tabs'))
      .map(el => el.outerHTML)
      .join('');
}"""


async def scrape(page, sida):
    await page.goto(SITE + sida, wait_until='networkidle', timeout=60000)
    await page.wait_for_selector('.tdt-root', timeout=30000)
    await page.wait_for_timeout(2000)

    etiketter = await page.eval_on_selector_all(
        '.tdt-tabs .tdt-tab', '(els) => els.map(e => e.textContent.trim())')
    flikar = {}
    for i, etikett in enumerate(etiketter):
        await page.eval_on_selector_all(
            '.tdt-tabs .tdt-tab', '(els, i) => els[i].click()', i)
        await page.wait_for_timeout(500)
        html = await page.evaluate(PANEL)
        rader = html.count('<tr')
        flikar[etikett] = html
        print(f'  {etikett:6} {rader:3} rader, {len(html) // 1024} kB')
    return flikar


async def main():
    ut = {}
    async with async_playwright() as p:
        webbläsare = await p.chromium.launch()
        sida = await webbläsare.new_page(viewport={'width': 1440, 'height': 900})
        for namn in SIDOR:
            print(namn)
            ut[namn] = await scrape(sida, namn)
        await webbläsare.close()

    mål = os.path.join(ROOT, 'tools', 'extracted', 'specs.json')
    with open(mål, 'w', encoding='utf-8') as fh:
        json.dump(ut, fh, indent=1, ensure_ascii=False)
    print(f'\n{sum(len(v) for v in ut.values())} flikar sparade i {mål}')


if __name__ == '__main__':
    asyncio.run(main())
