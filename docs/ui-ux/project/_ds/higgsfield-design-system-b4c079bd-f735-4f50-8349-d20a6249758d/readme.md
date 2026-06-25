# Higgsfield Design System

A dark-native, cinematic design system for **Higgsfield** — the AI-native creative suite for generating images, video and audio from prompts or references. This project encodes Higgsfield's visual language as tokens, reusable React components, foundation specimens and a full product UI kit so design agents can produce on-brand interfaces, mocks, decks and assets.

> **Sources** — built by studying the live product at **https://higgsfield.ai/** (homepage, generators, Canvas, Marketing Studio, Soul/Moodboards docs). No Figma file or codebase was provided. The reader is not assumed to have access; links are recorded for provenance. See **Caveats** for substitutions made without source binaries.

---

## What Higgsfield is

Higgsfield is a browser-based, multi-model creative platform. From one prompt box you generate cinematic **video**, photoreal **images** and **audio**, switching between proprietary models (**Soul 2.0**, **Seedance**, Higgsfield Lite/Standard/Turbo) and frontier partner engines (**Sora 2**, **Kling 3.0**, **Veo 3.1**, **Nano Banana Pro**, **Grok Imagine**). Signature capabilities: camera-control presets (dolly, crash zoom, bullet time, FPV), **Effects Mix** (stacked VFX), **Soul ID** character consistency, **Moodboards**, and a library of **viral presets** (Drift Racing, Kung Fu Hit, Neon City…). Higher surfaces: **Marketing Studio**, **Cinema Studio**, **AI Influencer**, node-based **Canvas**, **Supercomputer** (super-agent), and **MCP & CLI**.

**Audience:** solo creators, social teams, agencies and indie filmmakers who want studio-grade motion without a set.

**Products represented in this system:**
- **Web App** (`ui_kits/web-app/`) — the core Explore → prompt → generate workspace. *(Built.)*
- Marketing/Cinema studios, Canvas and mobile are referenced in nav but not yet recreated as kits — see Caveats.

---

## Content fundamentals

How Higgsfield writes — mirror this in any copy you produce.

- **Voice:** confident, cinematic, maker-to-maker. It sells *capability and scale*, not hype. "Big-budget visual effects, from explosions to surreal transformations." "One superagent for your entire creative stack."
- **Person:** speaks to **you** ("What will you create today?", "Turn Claude into a creative engine"). First-person plural ("our latest AI photo model") only in product/release notes.
- **Casing:** **Sentence case** for UI labels, body and most headings. **UPPERCASE** is reserved for two things: tiny eyebrows/kickers (tracked-out) and **VFX / preset names over media** (DRIFT RACING, KUNG FU HIT) — bold, lightly tracked. Model names keep their own casing (Seedance 2.0, Nano Banana Pro).
- **Length:** punchy. Headlines are short and declarative; sub-lines are one cinematic sentence. Feature cards are a 2–4 word title + a single benefit line ("Create high-quality videos in seconds").
- **Badges:** terse, ALL-CAPS or TitleCase flags — `New`, `PRO`, `4K`, `Trending`.
- **Numbers/specs read like a spec sheet** and live in monospace where technical: `seedance_2_0 · 4K · 1280×720 · 120 credits`.
- **Emoji:** **none.** The brand never uses emoji in product UI. Iconography and bold type carry emphasis instead.
- **Vibe words:** cinematic, native 4K, controllable, consistent, viral, premium, big-budget, frontier.

Examples to imitate: "Four times the resolution. The same cinematic magic." · "Every idea, brought to life on screen." · "No camera required."

---

## Visual foundations

- **Mode:** dark-native only. Near-black canvas `#0B0C0E` (brand base `#0F1113`), layered surfaces `#141619 → #1A1D21 → #22262B`. **Imagery carries all the color**; the chrome stays neutral.
- **Color use:** essentially monochrome. The **primary action is white** (`#FFFFFF` fill, near-black text) — the signature CTA. A single **cinematic mint** accent (`#4FE0A6`) appears sparingly for success / live-ready / focus glints. Semantic set: mint success, amber warning/PRO, red danger, blue info, plus a hot-pink **live/render** pulse (`#FF4D6D`).
- **Type:** one neutral grotesque (Geist here — see Caveats; the live site uses an Inter/SF-Pro-class face). Display is **tight-tracked** (`-0.03em`) and bold; body is 15px / 1.45. Eyebrows and VFX labels are **uppercase, tracked-out**. Technical strings are monospace (Geist Mono).
- **Backgrounds:** full-bleed media tiles and gradients; no patterns, no hand-drawn illustration, no skeuomorphism. Decorative gradients are restrained — mostly **scrims** over media (bottom-up black) and faint top **sheen** on cards, not rainbow fills. Avoid bluish-purple gradient slop.
- **Imagery vibe:** cinematic, filmic — moody, vignetted, often desaturated-with-one-light-source; warm OR cool but always graded. Grain is welcome. (The placeholder media in `assets/placeholders/` mimics this: dark gradient + bloom + vignette + grain.)
- **Corners:** generous, consistent rounding. Controls/inputs `12px`, cards `16px`, media tiles `20px`, sheets/hero `28px`, chips/avatars pill.
- **Cards:** flat dark surface + **hairline white-alpha border** (`rgba(255,255,255,.10)`) + inner **top-sheen**; shadow only on raised/hover. No heavy drop shadows at rest. Clickable cards **lift `-2px`** and brighten their border.
- **Borders & dividers:** white-alpha hairlines (6 / 10 / 18%), so they read on any surface.
- **Elevation:** deep, soft shadows for true overlays (modals, menus, toasts); on flat cards, elevation is implied by border + sheen, not shadow.
- **Glass / blur:** frosted chrome over media — toolbars, model pills, media-overlay buttons use `backdrop-filter: blur(18px)` on a translucent dark fill with a white-alpha border.
- **Transparency:** used for chrome over imagery (glass) and for text/border alpha ramps — not for whole panels of the app shell.
- **Motion:** quick and confident. Default ease-out `cubic-bezier(.22,1,.36,1)`, 140–220ms. Hover = subtle lift + image scale (`1.045`) + scrim deepen. Press = `scale(.97)`. Toggles/segmented use a gentle spring overshoot. The render/live dot **pulses**. No bounce on content, no infinite decorative loops.
- **Hover/press conventions:** hover lightens fills (6%→10%→16%) and text (secondary→primary); primary white button darkens (`#E4E6EA`); press shrinks. Focus = white `focus-visible` ring (2px gap + 2px ring) on dark.
- **Layout:** app shell is a fixed **248px sidebar** + top bar (`60px`) + scrolling content. Media galleries are dense CSS grids with `12px` gutters. Content max-width ~1280px, centered.

