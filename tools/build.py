"""Bygger de statiska sidorna från innehållet i tools/extracted/.

Innehållet kommer ordagrant från Framer-exporten (se extract.py), men
markupen är handskriven och delas mellan sidorna: samma sidhuvud, sidfot,
knappar och typografi överallt.

    python3 tools/extract.py pages/*.html   # innehåll -> tools/extracted/
    python3 tools/build.py                  # sidor -> *.html
"""
import hashlib
import json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tools', 'extracted')

LOGO = 'assets/images/pyaDngF6J38whdYhhBSMKD5Qug.png'

NAV = [('Home', '/'), ('About us', '/about'), ('Products', '/products'), ('Project', '/project')]

FOOTER_LINKS = [
    ('Links', [('Home', '/'), ('About', '/about'), ('Services', '/products')]),
    ('Support', [('Contact us', '/contact'), ('News', '/blog')]),
]

ARROW = ('<svg viewBox="0 0 16 16" fill="none" aria-hidden="true">'
         '<path d="M4.5 11.5 11.5 4.5M11.5 4.5H5.5M11.5 4.5v6" stroke="currentColor" '
         'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')


# --------------------------------------------------------------------------
# Hjälpare för det extraherade innehållet
# --------------------------------------------------------------------------

def load(page):
    with open(os.path.join(SRC, page + '.json'), encoding='utf-8') as fh:
        return json.load(fh)


def walk(blocks):
    """Går igenom alla block, även de som ligger inuti länkar."""
    for b in blocks:
        yield b
        if b['type'] == 'link':
            yield from walk(b.get('children', []))


def section(blocks, name, nth=0):
    """Blocken inuti den n:te sektionen med angivet Framer-namn."""
    hits = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b['type'] == 'begin' and b['name'] == name:
            depth, j = 1, i + 1
            while j < len(blocks) and depth:
                if blocks[j]['type'] == 'begin':
                    depth += 1
                elif blocks[j]['type'] == 'end':
                    depth -= 1
                j += 1
            hits.append(blocks[i + 1:j - 1])
            i = j
            continue
        if b['type'] == 'link':
            hits.extend(section(b.get('children', []), name))
        i += 1
    if len(hits) > nth:
        return hits[nth]
    # leta rekursivt en nivå ner
    for b in blocks:
        if b['type'] == 'begin':
            continue
    return []


def section_before(blocks, anchor, name):
    """Den sista gruppen `name` som börjar före gruppen `anchor`.

    Rubriken till ett block ligger strax före blocket självt. Att bara ta
    första träffen på sidan ger fel grupp när samma namn används flera gånger.
    """
    stop = next((i for i, b in enumerate(blocks)
                 if b['type'] == 'begin' and b['name'] == anchor), len(blocks))
    found, i = [], 0
    while i < stop:
        b = blocks[i]
        if b['type'] == 'begin' and b['name'] == name:
            depth, j = 1, i + 1
            while j < len(blocks) and depth:
                if blocks[j]['type'] == 'begin':
                    depth += 1
                elif blocks[j]['type'] == 'end':
                    depth -= 1
                j += 1
            found.append(blocks[i + 1:j - 1])
        i += 1
    return found[-1] if found else []


def deep_section(blocks, *names):
    cur = blocks
    for n in names:
        cur = section(cur, n)
    return cur


def texts(blocks):
    return [b for b in walk(blocks) if b['type'] == 'text']


def images(blocks):
    return [b for b in walk(blocks) if b['type'] == 'image']


def embeds(blocks):
    return [b for b in walk(blocks) if b['type'] == 'embed']


def repeat_blocks(blocks, name):
    """Alla syskonblock med angivet namn, var och en som en egen lista."""
    out, i = [], 0
    while i < len(blocks):
        if blocks[i]['type'] == 'begin' and blocks[i]['name'] == name:
            depth, j = 1, i + 1
            while j < len(blocks) and depth:
                if blocks[j]['type'] == 'begin':
                    depth += 1
                elif blocks[j]['type'] == 'end':
                    depth -= 1
                j += 1
            out.append(blocks[i + 1:j - 1])
            i = j
            continue
        i += 1
    return out


def body(blocks):
    """Sidans innehåll: allt mellan sidhuvudet och sidfoten."""
    out, depth, started = [], 0, False
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b['type'] == 'begin' and b['name'] == 'Spacer' and not started:
            started = True
            i += 1
            continue
        if not started:
            i += 1
            continue
        if b['type'] == 'begin' and b['name'] in ('Desktop', 'No Padding'):
            depth, j = 1, i + 1
            while j < len(blocks) and depth:
                if blocks[j]['type'] == 'begin':
                    depth += 1
                elif blocks[j]['type'] == 'end':
                    depth -= 1
                j += 1
            i = j
            continue
        out.append(b)
        i += 1
    return out


# --------------------------------------------------------------------------
# Byggstenar
# --------------------------------------------------------------------------

def version(path):
    """Kort innehållshash till fil-URL:er.

    Utan den kan en webbläsare para ihop ny HTML med gammal cachad CSS eller JS,
    och då går layouten sönder på sätt som inte syns i källkoden.
    """
    with open(os.path.join(ROOT, path), 'rb') as fh:
        return hashlib.sha1(fh.read()).hexdigest()[:8]


def asset(src):
    """Rotrelativ sökväg för lokala filer, externa URL:er lämnas orörda."""
    return src if src.startswith(('http://', 'https://', '//')) else '/' + src


def esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def btn(label, href, variant='', block=False, icon=True):
    cls = 'btn'
    if variant:
        cls += f' btn--{variant}'
    if block:
        cls += ' btn--block'
    icon_html = f'<span class="btn__icon">{ARROW}</span>' if icon else ''
    return (f'<a class="{cls}" href="{href}">'
            f'<span class="btn__label t-eyebrow">{label}</span>{icon_html}</a>')


def header_html(current):
    items = []
    for label, href in NAV:
        aria = ' aria-current="page"' if href == current else ''
        items.append(f'<a class="t-nav" href="{href}"{aria}>{label}</a>')
    return f'''  <header class="site-header" data-open="false">
    <div class="site-header__inner">
      <a class="site-logo" href="/" aria-label="NASPS">
        <img src="/{LOGO}" width="2421" height="510" alt="NASPS — Nordic Anchor &amp; Steel Pile Supply AB">
      </a>
      <button class="nav-toggle" type="button" aria-label="Menu" aria-expanded="false">
        <span></span><span></span><span></span>
      </button>
      <nav class="site-nav" aria-label="Main">
        {chr(10).join("        " + i for i in items).strip()}
      </nav>
      <a class="btn btn--boxed" href="/contact">
        <span class="btn__swap t-eyebrow"><span>Contact us</span><span aria-hidden="true">Contact us</span></span>
      </a>
    </div>
    <div class="rule site-header__rule"></div>
  </header>'''


