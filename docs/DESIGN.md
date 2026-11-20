# Augurai site design

Chosen with the UI/UX Pro Max and Impeccable skills on 2026-11-20. The site is a reading and reference tool for one AI engineer, so scanability and a comfortable long-form briefing outrank decoration.

## Direction

Swiss / minimal. Plain surfaces, hairline rules, one blue, one amber. Data tables are dense and quiet; the daily briefing is a single narrow reading column. No cards-in-boxes: lists are rows separated by 1px rules. No kickers above headings, no gradients, no glass.

## Tokens (`src/augurai/site/static/site.css`, `:root`)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#f8fafc` | `#0b1220` | page |
| `--surface` | `#ffffff` | `#111a2c` | header, table body |
| `--fg` | `#0f172a` | `#e6ebf5` | text |
| `--muted` | `#475569` | `#a3b0c4` | secondary text (contrast above 4.5:1 on both backgrounds) |
| `--link` / `--primary` | `#1e40af` | `#9bb8ff` / `#8fb0ff` | links, selection |
| `--accent` | `#b45309` | `#fbbf24` | active-nav underline only |
| `--c0`..`--c5` | blue, amber, green, purple, rose, cyan | lighter variants | chart series |

Light or dark follows the visitor's system (`prefers-color-scheme`); there is no toggle.

## Type

Fira Sans (text) and Fira Code (numbers in tables and charts, inline code), loaded from Google Fonts. Body 16px / 1.6; briefing measure 68ch; headings use balanced wrapping and slight negative tracking; `h1` scales 1.75-2.5rem.

## Layout

Single column, max width 1040px, 16px gutter. Navigation scrolls horizontally inside the header on narrow screens instead of wrapping. Wide tables scroll inside their own container, so the page itself never scrolls sideways (checked at 375px). Project and people lists become two columns from 820px.

## Behaviour

Filters (`select[data-filter]`) are progressive enhancement: without JavaScript every row stays visible. Focus rings are visible everywhere, there is a skip link, motion is limited to 160ms colour transitions and is disabled under `prefers-reduced-motion`.

## Constraints that shape the HTML

Templates expose these hooks and the CSS depends on them: `data-item`, `data-filter`, `.chip`, `.cards`, `.table-scroll`, `.num`, and `svg.chart` with series classes `s0`-`s5`.
