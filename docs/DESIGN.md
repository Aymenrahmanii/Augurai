# Augurai site design

A reading and reference tool for one AI engineer, so scanability, search and a comfortable briefing outrank decoration. Revised 2026-11-20 to be quieter: neutral greys plus one accent colour.

## Direction

Swiss / minimal, monochrome. Hairline rules, plain surfaces, one blue accent used only for links, the active tab, focus rings and one chart series. No gradients, no glass, no coloured stripes, no boxed cards: lists are rows separated by 1px rules. Imagery is functional: GitHub avatars for people and project owners (with an initial as the fallback), and a neutral monogram for model providers.

## Tokens (`src/augurai/site/static/site.css`, `:root`)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#f6f7f8` | `#0e1013` | page |
| `--surface` | `#ffffff` | `#15181c` | header, tables, inputs |
| `--fg` | `#111418` | `#eceef1` | text |
| `--muted` | `#5b6370` | `#9aa1ad` | secondary text |
| `--line` / `--line-strong` | `#e3e5e9` / `#c9cdd4` | `#262a30` / `#3a3f47` | rules, borders |
| `--tint` | `#eef0f3` | `#1c2025` | table headers, hover, monograms |
| `--accent` | `#1d4ed8` | `#8ab0ff` | links, active nav, focus, first chart series |

The theme follows the system and can be switched with the header button; the choice is remembered in `localStorage`.

## Type and layout

Fira Sans for text, Fira Code for numbers. Body 16px / 1.6, briefing measure 68ch. Single column up to 960px; on the home page the briefing sits beside a side panel (counts, newest models, rising projects). The header is sticky; navigation scrolls inside it on narrow screens; wide tables scroll inside their own container with a sticky header row. Verified with no horizontal page scroll at 375px on every page.

## Interaction (progressive enhancement, `filter.js`)

Live search (`input[data-filter-text]`) over each `[data-item]`'s `data-text`; select filters (`select[data-filter]`); sorting (`select[data-sort]` with `data-sort-<key>` values, rows without a value always last); a live "N of M" count; the theme toggle. Without JavaScript every list stays complete and readable.

## Charts

One accent series, the rest neutral and told apart by weight and dash; legends are labelled directly at the line ends and spaced so they do not overlap.

## Constraints that shape the HTML

Templates expose `data-item`, `data-text`, `data-filter`, `data-sort`, `data-sortable`, `data-count`, `.chip`, `.rows`, `.table-scroll`, `.avatar`, `.mono`, `.num` and `svg.chart` series classes `s0`-`s5`; the CSS and script depend on them. Every control has a visible label, targets are at least 44px, focus rings are visible, and motion is limited to 150ms colour transitions (off under `prefers-reduced-motion`).
