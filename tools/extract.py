"""Plockar ut innehållet ur Framer-exporten till JSON, en fil per sida.

Framer-sidorna SSR:ar samma innehåll en gång per brytpunkt. Vi behåller
desktop-varianten och slänger dubbletterna, och normaliserar rich text till
enkel HTML med semantiska klasser i stället för Framers hash-klasser.
"""
import html as htmlmod
import json, os, re, sys
from html.parser import HTMLParser

VOID = {'img','br','hr','meta','link','input','source','area','base','col','embed','param','track','wbr'}

# Framer-preset -> typografiklass i styles.css
PRESET = {
    '1iog5to': 'display', 'drdd5w': 'h4', '10qv1f6': 'h2', '1xhbru0': 'h3', '1tgbta8': 'h5', 'bf21uk': 'h6',
    '1ywtv7i': 'h6-sm', 'q4tobg': 'body', '194jgn1': 'sm', '1g3leso': 'xs',
    'e1xwg7': 'eyebrow', 'bh6wo5': 'nav', 'szp8ro': 'link',
}

KEEP_TAGS = {'p','h1','h2','h3','h4','h5','h6','ul','ol','li','strong','em','br','a','table','thead','tbody','tr','th','td','span','div','svg','path','rect','circle','polygon','button','style'}


class Node:
    def __init__(self, tag, attrs=None):
        self.tag, self.attrs, self.kids, self.text = tag, dict(attrs or []), [], ''


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('root'); self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs); self.stack[-1].kids.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].kids.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data.strip():
            n = Node('#text'); n.text = data; self.stack[-1].kids.append(n)


VIEWPORT = 1440  # bredden vi betraktar som "desktop"


def desktop_hash(html):
    """Hashen för den brytpunktsvariant som gäller vid VIEWPORT.

    Framer genererar olika brytpunkter per sida, så vi kan inte leta efter
    en fast bredd - vi väljer den variant vars media query matchar.
    """
    m = re.search(r'data-framer-hydrate-v2="([^"]*)"', html)
    if not m:
        return None
    data = json.loads(m.group(1).replace('&quot;', '"').replace('&amp;', '&'))
    for bp in data.get('breakpoints', []):
        q = bp.get('mediaQuery', '')
        lo = re.search(r'min-width:\s*([\d.]+)px', q)
        hi = re.search(r'max-width:\s*([\d.]+)px', q)
        if (not lo or VIEWPORT >= float(lo.group(1))) and (not hi or VIEWPORT <= float(hi.group(1))):
            return bp['hash']
    return None


def hidden_on_desktop(node, dhash):
    cls = node.attrs.get('class', '')
    return 'ssr-variant' in cls and dhash and f'hidden-{dhash}' in cls


def esc(s):
    # Hårda mellanslag i källtexten hindrar radbrytning på små skärmar.
    s = s.replace('\xa0', ' ')
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def rich(node):
    """Serialiserar en RichTextContainer till enkel HTML."""
    out = []
    for k in node.kids:
        if k.tag == '#text':
            out.append(esc(k.text))
        elif k.tag == 'br':
            out.append('<br>')
        elif k.tag in ('strong', 'em', 'b', 'i'):
            out.append(f'<{k.tag}>{rich(k)}</{k.tag}>')
        elif k.tag == 'a':
            href = k.attrs.get('href', '')
            out.append(f'<a href="{href}">{rich(k)}</a>')
        elif k.tag in ('ul', 'ol', 'li'):
            out.append(f'<{k.tag}>{rich(k)}</{k.tag}>')
        else:
            out.append(rich(k))
    return ''.join(out).strip()


SVG_CASED = {'viewbox': 'viewBox', 'preserveaspectratio': 'preserveAspectRatio',
             'strokewidth': 'stroke-width'}


def raw(node, in_style=False):
    """Serialiserar ett nod-träd rakt av (för HTML-embeds)."""
    if node.tag == '#text':
        return htmlmod.unescape(node.text) if in_style else esc(node.text)
    inner = ''.join(raw(k, in_style or node.tag == 'style') for k in node.kids)
    if node.tag == 'root':
        return inner
    keep = ('class', 'colspan', 'rowspan', 'viewbox', 'x', 'y', 'width', 'height', 'rx',
            'ry', 'cx', 'cy', 'r', 'points', 'd', 'fill', 'opacity', 'stroke',
            'stroke-width', 'stroke-linecap', 'stroke-linejoin', 'type', 'data-size')
    attrs = ''.join(f' {SVG_CASED.get(k, k)}="{v}"'
                    for k, v in node.attrs.items() if v is not None and k in keep)
    if node.tag in VOID:
        return f'<{node.tag}{attrs}>'
    return f'<{node.tag}{attrs}>{inner}</{node.tag}>'