def footer_html():
    cols = []
    for title, links in FOOTER_LINKS:
        items = ''.join(f'<li><a class="t-sm" href="{h}">{l}</a></li>' for l, h in links)
        cols.append(f'''<div class="site-footer__widget">
            <h2 class="t-h6-sm">{title}</h2>
            <ul>{items}</ul>
          </div>''')
    return f'''  <footer class="site-footer">
    <div class="site-footer__inner">
      <div class="rule"></div>
      <div class="site-footer__main">
        <div class="site-footer__brand">
          <a class="site-logo" href="/" aria-label="NASPS">
            <img src="/{LOGO}" width="2421" height="510" alt="NASPS — Nordic Anchor &amp; Steel Pile Supply AB">
          </a>
          {btn('Drop us a line', '/contact')}
        </div>
        <div class="site-footer__links">
          {''.join(cols)}
        </div>
      </div>
      <div class="rule"></div>
      <p class="t-sm">Copyright: © 2026 NASPS. All Rights Reserved.</p>
    </div>
  </footer>'''


def cta_html(blocks):
    """Den mörka kontaktsektionen längst ned på sidan."""
    cta = section(blocks, 'CTA')
    if not cta:
        return ''
    img = images(cta)
    src = asset(img[0]['src']) if img else ''
    tx = texts(cta)
    kicker = tx[0]['html'] if tx else 'Get in Touch with NASPS'
    heading = tx[1]['html'] if len(tx) > 1 else ''
    lead = tx[2]['html'] if len(tx) > 2 else ''
    lead_html = f'<p class="t-body">{lead}</p>' if lead else ''
    return f'''  <section class="band">
    <div class="band__frame" data-parallax>
      <img class="band__bg" src="{src}" alt="" loading="lazy">
    </div>
    <div class="band__cover">
      <div class="band__inner">
        <div class="cta__title">
          <p class="t-body">{kicker}</p>
          <h2 class="t-h2">{heading}</h2>
          {lead_html}
        </div>
        {btn('Drop us a line', '/contact', variant='red')}
      </div>
    </div>
  </section>'''


def wrap_tables(html):
    """Tabellerna i produktkomponenterna får en scrollbar behållare på små skärmar."""
    return re.sub(r'(<table\b.*?</table>)', r'<div class="table-scroll">\1</div>', html, flags=re.S)


def video_html(blk):
    """YouTube-fasad: miniatyr som byts mot en iframe först vid klick."""
    return f'''<div class="video" data-video="{blk['id']}">
          <img src="{blk['thumb']}" alt="" loading="lazy">
          <button class="video__play" type="button" aria-label="Play video">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5z" fill="currentColor"/></svg>
          </button>
        </div>'''


def eyebrow(block, light=False):
    """Rubriketiketten med prickmarkör. Behåller källans typografiklass."""
    if isinstance(block, dict):
        label, style = block['html'], 't-' + block['style']
    else:
        label, style = block, 't-eyebrow'
    cls = 'eyebrow eyebrow--light' if light else 'eyebrow'
    return f'<p class="{cls} {style}"><span class="eyebrow__dot"></span>{label}</p>'


def page_head(kicker, heading, paragraphs, level='t-h2', tag='h1', center=False, button=None):
    cls = 'page-head page-head--center' if center else 'page-head'
    parts = [f'<div class="{cls}">', '<div class="page-head__title">']
    if kicker:
        parts.append(eyebrow(kicker))
    parts.append(f'<{tag} class="{level}">{heading}</{tag}>')
    parts.append('</div>')
    for p in paragraphs:
        parts.append(f'<p class="t-body">{p}</p>')
    if button:
        parts.append(button)
    parts.append('</div>')
    return ''.join(parts)


def relative_assets(html, depth):
    """Filsökvägar relativa till sidan så att den även går att öppna från disk.

    Sidlänkarna är kvar som rena URL:er (/about) - de kräver en webbserver.
    """
    prefix = '../' * depth
    for attr in ('src', 'href'):
        for path in ('assets/', 'styles.css', 'script.js'):
            html = html.replace(f'{attr}="/{path}', f'{attr}="{prefix}{path}')
    return html


def document(title, description, canonical, main, current, og_image=None, base='/', footer=True,
             depth=0):
    og = og_image or 'assets/images/mDnzXLO8w8dvYWNOeqpLuWrdak.png'
    # Framer-exportens relativa länkar -> rotrelativa, rena URL:er
    main = main.replace('href="./"', 'href="/"').replace('href="./', f'href="{base}')
    main = main.replace('href="../"', 'href="/"').replace('href="../', 'href="/')
    page = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{canonical}">
  <link rel="icon" href="/assets/images/T3ZUxEdOhiSFrf9m5g33PWyCt4.png">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="/{og}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(description)}">
  <meta name="twitter:image" content="/{og}">
  <link rel="preload" href="/assets/fonts/plus-jakarta-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/styles.css?v={version('styles.css')}">
</head>
<body>
{header_html(current)}
  <main>
{main}
  </main>
{footer_html() if footer else ''}
  <script src="/script.js?v={version('script.js')}"></script>
