# Design brief — paste this into Lovable / v0 / Figma Make

The dashboard in `src/static/` is already built in this style. Use this brief only if
you want to explore a different look in a design tool first. Whatever comes back,
**keep the element ids and class names listed at the bottom** or `app.js` stops working.

---

## The prompt

> Design a web dashboard called **ShipCheck** for a shipping documentation team at a
> freight forwarder. The team receives hundreds of customer emails a day; the product
> sorts them and checks a draft Bill of Lading against the customer's Shipping
> Instruction, field by field, and escalates anything it isn't sure about to a person.
>
> **Audience:** logistics operations staff and their managers. The tone is calm,
> corporate, trustworthy — think a bank's internal ops console, not a startup landing
> page. No gradients, no glassmorphism, no emoji, no AI sparkles.
>
> **Look:** near-black left sidebar (#121316) with a single warm orange accent
> (#F26B1D). Light grey workspace (#F4F5F7), white cards with a 14px radius, 1px
> #E6E8EC borders and a very soft shadow. Inter throughout — no serif. Tight
> letter-spacing on headings (-0.02em), tabular numbers on statistics.
>
> **Layout:**
> - Fixed 252px sidebar, full viewport height, never scrolls with the page: logo block
>   at top, then small uppercase section labels ("Operations", "Workspace") over nav
>   items with 18px line icons. The active item is a solid orange rounded rectangle
>   with white text. A badge count sits right-aligned inside one nav item. At the
>   bottom of the sidebar, a dark card showing system status with a small green dot.
> - A flat sticky top bar (64px) that sits flush against the top of the content column
>   and **does not move, resize or detach when the page scrolls**: search field on the
>   left, a secondary link and a circular avatar on the right.
> - Page heading block: small orange uppercase eyebrow, 30px bold title, grey one-line
>   description.
> - A row of 5 statistic cards. Each is a horizontal card: a 40px rounded-square icon
>   tile (tinted background, matching icon colour) on the left, then a small grey
>   label above a large bold number. Tint the tile orange by default, red for a
>   "problem" metric, amber for a "waiting" metric, green for a "saved" metric.
> - Main area is a two-column split: a scrollable email list (380px, sticky) beside a
>   wide detail panel. List rows show a bold subject line and a row of small uppercase
>   status tags; the selected row gets a pale orange background and a 3px orange left
>   border.
> - The detail panel shows: status tags, subject, sender metadata, a coloured result
>   banner with a 4px left border, a comparison table (uppercase 10px column headers,
>   mismatching rows tinted red), a vertical timeline of what the system did with
>   coloured dots, and an action row with one solid orange primary button.
> - Below 1000px the sidebar slides off-canvas behind a hamburger in the top bar, with
>   a dark scrim; the split becomes one column.
>
> **Output:** a single self-contained HTML file plus one CSS file. Plain HTML/CSS/JS
> only — no React, no build step, no Tailwind CDN, no icon font (inline SVG icons).
> Define all colours as CSS custom properties on `:root`.

---

## Contract — these must survive any redesign

`app.js` reads and writes these. Renaming or removing one breaks the app silently.

**ids:** `app-name`, `ai-status`, `queue-count`, `eyebrow`, `page-title`, `page-sub`,
`stats`, `view-list`, `view-new`, `view-how`, `search`, `cat-chips`, `status-chips`,
`list`, `detail`, `modal`, `modal-body`, `new-form`, `new-status`, `menu-btn`, `scrim`

**classes / attributes:** `.tabs a[data-tab="inbox|queue|new|how"]` (gets `.active`),
`.count`, `.stat` + `.stat-ico` + `.n` + `.l` (+ modifiers `.bad` `.warn` `.ok`),
`.card`, `.split`, `.list-pane`, `.detail-pane`, `.row` + `.sel` + `.subj` + `.meta`,
`.chip` + `.on`, `.pill` + `.pill-ok|-bad|-amber|-info|-grey|-brand`, `.banner` +
`.ok|.bad|.warn|.grey`, `table.cmp` + `tr.mismatch|.blank|.clickable|.evidence`,
`.trace` + `li.warn|.fail`, `.doc`, `details.body`, `.review`, `.actions`,
`.btn` + `.btn-primary|-ok|-soft|-ghost`, `.how-step` + `.num`, `.bar` + `.track` +
`.fill`, `.modal-box`, `.modal-close`, `[data-example]`, `body.nav-open`