def walk(node, dhash, out):
    if hidden_on_desktop(node, dhash):
        return
    cls = node.attrs.get('class', '')
    name = node.attrs.get('data-framer-name')

    if node.attrs.get('data-framer-component-type') == 'RichTextContainer':
        for k in node.kids:
            if k.tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol'):
                preset = ''
                m = re.search(r'framer-styles-preset-([a-z0-9]+)', k.attrs.get('class', ''))
                if m:
                    preset = PRESET.get(m.group(1), m.group(1))
                html = rich(k)
                if html:
                    out.append({'type': 'text', 'tag': k.tag, 'style': preset, 'html': html})
        return

    # YouTube-inbäddning (Framers lite-embed: bild + dold iframe)
    if node.tag == 'article':
        frames = [k for k in walkall(node) if k.tag == 'iframe' and 'youtube' in (k.attrs.get('src') or '')]
        if frames:
            vid = re.search(r'/embed/([\w-]+)', frames[0].attrs['src'])
            thumb = next((k.attrs.get('src') for k in walkall(node) if k.tag == 'img'), '')
            out.append({'type': 'video', 'id': vid.group(1) if vid else '',
                        'thumb': thumb, 'src': frames[0].attrs['src']})
            return

    if node.tag == 'img':
        src = node.attrs.get('src', '')
        if src:
            src = src.split('?')[0].replace('https://framerusercontent.com/images/', 'assets/images/')
            out.append({'type': 'image', 'src': src,
                        'w': node.attrs.get('width'), 'h': node.attrs.get('height'),
                        'alt': node.attrs.get('alt') or ''})
        return

    # HTML-embed (egna tabellkomponenter på produktsidorna). Komponentens
    # <style> ligger som syskon till rot-diven, så vi tar hela behållaren.
    if any(re.search(r'\b(tdt|ct|cv|ss|sa)-root\b', k.attrs.get('class', '')) for k in node.kids):
        out.append({'type': 'embed', 'html': ''.join(raw(k) for k in node.kids)})
        return

    if node.tag == 'a' and node.attrs.get('href'):
        kids = []
        for k in node.kids:
            walk(k, dhash, kids)
        out.append({'type': 'link', 'href': node.attrs['href'], 'name': name,
                    'label': ' '.join(texts(node)), 'children': dedupe(kids)})
        return

    if name:
        out.append({'type': 'begin', 'name': name})
    for k in node.kids:
        walk(k, dhash, out)
    if name:
        out.append({'type': 'end', 'name': name})


def walkall(node):
    for k in node.kids:
        yield k
        yield from walkall(k)


def texts(node):
    if node.tag == '#text':
        t = ' '.join(node.text.split())
        if t:
            yield t
        return
    for k in node.kids:
        yield from texts(k)


def dedupe(blocks):
    """Slänger de brytpunktsdubbletter Framer SSR:ar (Desktop/Tablet/Phone)."""
    out, seen, i = [], set(), 0
    while i < len(blocks):
        b = blocks[i]
        if b['type'] == 'begin':
            depth, j = 1, i + 1
            while j < len(blocks) and depth:
                if blocks[j]['type'] == 'begin':
                    depth += 1
                elif blocks[j]['type'] == 'end':
                    depth -= 1
                j += 1
            chunk = blocks[i:j]
            key = json.dumps([c for c in chunk if c['type'] != 'begin' and c['type'] != 'end'], sort_keys=True)
            if key != '[]' and key in seen:
                i = j
                continue
            seen.add(key)
            out.append(b)
            out.extend(dedupe(blocks[i + 1:j - 1]))
            out.append(blocks[j - 1])
            i = j
        else:
            key = json.dumps(b, sort_keys=True)
            if key not in seen or b['type'] == 'image':
                seen.add(key)
                out.append(b)
            i += 1
    return out


def extract(path):
    html = open(path, encoding='utf-8').read()
    dhash = desktop_hash(html)
    start = html.find('<div data-framer-root')
    end = html.rfind('</body>')
    t = Tree(); t.feed(html[start:end])
    blocks = []
    walk(t.root, dhash, blocks)
    return dedupe(blocks)


if __name__ == '__main__':
    os.makedirs('tools/extracted', exist_ok=True)
    for path in sys.argv[1:]:
        page = os.path.basename(path)[:-5]
        data = extract(path)
        json.dump(data, open(f'tools/extracted/{page}.json', 'w'), indent=1, ensure_ascii=False)
        print(f'{page}: {len(data)} block')