</body>
</html>
'''
    return relative_assets(page, depth)


def section_wrap(inner, extra='', flush=False):
    cls = 'section'
    if flush:
        cls += ' section--flush'
    if extra:
        cls += ' ' + extra
    return f'''  <section class="{cls}">
    <div class="section__inner">
{inner}
    </div>
  </section>'''


# --------------------------------------------------------------------------
# Sidmallar
# --------------------------------------------------------------------------

def render_index(b):
    hero = section(b, 'Hero')
    ht = texts(deep_section(hero, 'Hero Title', 'Title'))
    icon = images(deep_section(hero, 'Hero Title', 'Title'))
    aside = texts(deep_section(hero, 'Hero Title', 'Content'))
    media = section(hero, 'Desktop/01')
    media_img = images(media)[0]
    card = texts(section(media, 'Content'))

    line1 = ht[0]['html'] if ht else ''
    line2 = ht[1]['html'] if len(ht) > 1 else ''
    icon_html = (f'<img class="hero__title-icon" src="{asset(icon[0]["src"])}" alt="" '
                 f'width="{icon[0]["w"]}" height="{icon[0]["h"]}">') if icon else ''

    hero_html = f'''      <div class="hero__top">
        <div class="hero__title">
          <h1 class="t-h2 hero__heading">
            <span class="hero__line">{line1} {icon_html}</span>
            <span class="hero__line">{line2}</span>
          </h1>
        </div>
        <div class="hero__aside">
          <p class="t-body">{aside[0]['html'] if aside else ''}</p>
          {btn('View Projects', '/project', block=True)}
        </div>
      </div>
      <div class="hero__media">
        <img src="{asset(media_img["src"])}" width="{media_img['w']}" height="{media_img['h']}" alt="">
        <div class="hero__card">
          <div class="hero__card-head">
            {eyebrow(card[0])}
            <h2 class="t-h3">{card[1]['html']}</h2>
          </div>
          <p class="t-sm">{card[2]['html']}</p>
        </div>
      </div>'''

    quote_sec = section(b, 'Quote Section')
    qimg = images(quote_sec)[0]
    quote = texts(quote_sec)[0]['html']
    quote_html = f'''  <section class="band">
    <div class="band__frame" data-parallax>
      <img class="band__bg" src="{asset(qimg["src"])}" alt="" loading="lazy">
    </div>
    <div class="band__cover">
      <div class="band__inner">
        <blockquote class="quote t-h6">{quote}</blockquote>
      </div>
    </div>
  </section>'''

    svc = section(b, 'Our Service')
    kicker = texts(deep_section(svc, 'Title Section'))[0]

    main = '\n'.join([
        section_wrap(hero_html),
        quote_html,
        section_wrap(showcase_html(kicker), extra='showcase-section'),
        team_section(b),
        cta_html(b),
    ])
    return main


# Produktkarusellen på startsidan är scrollstyrd och finns inte i den
# server-renderade exporten. Texter, bilder och länkar är avlästa från den
# publicerade sidan (nasps.se) i tur och ordning.
SHOWCASE = [
    {
        'num': '01',
        'name': 'HTP Roller 400',
        'lead': 'Excavator crab to handle and thread casings and rods. Gripping and pipe '
                'rotation in one attachment, operated through the excavator or by remote radio.',
        'desc': 'HTP Roller 400 is an attachment for handling drilled piles and drill rods, and '
                'for making threaded pile connections. Torque 5500 Nm at 310 bar, jaw opening '
                '800 mm and a maximum handling load of 2500 kg.',
        'img': 'assets/images/htp-roller-400.jpg',
        'photo': True,
        'href': '/product-htp-roller-400',
    },
    {
        'num': '02',
        'name': 'R Thread Self Drilling Anchor Bolt System',
        'lead': 'R thread self drilling anchor bolt system performs drilling, grouting &amp; '
                'anchoring in one step. Easy to process and no risks of drill hole collapse. '
                'Suitable for unstable conditions.',
        'desc': 'R thread self drilling anchor bolt system is composed by hollow rock bolt, '
                'anchor nut, anchor plate, anchor coupler, drill bit, centralizer, and the '
                'hollow anchor bars can be cut and lengthened by coupling on request.',
        'img': 'assets/images/Pbk4MyEU538FtAGhuWR6brBHfUA.png',
        'href': '/product-r-thread',
    },
    {
        'num': '03',
        'name': 'T thread self drilling hollow rock bolt',
        'lead': 'T thread self-drilling rock bolts, a wide range of diameter, and more powerful '
                'support. Widely used in complicated, loose, narrow spaces and broken '
                'geological conditions.',
        'desc': 'Revolutionizing outdoor realms with visionary design, seamlessly blending '
                'aesthetics and functionality to create immersive and purpose-driven spaces '
                'that redefine the outdoor experience, setting new standards in outdoor living.',
        'img': 'assets/images/RvwDomKxByGKMr4EPsmiL3lN5HM.png',
        'href': '/product-t-thread',
    },
    {
        # Punkten finns i listan på originalet men har inget eget läge.
        'num': '04',
        'name': 'Stainless Steel Self Drilling Anchor Bolt',
        'inert': True,
    },
    {
        'num': '05',
        'name': 'Hot-dip Galvanizing Rock Bolts System',
        'lead': 'R thread self drilling anchor bolt system performs drilling, grouting &amp; '
                'anchoring in one step. Easy to process and no risks of drill hole collapse. '
                'Suitable for unstable conditions.',
        'desc': 'Immerse the derusted anchor bar and accessories in liquid zinc for a certain '
                'time, so that the atoms can penetrate and diffuse each other, thereby forming '
                'an iron-zinc alloy layer, which is dense, uniform, firmly bonded, bright and '
                'corrosion resistant.',
        'img': 'assets/images/q3MHkbqyl6MBS2NLtkOTD6ZnSTE.png',
        'href': '/product-hot-dip',
    },
    {
        'num': '06',
        'name': 'Duplex Coating Rock Bolt',
        'lead': 'Duplex coating rock bolt is a supporting method with better anti-corrosion '
                'effect, which combines hot-dip galvanizing method with epoxy coating method '
                'together, which hardens the surface and prevents coating from peeling off.',
        'desc': 'Duplex coating is a combination of hot-dip galvanizing and epoxy coating. '
                'Firstly, product is hot-dip galvanized, and then epoxy powder is sprayed on '
                'the surface. The anchor bolt has better anti-corrosion performance and longer '
                'service life after two kinds of anti-corrosion processes. It can not only '
                'resist ordinary chemical corrosion, but also work in acidic environment and '
                'electrochemical corrosion with stray currents.',
        'img': 'assets/images/Nb9tZClpU1UVSJbUg21yXqFtNKU.png',
        'href': None,
    },
]


def showcase_html(kicker):
    """Scrollstyrd produktkarusell: listan till vänster, aktivt läge till höger."""
    states = [p for p in SHOWCASE if not p.get('inert')]
    heads, arts, panels, items = [], [], [], []
    for i, p in enumerate(states):
        on = ' is-active' if i == 0 else ''
        heads.append(f'<div class="showcase__state{on}" data-state="{i}">'
                     f'<h2 class="t-h2">{p["name"]}</h2>'
                     f'<p class="t-body">{p["lead"]}</p></div>')
        fit = ' showcase__art--photo' if p.get('photo') else ''
        arts.append(f'<img class="showcase__art{fit} showcase__state{on}" data-state="{i}" '
                    f'src="/{p["img"]}" alt="" loading="lazy">')
        cta = btn('Read more', p['href'], block=True) if p['href'] else ''
        panels.append(f'<div class="showcase__state{on}" data-state="{i}">'
                      f'<h3 class="t-h6">{p["name"]}</h3>'
                      f'<p class="t-body">{p["desc"]}</p>{cta}</div>')

    index = 0
    for p in SHOWCASE:
        if p.get('inert'):
            items.append(f'<span class="showcase__item"><span class="t-h6-sm">{p["name"]}</span></span>')
            continue
        on = ' is-active' if index == 0 else ''
        items.append(f'<button class="showcase__item{on}" type="button" data-goto="{index}">'
                     f'<span class="t-h6-sm">{p["name"]}</span>'
                     f'<span class="showcase__num t-sm">{p["num"]}</span></button>')
        index += 1

    return f'''      <div class="showcase" data-showcase data-steps="{len(states)}">
        <div class="showcase__body">
          <div class="showcase__col">
            <div class="showcase__intro">
              {eyebrow(kicker)}
              {''.join(heads)}
            </div>
            <div class="showcase__list">{''.join(items)}</div>
          </div>
          <div class="showcase__media">
            <div class="showcase__arts">{''.join(arts)}</div>
            <div class="showcase__panel">{''.join(panels)}</div>
          </div>
        </div>
      </div>'''


def team_section(b, narrow=False):
    team = section(b, 'Team List')
    if not team:
        return ''
    title = texts(section_before(b, 'Team List', 'Title'))
    cards = []
    for link in [l for l in team if l['type'] == 'link']:
        img = images(link.get('children', []))
        tx = texts(link.get('children', []))
        src = f'/{img[0]["src"]}' if img else ''
        cards.append(f'''<div class="team__card">
            <img src="{src}" alt="{esc(tx[0]['html'])}" loading="lazy">
            <div class="team__meta">
              <h3 class="t-h6-sm">{tx[0]['html']}</h3>
              <p class="t-xs muted">{tx[1]['html']}</p>
              <p class="t-xs"><a href="mailto:{tx[2]['html']}">{tx[2]['html']}</a></p>
            </div>
          </div>''')
    inner = f'''      <div class="page-head">
        <div class="page-head__title">
          {eyebrow(title[0])}
          <h2 class="t-h2">{title[1]['html']}</h2>
        </div>
      </div>
      <div class="team">
        {''.join(cards)}
      </div>'''
    return section_wrap(inner, extra='team-section--narrow' if narrow else 'team-section')


def render_about(b):
    head = deep_section(b, 'Page Title', 'Page Title')
    tx = texts(head)
    link = [l for l in walk(section(b, 'Page Title')) if l['type'] == 'link'][0]
    kicker = tx[0]['html']
    heading = tx[1]['html']
    paras = [t['html'] for t in tx[2:]]
    head_html = '      ' + page_head(kicker, heading, paras,
                                     button=btn('View our projects', '/project'))
    return '\n'.join([section_wrap(head_html), team_section(b, narrow=True)])


def render_project(b):
    head = deep_section(b, 'Page Title', 'Page Title')
    tx = texts(head)
    head_html = '      ' + page_head(tx[0], tx[1]['html'], [t['html'] for t in tx[2:]])

    cards = []
    for item in [x for x in walk(section(b, 'Project List')) if x['type'] == 'link' and x.get('name') == 'Project Image']:
        img = images(item.get('children', []))[0]
        cards.append((item['href'], img))
    metas = []
    for card in section(b, 'Project List'):
        pass
    # år och titel ligger i "Project Description"
    descs = []
    blocks = section(b, 'Project List')
    i = 0
    while i < len(blocks):
        if blocks[i]['type'] == 'begin' and blocks[i]['name'] == 'Variant 1':
            depth, j = 1, i + 1
            while j < len(blocks) and depth:
                if blocks[j]['type'] == 'begin':
                    depth += 1
                elif blocks[j]['type'] == 'end':
                    depth -= 1
                j += 1
            descs.append(blocks[i + 1:j - 1])
            i = j
            continue
        i += 1

    html = []
    for chunk in descs:
        link = [l for l in walk(chunk) if l['type'] == 'link' and l.get('name') == 'Project Image'][0]
        img = images(link.get('children', []))[0]
        tx = texts(section(chunk, 'Project Description'))
        href = link['href'].replace('./', '/')
        html.append(f'''<article class="card">
          <a class="card__media" href="{href}"><img src="{asset(img["src"])}" alt="{esc(tx[1]['html'])}" loading="lazy"></a>
          <div class="card__body">
            <p class="card__meta t-xs">{tx[0]['html']}</p>
            <h2 class="t-h6-sm"><a href="{href}">{tx[1]['html']}</a></h2>
          </div>
          {btn('View project', href)}
        </article>''')

    return section_wrap(head_html + f'\n      <div class="cards">{"".join(html)}</div>')


def render_blog(b):
    latest = section(b, 'Latest Blog')
    head = deep_section(latest, 'Page Title')
    tx = texts(head)
    head_html = '      ' + page_head(tx[0], tx[1]['html'], [t['html'] for t in tx[2:]])

    posts, blocks, i = [], latest, 0
    while i < len(blocks):
        if blocks[i]['type'] == 'begin' and blocks[i]['name'] == 'Variant 1':
            depth, j = 1, i + 1
            while j < len(blocks) and depth:
                if blocks[j]['type'] == 'begin':
                    depth += 1
                elif blocks[j]['type'] == 'end':
                    depth -= 1
                j += 1
            posts.append(blocks[i + 1:j - 1])
            i = j
            continue
        i += 1

    cards = []
    for chunk in posts:
        link = [l for l in walk(chunk) if l['type'] == 'link' and l.get('name') == 'Post Image'][0]
        img = images(link.get('children', []))[0]
        content = section(chunk, 'Post Content')
        tx = texts(content)
        href = url(link['href'])
        title = re.sub(r'</?a[^>]*>', '', tx[1]['html'])
        cards.append(f'''<article class="card">
          <a class="card__media" href="{href}"><img src="{asset(img["src"])}" alt="{esc(title)}" loading="lazy"></a>
          <div class="card__body">
            <p class="card__meta t-xs">{tx[0]['html']}</p>
            <h2 class="t-h6-sm"><a href="{href}">{title}</a></h2>
            <p class="card__excerpt t-xs">{tx[-1]['html']}</p>
          </div>
        </article>''')

    return section_wrap(head_html + f'\n      <div class="cards">{"".join(cards)}</div>')


def render_contact(b):
    main = deep_section(b, 'Page Title', 'Main')
    head = deep_section(main, 'Page Title')
    tx = texts(head)
    head_html = page_head(tx[0], tx[1]['html'], [t['html'] for t in tx[2:]],
                          level='t-display')

    cols = []
    for name in ('Location', 'Email', 'Phone'):
        blk = section(main, name)
        t = texts(blk)
        value = t[2]['html']
        if name == 'Email':
            value = re.sub(r'([\w.+-]+@[\w.-]+)', r'<a href="mailto:\1">\1</a>', value)
        if name == 'Phone':
            value = re.sub(r'(\+[\d ]{6,})', lambda m: f'<a href="tel:{m.group(1).replace(" ", "")}">{m.group(1)}</a>', value)
        cols.append(f'''<div class="case__fact">
            <h2 class="t-h6-sm">{t[0]['html']}</h2>
            <p class="t-sm muted">{t[1]['html']}</p>
            <p class="t-body">{value}</p>
          </div>''')

    inner = f'''      <div class="contact">
        {head_html}
        <div class="case__facts">{''.join(cols)}</div>
      </div>'''
    return section_wrap(inner)


FAQ_FALLBACK = 'Contact us and we will get back to you with the details for your project.'


def render_faq(b):
    main = section(b, 'Main Section')
    head = deep_section(main, 'Page Title')
    tx = texts(head)
    head_html = '      ' + page_head(tx[0], tx[1]['html'], [t['html'] for t in tx[2:]], center=True)

    faq = section(main, 'Faq')
    items, blocks, i = [], faq, 0
    while i < len(blocks):
        if blocks[i]['type'] == 'begin' and blocks[i]['name'] in ('Open', 'Close'):
            state = blocks[i]['name']
            depth, j = 1, i + 1
            while j < len(blocks) and depth:
                if blocks[j]['type'] == 'begin':
                    depth += 1
                elif blocks[j]['type'] == 'end':
                    depth -= 1
                j += 1
            items.append((state, texts(blocks[i + 1:j - 1])))
            i = j
            continue
        i += 1

    html = []
    for n, (state, tx2) in enumerate(items):
        question = tx2[0]['html']
        answer = tx2[1]['html'] if len(tx2) > 1 else FAQ_FALLBACK
        open_ = 'true' if state == 'Open' else 'false'
        html.append(f'''<div class="faq__item" data-open="{open_}">
          <button class="faq__q t-h6-sm" type="button" aria-expanded="{open_}" aria-controls="faq-{n}">
            <span>{question}</span><span class="faq__icon" aria-hidden="true"></span>
          </button>
          <div class="faq__a" id="faq-{n}"><div><p class="t-sm">{answer}</p></div></div>
        </div>''')

    button = texts(section(main, 'Button'))
    inner = f'''{head_html}
      <div class="faq">{''.join(html)}</div>
      <div class="faq__footer">
        <p class="t-h6-sm">{button[0]['html'] if button else 'Still have any questions?'}</p>
        {btn('Contact us', '/contact')}
      </div>'''
    return section_wrap(inner)


def render_legal(b):
    main = section(b, 'Main Section')
    head = deep_section(main, 'Page Title')
    tx = texts(head)
    head_html = '      ' + page_head(tx[0], tx[1]['html'], [t['html'] for t in tx[2:]])

    items, blocks, i = [], section(main, 'Content'), 0
    while i < len(blocks):
        if blocks[i]['type'] == 'begin' and blocks[i]['name'] == 'Item':
            depth, j = 1, i + 1
            while j < len(blocks) and depth:
                if blocks[j]['type'] == 'begin':
                    depth += 1
                elif blocks[j]['type'] == 'end':
                    depth -= 1
                j += 1
            items.append(texts(blocks[i + 1:j - 1]))
            i = j
            continue
        i += 1

    html = []
    for tx2 in items:
        parts = [f'<h2 class="t-h5">{tx2[0]["html"]}</h2>']
        for t in tx2[1:]:
            if t['tag'] in ('ul', 'ol'):
                parts.append(f'<{t["tag"]} class="t-body rich">{t["html"]}</{t["tag"]}>')
            else:
                parts.append(f'<p class="t-body">{t["html"]}</p>')
        html.append(f'<section class="legal__item">{"".join(parts)}</section>')

    return section_wrap(head_html + f'\n      <div class="legal">{"".join(html)}</div>')


def render_404(b):
    tx = texts(section(b, 'Description'))
    return f'''  <section class="section">
    <div class="section__inner">
      <div class="notfound">
        <p class="notfound__code">404</p>
        <h1 class="t-display">{tx[0]['html']}</h1>
        <p class="t-sm muted">{tx[1]['html']}</p>
        {btn('Back to homepage', '/')}
      </div>
    </div>
  </section>'''


def render_case(b):
    top = section(b, 'Project Title')
    main = section(top, 'Main')
    head = deep_section(main, 'Page Title')
    tx = texts(head)
    facts = []
    for name in ('Client', 'Service', 'Year', 'Location'):
        t = texts(section(main, name))
        if len(t) >= 2:
            facts.append(f'<div class="case__fact"><dt class="t-xs">{t[0]["html"]}</dt>'
                         f'<dd class="t-body">{t[1]["html"]}</dd></div>')
    hero_img = images(section(top, 'Image'))
    gallery = images(section(b, 'Content Section'))

    gal = ''.join(f'<img src="{asset(g["src"])}" width="{g["w"]}" height="{g["h"]}" alt="" loading="lazy">'
                  for g in gallery)
    hero = (f'<div class="case__media"><img src="{asset(hero_img[0]["src"])}" '
            f'width="{hero_img[0]["w"]}" height="{hero_img[0]["h"]}" alt=""></div>') if hero_img else ''

    inner = f'''      <div class="case__top">
        <div class="case__main">
          {page_head(tx[0], tx[1]['html'], [t['html'] for t in tx[2:]], level='t-display')}
          <dl class="case__facts">{''.join(facts)}</dl>
          {btn('Drop us a line', '/contact')}
        </div>
        {hero}
      </div>
      <div class="case__gallery">{gal}</div>'''
    return '\n'.join([section_wrap(inner), cta_html(b)])


def render_post(b):
    main = section(b, 'Main Content')
    head = deep_section(main, 'Title', 'Post Title')
    tx = texts(deep_section(head, 'Title'))
    meta = []
    for name in ('Date', 'Author'):
        t = texts(section(head, name))
        if len(t) >= 2:
            meta.append(f'<div><dt class="t-sm muted">{t[0]["html"]}</dt>'
                        f'<dd class="t-body">{t[1]["html"]}</dd></div>')
    excerpt = [t for t in texts(head) if t not in tx and t['style'] == 'body']
    excerpt = excerpt[-1]['html'] if excerpt else ''
    img = images(section(main, 'Post Image'))
    img_html = ''.join(f'<img src="{asset(i["src"])}" width="{i["w"]}" height="{i["h"]}" alt="" loading="lazy">'
                       for i in img)

    inner = f'''      <article class="post">
        <div class="post__aside">
          {eyebrow(tx[0])}
          <h1 class="t-h2">{tx[1]['html']}</h1>
          <dl class="post__meta">{''.join(meta)}</dl>
          <p class="t-sm muted">{excerpt}</p>
          {img_html}
        </div>
        <div class="post__body">
          {''.join(f'<p class="t-body">{t["html"]}</p>' for t in texts(section(main, 'Post Content')))}
        </div>
      </article>'''
    return '\n'.join(x for x in [section_wrap(inner), related_posts(b)] if x)


def related_posts(b):
    latest = section(b, 'Latest Blog')
    if not latest:
        return ''
    title = texts(section(latest, 'Title'))
    cards = []
    for chunk in repeat_blocks(latest, 'Variant 1'):
        link = [l for l in walk(chunk) if l['type'] == 'link' and l.get('name') == 'Post Image'][0]
        img = images(link.get('children', []))[0]
        tx = texts(section(chunk, 'Post Content'))
        href = link['href']
        name = re.sub(r'</?a[^>]*>', '', tx[1]['html'])
        cards.append(f'''<article class="card">
          <a class="card__media" href="{href}"><img src="{asset(img["src"])}" alt="{esc(name)}" loading="lazy"></a>
          <div class="card__body">
            <p class="card__meta t-xs">{tx[0]['html']}</p>
            <h3 class="t-h6-sm"><a href="{href}">{name}</a></h3>
            <p class="card__excerpt t-xs">{tx[-1]['html']}</p>
          </div>
        </article>''')
    inner = f'''      <div class="page-head">
        <div class="page-head__title">
          {eyebrow(title[0])}
          <h2 class="t-h2">{title[1]['html']}</h2>
        </div>
      </div>
      <div class="cards">{''.join(cards)}</div>'''
    return section_wrap(inner)


def render_product(b):
    blocks = body(b)
    head = section(blocks, 'Page Title', 0)
    hero_img = images(head)
    tx = texts(head)
    hero = f'''      <div class="product__head">
        <div class="product__figure">
          {f'<img src="{asset(hero_img[0]["src"])}" width="{hero_img[0]["w"]}" height="{hero_img[0]["h"]}" alt="{esc(tx[0]["html"]) if tx else ""}">' if hero_img else ''}
        </div>
        <div class="product__intro">
          <h1 class="t-h3">{tx[0]['html'] if tx else ''}</h1>
          {''.join(f'<p class="t-sm">{t["html"]}</p>' for t in tx[1:])}
        </div>
      </div>'''

    sections = []
    seen_hero = False
    i = 0
    while i < len(blocks):
        if blocks[i]['type'] == 'begin' and blocks[i]['name'] == 'Page Title':
            depth, j = 1, i + 1
            while j < len(blocks) and depth:
                if blocks[j]['type'] == 'begin':
                    depth += 1
                elif blocks[j]['type'] == 'end':
                    depth -= 1
                j += 1
            if seen_hero:
                sections.append(blocks[i + 1:j - 1])
            seen_hero = True
            i = j
            continue
        i += 1

    parts = [section_wrap(hero)]
    for sec_blocks in sections:
        # Löptext samlas i .prose; tabellkomponenterna ligger centrerade för sig.
        groups, prose = [], []
        for blk in walk(sec_blocks):
            if blk['type'] == 'text':
                if blk['style'] == 'eyebrow' or (blk['style'] == 'body' and blk['html'].isupper()):
                    prose.append(eyebrow(blk))
                elif blk['tag'] in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                    prose.append(f'<h2 class="t-h3">{blk["html"]}</h2>')
                elif blk['tag'] in ('ul', 'ol'):
                    prose.append(f'<{blk["tag"]} class="t-body rich">{blk["html"]}</{blk["tag"]}>')
                else:
                    prose.append(f'<p class="t-body rich">{blk["html"]}</p>')
            elif blk['type'] == 'image':
                prose.append(f'<img src="{asset(blk["src"])}" width="{blk["w"]}" height="{blk["h"]}" alt="" loading="lazy">')
            elif blk['type'] == 'video':
                if prose:
                    groups.append(f'<div class="prose">{"".join(prose)}</div>')
                    prose = []
                groups.append(video_html(blk))
            elif blk['type'] == 'embed':
                if prose:
                    groups.append(f'<div class="prose">{"".join(prose)}</div>')
                    prose = []
                groups.append(f'<div class="product__specs">{wrap_tables(blk["html"])}</div>')
        if prose:
            groups.append(f'<div class="prose">{"".join(prose)}</div>')
        parts.append(section_wrap('      ' + ''.join(groups), extra='section--prose', flush=True))
    parts.append(cta_html(b))
    return '\n'.join(p for p in parts if p)


# Produktsidorna. Namn och storlekar är lästa ur respektive sidas spec-tabell:
# tre av sidorna delar samma rubrik och ingress i Framer-originalet, så korten
# skiljs åt på det som faktiskt skiljer sidorna åt.
# HTP Roller 400. Till skillnad från de övriga produkterna kommer den inte ur
# Framer-exporten - text och specifikationer är hämtade ur produktbladet
# (NASPS_Spinner_ENG.pdf) och bilderna ur fotograferingen.
HTP_ROLLER = {
    'slug': 'product-htp-roller-400',
    'name': 'HTP Roller 400',
    'tagline': 'Excavator crab to handle and thread casings and rods',
    'lead': 'An attachment for handling drilled piles and drill rods, and for making threaded '
            'pile connections. Gripping and pipe rotation in one unit, operated through the '
            'excavator or by remote radio.',
    'image': 'assets/images/htp-roller-400.jpg',
    'wide': 'assets/images/htp-roller-400-wide.jpg',
    'gallery': [
        ('assets/images/htp-roller-400-front.jpg',
         'HTP Roller 400 seen from the front, with the roller assembly in the gripping section'),
        ('assets/images/htp-roller-400-grip.jpg',
         'HTP Roller 400 with the jaws closed around a casing'),
        ('assets/images/htp-roller-400-mount.jpg',
         'HTP Roller 400 from behind, with the excavator mounting bracket'),
    ],
    'body': [
        'HTP Roller 400 is an attachment, designed for installation on an excavator and '
        'intended for handling drilled piles, drill rods, and for making threaded pile '
        'connections. The attachment is equipped with both a standard gripping function and an '
        'additional pipe rotation function. Switching between these two operating modes is '
        'carried out using the remote control supplied with the unit. The primary operation is '
        'performed through the excavator’s hydraulic control system and rotator function.',
        'When making threaded connections on drilled piles, only one pile shall be handled at a '
        'time. It is recommended to grip the pile as close to the center point as possible in '
        'order to minimize unnecessary torsional forces and structural stress within the '
        'attachment. The maximum permissible load capacity of 2500 kg must not be exceeded '
        'during operation.',
        'During the threaded connection rotation process, the operation shall be carried out in '
        'a controlled and steady manner to avoid damage to the threads or connection surfaces. '
        'The connection is considered complete when the thread has been fully tightened or when '
        'friction grip between the contact surfaces ceases. All threaded connections shall '
        'subsequently be verified by visual inspection.',
        'The attachment may also be used for loading, lifting, and general handling of drill '
        'piles and similar materials. Caution shall be exercised during material handling due '
        'to the roller assembly integrated into the gripping section.',
        'The attachment must not be subjected to excessive external loads or unintended forces, '
        'for example during turning or repositioning of the excavator while carrying a load. '
        'Special attention and caution shall always be observed whenever personnel are present '
        'within the attachment’s hazard zone.',
    ],
    'specs': [
        ('Excavator size range', '15–25 tons (basic model)'),
        ('Grab weight', '650 kg'),
        ('Max casing size', '406 (508) mm'),
        ('Measurements', 'Width 1200 mm · height 1000 mm · depth 800 mm'),
        ('Jaw opening', '800 mm'),
        ('Torque', '5500 Nm @ 310 bar'),
        ('Max handling load', '2500 kg'),
        ('Operation', 'Excavator hydraulics or remote radio'),
        ('Patent', '# 20257133'),
    ],
}


def carousel(images, label='Product photos'):
    """Bildsnurra. Utan JS blir det en svepbar rad med scroll-snap; med JS
    tillkommer pilar, punkter och bildtext."""
    slides, dots = [], []
    for i, (src, alt) in enumerate(images):
        slides.append(
            f'<li class="carousel__slide" data-slide="{i}">'
            f'<img src="{asset(src)}" width="1050" height="1400" alt="{esc(alt)}"'
            f'{"" if i == 0 else " loading=\'lazy\'"}></li>')
        dots.append(
            f'<button class="slider-dot" type="button" data-goto="{i}" '
            f'aria-label="Show image {i + 1} of {len(images)}"'
            f'{" aria-current=\'true\'" if i == 0 else ""}></button>')

    arrow = ('<svg viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M10 3.5 5.5 8l4.5 '
             '4.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" '
             'stroke-linejoin="round"/></svg>')
    return f'''<div class="carousel" data-carousel role="group" aria-roledescription="carousel"
           aria-label="{esc(label)}">
          <div class="carousel__viewport" tabindex="0">
            <ul class="carousel__track">{''.join(slides)}</ul>
          </div>
          <div class="carousel__controls">
            <button class="slider-arrow" type="button" data-prev aria-label="Previous image">
              {arrow}
            </button>
            <div class="slider-dots">{''.join(dots)}</div>
            <button class="slider-arrow slider-arrow--next" type="button" data-next
                    aria-label="Next image">{arrow}</button>
          </div>
          <p class="carousel__caption t-sm muted" data-caption aria-live="polite">{esc(images[0][1])}</p>
        </div>'''


def render_htp_roller(_blocks=None):
    """Produktsida för HTP Roller 400 - innehållet kommer från produktbladet."""
    p = HTP_ROLLER
    hero = f'''      <div class="product__head">
        <div class="product__figure product__figure--photo">
          <img src="{asset(p['image'])}" width="1050" height="1400"
               alt="HTP Roller 400 attachment for excavators">
        </div>
        <div class="product__intro">
          {eyebrow(p['tagline'])}
          <h1 class="t-h3">{p['name']}</h1>
          <p class="t-body">{p['lead']}</p>
          {btn('Request a quote', '/contact')}
        </div>
      </div>'''

    intro = ('<div class="prose">' + eyebrow('Introduction')
             + ''.join(f'<p class="t-body">{t}</p>' for t in p['body']) + '</div>')

    rows = ''.join(f'<tr><th scope="row" class="t-sm">{k}</th><td class="t-body">{v}</td></tr>'
                   for k, v in p['specs'])
    specs = (f'<div class="prose"><h2 class="t-h3">Technical data</h2></div>'
             f'<div class="product__specs"><table class="spec"><tbody>{rows}</tbody></table></div>')

    gallery = carousel(p['gallery'], f"{p['name']} photos")

    return '\n'.join([
        section_wrap(hero),
        section_wrap('      ' + intro, extra='section--prose', flush=True),
        section_wrap('      ' + specs, extra='section--prose', flush=True),
        section_wrap(f'      {gallery}', flush=True),
        cta_html(load('product-r-thread')),
    ])



PRODUCTS = [
    {
        'slug': HTP_ROLLER['slug'],
        'name': HTP_ROLLER['name'],
        'sizes': 'Torque 5500 Nm · jaw 800 mm · 2500 kg',
        'desc': HTP_ROLLER['lead'],
        'img': HTP_ROLLER['image'],
        'photo': True,
        'render': 'htp',
    },
    {
        'slug': 'product-r-thread',
        'name': 'R Thread Self Drilling Anchor Bolt System',
        'sizes': 'R25 · R32 · R38 · R51',
        'desc': 'R thread self drilling anchor bolt system performs drilling, grouting &amp; '
                'anchoring in one step. Easy to process and no risks of drill hole collapse. '
                'Suitable for unstable conditions.',
    },
    {
        'slug': 'product-t-thread',
        'name': 'T Thread Self Drilling Anchor Bolt System',
        'sizes': 'T30 · T40 · T52 · T73 · T76 · T103 · T111 · T127 · T130 · T150 · T200',
        'desc': 'T thread self-drilling rock bolts, a wide range of diameter, and more powerful '
                'support. Widely used in complicated, loose, narrow spaces and broken '
                'geological conditions.',
    },
    {
        'slug': 'product-self-drilling-anchor-bolt',
        'name': 'Stainless Steel Self Drilling Anchor Bolt',
        'sizes': 'SXR25 · SXR32 · SXR38 · SXR51',
        'desc': 'Hollow anchor bars in stainless steel with couplers, hex nuts and plates — the '
                'SXR series, for ground conditions where corrosion resistance is decisive.',
    },
    {
        'slug': 'product-hot-dip',
        'name': 'Hot-dip Galvanizing Rock Bolts System',
        'sizes': 'ISO 1461 coating',
        'desc': 'Hot-dip galvanizing rock bolt is a sda rock bolt with good anti-corrosion '
                'property. It forms a protective layer by putting clean-surface products into '
                'molten galvanizing zinc.',
    },
    {
        # Duplex saknar egen produktsida - kortet visas utan Read more.
        'slug': None,
        'name': 'Duplex Coating Rock Bolt',
        'sizes': 'Hot-dip galvanizing + epoxy coating',
        'desc': 'Duplex coating rock bolt is a supporting method with better anti-corrosion '
                'effect, which combines hot-dip galvanizing method with epoxy coating method '
                'together, which hardens the surface and prevents coating from peeling off.',
        'img': 'assets/images/Nb9tZClpU1UVSJbUg21yXqFtNKU.png',
    },
]


def product_image(slug):
    """Produktbilden från sidans egen ingress."""
    img = images(section(body(load(slug)), 'Page Title', 0))
    return img[0] if img else None


def render_products():
    """Produktöversikten: stora kort som leder in till respektive produktsida."""
    cards = []
    for i, p in enumerate(PRODUCTS):
        href = '/' + p['slug'] if p['slug'] else None
        wide = ' product-card--wide' if i == len(PRODUCTS) - 1 and len(PRODUCTS) % 2 else ''
        photo = ' product-card__media--photo' if p.get('photo') else ''
        if p.get('img'):
            src, w, h = asset(p['img']), 1050, 1400
        else:
            img = product_image(p['slug'])
            src, w, h = (asset(img['src']), img['w'], img['h']) if img else (None, 0, 0)

        image = f'<img src="{src}" width="{w}" height="{h}" alt="" loading="lazy">'
        if href:
            media = (f'<a class="product-card__media{photo}" href="{href}" tabindex="-1" '
                     f'aria-hidden="true">{image}</a>')
            title = f'<a href="{href}">{p["name"]}</a>'
            action = btn('Read more', href)
        else:
            media = f'<div class="product-card__media{photo}">{image}</div>'
            title = p['name']
            action = ''
        cards.append(f'''<article class="product-card{wide}">
          {media if src else ''}
          <div class="product-card__body">
            <p class="product-card__sizes t-eyebrow">{p['sizes']}</p>
            <h2 class="t-h5">{title}</h2>
            <p class="t-body">{p['desc']}</p>
            {action}
          </div>
        </article>''')

    head_html = '      ' + page_head(
        'Products',
        'Systems and components for demanding ground conditions',
        ['Self-drilling anchors, rock bolt systems, couplings and drilling tools — selected for '
         'structural performance, installation efficiency and site-proven durability. Every '
         'product page carries the full technical data.'])
    return section_wrap(head_html + f'''
      <div class="product-grid">{''.join(cards)}</div>''')


# --------------------------------------------------------------------------
# Sidregister
# --------------------------------------------------------------------------

PAGES = [
    # (källa i tools/extracted, utfil, aktiv nav-post, renderare)
    ('index', 'index.html', '/', render_index),
    ('about', 'about.html', '/about', render_about),
    ('project', 'project.html', '/project', render_project),
    ('project__salen', 'project/salen.html', '/project', render_case),
    ('project__rodaulven', 'project/rodaulven.html', '/project', render_case),
    ('blog', 'blog.html', '', render_blog),
    ('blog__project-salen', 'blog/project-salen.html', '', render_post),
    ('blog__nasps-accelerates-growth', 'blog/nasps-accelerates-growth.html', '', render_post),
    ('blog__röda-ulven-expands-in-skagshamn-–-investing-in-increased-capacity',
     'blog/röda-ulven-expands-in-skagshamn-–-investing-in-increased-capacity.html', '', render_post),
    ('contact', 'contact.html', '', render_contact),
    ('faq', 'faq.html', '', render_faq),
    ('privacy', 'privacy.html', '', render_legal),
    ('terms', 'terms.html', '', render_legal),
    ('404', '404.html', '', render_404),
] + [(p['slug'], p['slug'] + '.html', '/products',
      render_htp_roller if p.get('render') == 'htp' else render_product)
     for p in PRODUCTS if p['slug']]


EXTRA_META = {
    # Sidor som inte finns i Framer-exporten och därför saknar metadata där.
    'product-htp-roller-400': {
        'title': 'HTP Roller 400 | NASPS - Nordic Anchor & Steel Pile Supply AB',
        'description': 'Excavator attachment for handling drilled piles and drill rods and for '
                       'making threaded pile connections. Torque 5500 Nm, jaw opening 800 mm, '
                       'max handling load 2500 kg.',
        'canonical': 'https://www.nasps.se/product-htp-roller-400',
        'og': 'assets/images/htp-roller-400.jpg',
    },
}


def meta_for(page):
    """Titel, beskrivning och canonical hämtas ur den ursprungliga exporten."""
    if page in EXTRA_META:
        return EXTRA_META[page]
    path = os.path.join(ROOT, 'pages', page + '.html')
    if not os.path.exists(path):
        return None
    src = open(path, encoding='utf-8').read()
    title = re.search(r'<title>(.*?)</title>', src, re.S)
    desc = re.search(r'<meta name="description" content="(.*?)"', src, re.S)
    canon = re.search(r'<link rel="canonical" href="(.*?)"', src)
    og = re.search(r'<meta property="og:image" content="https://framerusercontent.com/images/(.*?)"', src)
    return {
        'title': (title.group(1) if title else 'NASPS').replace('&amp;', '&'),
        'description': (desc.group(1) if desc else '').replace('&amp;', '&'),
        'canonical': canon.group(1) if canon else 'https://www.nasps.se/',
        'og': 'assets/images/' + og.group(1) if og else None,
    }


def main():
    written = []
    for source, out, current, render in PAGES:
        has_content = os.path.exists(os.path.join(SRC, source + '.json'))
        blocks = load(source) if has_content else []
        m = meta_for(source) or {'title': 'NASPS', 'description': '', 'canonical': 'https://www.nasps.se/', 'og': None}
        base = '/' + out.rsplit('/', 1)[0] + '/' if '/' in out else '/'
        html = document(m['title'], m['description'], m['canonical'], render(blocks), current,
                        m['og'], base, footer=source != '404', depth=out.count('/'))
        path = os.path.join(ROOT, out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(html)
        written.append(out)

    html = document('Products | NASPS - Nordic Anchor & Steel Pile Supply AB',
                    'Self-drilling anchors, rock bolt systems and drilling tools from NASPS.',
                    'https://www.nasps.se/products', render_products(), '')
    with open(os.path.join(ROOT, 'products.html'), 'w', encoding='utf-8') as fh:
        fh.write(html)
    written.append('products.html')

    print(f'{len(written)} sidor byggda')


def url(href):
    return href.replace('./', '/')


if __name__ == '__main__':
    main()
