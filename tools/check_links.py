"""Kontrollerar att varje intern adress i de byggda sidorna pekar på en fil.

Adresserna är relativa till sidan de står i, så att sajten fungerar både på
domänroten och i en underkatalog. Därför löses varje länk mot sin egen fils
katalog - inte mot projektroten.

    python3 tools/check_links.py        # avslutar med 1 om något är brutet
"""
import glob
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOPPA_ÖVER = ('pages/', 'tools/', 'content/', '_site/')
EXTERNT = ('http://', 'https://', 'mailto:', 'tel:', '#', 'data:', '//')


def sidor():
    for path in sorted(glob.glob(os.path.join(ROOT, '**', '*.html'), recursive=True)):
        rel = os.path.relpath(path, ROOT)
        if not rel.startswith(HOPPA_ÖVER):
            yield rel


def finns(mål):
    return any(os.path.exists(os.path.join(ROOT, kandidat))
               for kandidat in (mål, mål + '.html', os.path.join(mål, 'index.html')))


def main():
    brutna, kontrollerade = [], 0
    for rel in sidor():
        with open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
            html = fh.read()
        for m in re.finditer(r'(?:href|src)="([^"]+)"', html):
            adress = m.group(1)
            if adress.startswith(EXTERNT):
                continue
            # frågesträng (?v=hash) och ankare hör inte till filnamnet
            ren = urllib.parse.unquote(adress.split('?')[0].split('#')[0])
            if not ren:
                continue
            kontrollerade += 1
            mål = os.path.normpath(os.path.join(os.path.dirname(rel), ren))
            if not finns(mål):
                brutna.append((rel, adress))

    print(f'{len(list(sidor()))} sidor, {kontrollerade} interna adresser')
    for rel, adress in brutna:
        print(f'  BRUTEN  {rel} -> {adress}')
    if brutna:
        print(f'{len(brutna)} brutna länkar')
        return 1
    print('inga brutna länkar')
    return 0


if __name__ == '__main__':
    sys.exit(main())
