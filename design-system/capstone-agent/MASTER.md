# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Capstone Agent
**Generated:** 2026-09-30 04:55:32
**Category:** Scientific grid operations workspace
**Design Dials:** Motion 2/10 (restrained) | Density 7/10 (engineering)

> **Product override:** This file is a token draft for the existing Capstone App and the Thread redesign. It is not a generic landing-page recipe. The current App CSS and `docs/superpowers/specs/2026-09-30-capstone-ui-wireframes.md` are the product sources of truth. Hero sections, marketing CTAs, glow effects, and decorative staggered motion do not apply to the Thread workspace.

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#102126` | `--color-primary` |
| On Primary | `#E9EFED` | `--color-on-primary` |
| Secondary | `#13272B` | `--color-secondary` |
| On Secondary | `#E9EFED` | `--color-on-secondary` |
| Accent/CTA | `#7CDBC8` | `--color-accent` |
| On Accent/CTA | `#0A2728` | `--color-on-accent` |
| Background | `#081216` | `--color-background` |
| Foreground | `#E9EFED` | `--color-foreground` |
| Card | `#102126` | `--color-card` |
| Card Foreground | `#E9EFED` | `--color-card-foreground` |
| Muted | `#13272B` | `--color-muted` |
| Muted Foreground | `#98A9A9` | `--color-muted-foreground` |
| Border | `#20353A` | `--color-border` |
| Destructive | `#DC9789` | `--color-destructive` |
| On Destructive | `#081216` | `--color-on-destructive` |
| Ring | `#7CDBC8` | `--color-ring` |

**Color Notes:** Dark terminal + running green + failed red + queued amber

### Typography

- **Heading Font:** Inter, with Chinese system fallbacks
- **Body Font:** Inter, with Chinese system fallbacks
- **Metadata Font:** SFMono-Regular, Consolas, Liberation Mono, monospace
- **Mood:** scientific operations, evidence, topology, precise and quiet
- **External font downloads:** not required; use the existing App stack for deterministic local rendering.

### Spacing Variables

*Density: 7/10 — Standard*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #7CDBC8;
  color: #0A2728;
  padding: 10px 17px;
  border: 1px solid #90E7D4;
  border-radius: 3px;
  font-weight: 600;
  transition: background 180ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  background: #A6F0DF;
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #BFD0C9;
  border: 1px solid #355357;
  padding: 10px 17px;
  border-radius: 3px;
  font-weight: 600;
  transition: border-color 180ms ease, color 180ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #102126;
  border: 1px solid #20353A;
  border-radius: 3px;
  padding: 17px 19px;
}

.card:hover {
  border-color: #315C57;
}
```

### Inputs

```css
.input {
  padding: 10px 12px;
  color: #E9EFED;
  background: #0C191D;
  border: 1px solid #20353A;
  border-radius: 3px;
  font-size: 16px;
  transition: border-color 180ms ease;
}

.input:focus {
  border-color: #7CDBC8;
  outline: none;
  box-shadow: 0 0 0 3px #7CDBC820;
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: #102126;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

The page-pattern guidance below applies only to standalone documentation or catalog surfaces. The Thread workspace uses the two-pane geometry and state walkthroughs in `docs/superpowers/specs/2026-09-30-capstone-ui-wireframes.md`; it has no hero section or marketing CTA.

**Style:** Dark Mode (OLED)

**Keywords:** Dark theme, low light, high contrast, deep black, midnight blue, eye-friendly, OLED, night mode, power efficient

**Best For:** Night-mode apps, coding platforms, entertainment, eye-strain prevention, OLED devices, low-light

**Key Effects:** Minimal glow (text-shadow: 0 0 10px), dark-to-light transitions, low white emission, high readability, visible focus

### Page Pattern

**Pattern Name:** Real-Time / Operations Landing

- **Conversion Strategy:** Offer a demo or sandbox and show trust signals. Label telemetry as live only when backed by a current source, with update time and stale state. Provide pause/hide or update-frequency controls for tickers and previews, stop offscreen/hidden work, support keyboard controls, and render a static final snapshot under reduced motion.
- **CTA Placement:** Primary CTA in nav + After metrics
- **Section Order:** Hero (product + live preview or status) > Key metrics/indicators > How it works > CTA (Start trial / Contact)

---

## Motion

**Stagger List** (Standard) — Trigger: load or scroll | Duration: 300-450ms | Easing: `back.out(1.4)`

```js
gsap.from('.grid-item', { opacity: 0, scale: 0.92, y: 16, duration: 0.4, stagger: { each: 0.06, from: 'start', grid: 'auto' }, ease: 'back.out(1.4)' });
```

**Framework notes:** grid: 'auto' lets GSAP infer rows/columns from a CSS grid layout for a natural wave stagger; Use matchMedia('(prefers-reduced-motion: reduce)') to skip non-essential motion and render the final state immediately

- ✅ Combine with from: 'center' for a bento-grid layout to draw the eye inward first
- ❌ Don't use back.out on dense data tables; the overshoot reads as sloppy on informational UI
- ⚡ Group DOM writes; avoid interleaving layout reads (getBoundingClientRect) between staggered tweens

---

## Anti-Patterns (Do NOT Use)

- ❌ Slow dashboards
- ❌ decorative charts
- ❌ hidden error states

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
