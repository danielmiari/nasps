# nasps.se

Statisk sajt i NASPS designspråk. Sidorna är handskriven HTML mot ett gemensamt
designsystem i [`styles.css`](styles.css) — inget ramverk, ingen runtime utöver
[`script.js`](script.js) (mobilmeny, FAQ-dragspel, storlekstabbar, bildsnurra,
videofasad, parallax på bildbanden).

Designen är hämtad ur den tidigare Framer-sajten: färger, typografi, mått,
sektionsindelning och all text kommer därifrån. Originalexporten ligger kvar i
[`pages/`](pages/) som referens.

## Språk

Sajten byggs på två språk. Engelska ligger på rotadressen, svenska under `/sv/`
med samma slugs: `/about` och `/sv/about`. Språkväxlaren i sidhuvudet länkar
till samma sida i det andra språket, och varje sida har `hreflang` för båda.

All text går genom `t()` i `tools/build.py` och slås upp i
`tools/translations/sv.json`, nycklad på den engelska källsträngen. Saknas en
översättning används originalet — en ofullständig ordlista ger alltså engelsk
text, inte en trasig sida. Lista det som saknas med:

```sh
python3 tools/build.py --saknade    # -> tools/translations/sv.saknade.json
```

Följande står kvar på engelska med avsikt: **produktnamn**, spec-tabellernas
innehåll (teknisk data från leverantören), och Framers mall-badge som ändå inte
renderas. `tools/translations/en.json` används tvärtom för rättelser i
källtexten — Röda Ulven-sidan är skriven på svenska i Framer-exporten och får
sin engelska text därifrån.

## Struktur

| Rutt | Fil |
|---|---|
| `/` | `index.html` |
| `/about` | `about.html` |
| `/sv/…` | svensk version av varje sida |
| `/project` | `project.html` |
| `/project/salen`, `/project/rodaulven` | `project/*.html` |
| `/products` | `products.html` — produktöversikt med kort |
| 5 produktsidor | `product-*.html` |

Produktöversikten listar sex produkter: Duplex Coating Rock Bolt saknar egen sida
och visas som ett kort utan Read more-länk (`'slug': None` i `PRODUCTS`). Shank
Adapter är borttagen och `/product-shank_adapter` omdirigeras till `/products`.
| `/blog` + 3 inlägg | `blog.html`, `blog/*.html` |
| `/contact`, `/faq`, `/privacy`, `/terms`, `/404` | resp. fil |

Huvudmenyn är Home / About us / Products / Project + kontaktknappen.

Alla interna adresser är **relativa till sidan** (`about`, `../about`,
`./` för start). Det gör att sajten fungerar oavsett var den ligger: på
domänroten via Vercel, eller i en underkatalog som GitHub Pages
(`danielmiari.github.io/nasps/`). Mallarna skriver `/about` internt —
omskrivningen sker på ett ställe, i `relative_urls()` i `tools/build.py`.

Adresserna är utan filändelse, vilket kräver en värd som mappar `/about` →
`about.html`. GitHub Pages och Vercel gör det, liksom `tools/serve.py`.

## Publicering

Sajten ligger på GitHub Pages, tills vidare på
`danielmiari.github.io/nasps/`.

**Byta till egen domän:** lägg först in DNS-posterna hos GoDaddy (fyra A-poster
på apex mot 185.199.108–111.153, och `www` som CNAME mot `danielmiari.github.io.`).
Kopiera sedan `tools/CNAME.väntar` till `CNAME` i rotkatalogen och pusha.
Ordningen spelar roll: läggs CNAME in före DNS börjar GitHub genast omdirigera
förhandsadressen till domänen, som då fortfarande pekar någon annanstans.

Filen ska redigeras i repot, inte via GitHubs gränssnitt — gränssnittet
committar en egen version och då hamnar repot ur synk.

`.github/workflows/pages.yml` kör `tools/build.py` och `tools/check_links.py`
vid varje push till `main` och publicerar resultatet. Bygget behöver bara
Pythons standardbibliotek. Att sidorna ändå är incheckade gör repot
publicerbart även om workflowen skulle fallera.

`vercel.json` ligger kvar för den dag sajten flyttar till Vercel — Pages läser
den inte. Sidor som tagits bort listas i `BORTTAGNA` i `tools/build.py` och får
en liten vidarebefordringssida, eftersom Pages inte kan göra serveromdirigeringar.

## Förhandsvisa lokalt

```sh
python3 tools/serve.py        # http://127.0.0.1:8000
python3 tools/check_links.py  # löser varje intern länk mot sin egen sida
```

`python3 -m http.server` duger **inte** — den hittar inte `about.html` när
webbläsaren ber om `/about` utan svarar med sin egen felsida. `tools/serve.py`
gör samma sak som Vercel: provar `about.html`, `about/index.html`, och visar
sajtens egen `404.html` för okända adresser. Är porten upptagen tas nästa
lediga och adressen skrivs ut.

## Designtokens

Typsnitt: **Plus Jakarta Sans** (självhostad i `assets/fonts/`, variabel vikt).

| Roll | Hex |
|---|---|
| Text / mörk bas | `#1e1e1c` |
| Bakgrund | `#f1efea` |
| Vit | `#ffffff` |
| Accent röd | `#ee3423` |
| Accent orange (hover) | `#e8792f` |

Typografiskalan (`.t-display` 64 → `.t-xs` 12) och stegen mellan brytpunkterna
följer originalets. Brytpunkter: desktop ≥1200px, tablet 810–1199px, telefon
<810px. Sidbredd max 1440px, sektionspadding 50/40px.

## Bygga om sidorna

Sidorna genereras ur innehållet i `tools/extracted/` så att sidhuvud, sidfot och
komponenter hålls identiska på alla sidor:

```sh
python3 tools/extract.py pages/*.html   # innehåll ur Framer-exporten -> JSON
python3 tools/build.py                  # JSON + mallar -> HTML i roten
```

HTP Roller 400 finns inte i Framer-exporten — dess text, specifikationer och
bilder ligger i `HTP_ROLLER` överst bland produkterna i `tools/build.py`. Nya
produkter läggs till på samma sätt: en post i `PRODUCTS` (kortet och sidan) och
en i `SHOWCASE` (startsidans karusell).

`extract.py` behövs bara om innehållet i `pages/` ändras. Redigera du HTML-filerna
direkt skrivs ändringarna över nästa gång `build.py` körs — layoutändringar hör
hemma i `tools/build.py`, formgivning i `styles.css`.

`styles.css` och `script.js` länkas med ett innehållshash (`?v=…`) som byts vid
varje bygge. Det hindrar webbläsare från att para ihop ny HTML med gammal
cachad CSS eller JS — en blandning som ger trasig layout utan att något syns
fel i källkoden.

## Bildverktyg

Produktrenderingarna ligger på genomskinlig bakgrund. Kommer en ny bild med
vit platta bakom sig:

```sh
python3 tools/cutout.py bild.png bild.png
```

Den plockar bort den vita ytan och den mjuka slagskuggan, mjukar upp kanten och
sparar som palett-PNG i samma storleksordning som de övriga bilderna.

## Övrigt

- `assets/images/` — 22 bilder i originalupplösning, `assets/fonts/` — typsnitt
- `content/`, `assets-all.txt`, `list-*.txt`, `urls.txt` — underlag från exporten
- Produktsidornas spec-tabeller är egna HTML-komponenter från exporten. Data
  för storleksflikarna ritas av embed-koden i webbläsaren och fanns därför inte
  i exporten — den hämtas i stället med `python3 tools/scrape_specs.py` från
  nasps.se och sparas i `tools/extracted/specs.json`.