Full specimens live in the **Design System** tab (Colors, Type, Spacing, Brand groups).

---

## Iconography

- **Style:** clean **line icons**, ~2px stroke, rounded caps/joins, 24px grid — monochrome, inheriting `currentColor` (white at full/again dimmed by text-alpha). No filled/duotone icon style in chrome; fills appear only for tiny marks (the star "spark" mark, play triangles).
- **The brand mark** is the wordmark "Higgsfield" set in the grotesque, plus an `H` monogram tile. Filled **4-point star / sparkle** is the recurring motif for "generate / AI / model".
- **In this system:** the Web App kit renders icons from an embedded **Lucide** line set (`ui_kits/web-app/icons.jsx`) — Lucide (ISC) is the closest CDN-available match to Higgsfield's custom line icons. *Substitution flagged* — swap for the official icon set if provided.
- **Emoji / unicode as icons:** never. Use the line set.
- **Assets on disk:** `assets/logo/` (recreated wordmark + monogram, replace with official binaries), `assets/placeholders/` (14 cinematic gradient stand-ins for media). No official photographic/illustration assets were available to copy.

---

## Index / manifest

**Root**
- `styles.css` — the single entry consumers link; `@import`s the token + font layers and the base reset.
- `tokens/` — `colors.css`, `typography.css`, `spacing.css`, `effects.css`, `fonts.css`, `base.css`.
- `assets/` — `logo/` (wordmark, monogram), `placeholders/` (cinematic media stand-ins).
- `readme.md` — this file. `SKILL.md` — Agent-Skills entry point.

**Foundation cards** (`guidelines/foundations/`, shown in the Design System tab)
- Colors: Surfaces · Text & Action · Semantic & State · Borders & Fills
- Type: Display Scale · Body & UI Text · Eyebrow/VFX/Mono
- Spacing: Space Scale · Radii · Elevation & Shadows
- Brand: Logo & Mark · Glass & Media Scrim

**Components** (`components/`, namespace `window.HiggsfieldDesignSystem_*`)
- `core/` — **Button, IconButton, Badge, Tag, Avatar, Spinner**
- `forms/` — **Input, Select, Switch, SegmentedControl, Slider**
- `feedback/` — **Tooltip, Dialog, Toast (+ ToastStack)**
- `media/` — **Card, MediaCard, ModelPill, PromptComposer**

Each directory has a `*.card.html` (Components group) demoing its variants. Every component ships `<Name>.jsx` + `<Name>.d.ts` + `<Name>.prompt.md`.

**UI kits** (`ui_kits/`)
- `web-app/` — interactive Explore → generate workspace (`index.html` orchestrates `Sidebar`, `TopBar`, `ExploreView`, `CreateView`, a model menu, `data.js`, `icons.jsx`, `kit.css`).

---

## Caveats & open questions

1. **No Figma or codebase** was provided — the system is a faithful *interpretation* of the public site, not a pixel extraction. If you have the real design files/tokens, share them and I'll reconcile exact values.
2. **Fonts substituted.** I shipped **Geist / Geist Mono** (loaded via Google Fonts) as a close neutral-grotesque stand-in. **Please send the official Higgsfield webfonts** and I'll wire real `@font-face` binaries.
3. **Logo recreated as text**, not official artwork. **Please provide the official logo SVG/PNG** (wordmark + mark, light/dark).
4. **Icons = Lucide** line set as the nearest CDN match. Provide the official icon set to swap in.
5. **Media is placeholder** — abstract cinematic gradients I generated, not real Higgsfield outputs. Drop in real stills/posters for production-grade mocks.
6. **Accent color** (mint `#4FE0A6`) is my read of the brand's sparing accent usage; confirm the official accent/semantic hexes.
7. **One UI kit built** (Web App). Want Marketing Studio, Canvas (node editor), the mobile app, or a slide template next? Tell me which surface matters most.
