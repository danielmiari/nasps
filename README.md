# nasps.se — export från Framer

Hämtat 2026-08-30 från https://www.nasps.se (Framer, server-renderat/SSG).

## Innehåll
- `pages/` — 19 råa HTML-sidor exakt som Framer serverar dem
- `content/` — samma sidor som markdown (rubriker, brödtext, listor, bild- och länkreferenser)
- `content/_index.json` — sidregister: titel, meta-description, antal bilder/länkar
- `assets/images/` — 22 bilder i originalupplösning (22 MB)
- `assets/fonts/` — 27 woff2-filer (Plus Jakarta Sans + Inter)
- `sitemap.xml`, `urls.txt`, `assets-all.txt` — källistor

## Sidstruktur
| Rutt | Fil |
|---|---|
| `/` | index |
| `/about` | about |
| `/blog` + 3 inlägg | blog, blog__* |
| `/project` + 2 case | project, project__salen, project__rodaulven |
| 5 produktsidor | product-hot-dip, product-r-thread, product-t-thread, product-shank_adapter, product-self-drilling-anchor-bolt |
| `/contact`, `/faq`, `/privacy`, `/terms`, `/404` | resp. fil |

## Designtokens
Typsnitt: **Plus Jakarta Sans** (primär), Inter (fallback/kod)

| Roll | Hex |
|---|---|
| Text / mörk bas | `#1e1e1c` |
| Ljus bakgrund | `#f1efea` |
| Vit | `#ffffff` |
| Accent röd | `#ee3423` |
| Accent orange | `#e8792f` / `#e8620a` |
| Länk/interaktiv blå | `#0099ff` |

Opacitetsvarianter av `#1e1e1c`: 05, 0d, 33, 4d, 80, 99, b3, cc, e6.
