# Frontend Changes

## Code Quality Tooling (Prettier + ESLint)

### Prettier (code formatter)

- `frontend/.prettierrc` — formatting rules: 100-char line width, single quotes, 2-space indent, trailing commas, LF line endings
- `frontend/.prettierignore` — excludes `node_modules`
- Ran `prettier --write` on all three existing frontend files (`index.html`, `script.js`, `style.css`) to apply consistent formatting

### ESLint (static analysis)

- `frontend/eslint.config.js` — flat config targeting `script.js`; enforces `no-var`, `prefer-const`, `eqeqeq`, `no-undef`, `no-unused-vars`; browser globals (`document`, `window`, `fetch`, `marked`, etc.) declared to avoid false positives

### npm package

- `frontend/package.json` — dev-only package with `prettier` and `eslint`; defines four scripts:
  - `npm run format` — auto-format all files in place
  - `npm run format:check` — CI-safe check (exits non-zero if any file differs)
  - `npm run lint` — run ESLint on `script.js`
  - `npm run lint:fix` — auto-fix ESLint issues
  - `npm run quality` — run both `format:check` and `lint` in sequence

### Developer scripts (repo root `scripts/`)

- `scripts/frontend-format.sh` — installs deps if needed, then runs `npm run format`
- `scripts/frontend-quality.sh` — installs deps if needed, then runs `npm run quality` (format check + lint)

## Dark/Light Theme Toggle

Added a dark/light theme toggle button to the header.

### `frontend/index.html`
- Wrapped `#newChatButton` in a new `.header-actions` flex container
- Added `#themeToggleButton` with inline SVG sun/moon icons and accessibility attributes

### `frontend/style.css`
- Added `--code-bg` CSS variable to `:root` (dark default: `rgba(0,0,0,0.2)`)
- Added `[data-theme="light"]` block with light theme variable overrides
- Added smooth `transition` rule on `body, body *` (0.3s ease)
- Added `.header-actions` and `.theme-toggle-btn` styles
- CSS-driven sun/moon icon visibility with rotate+scale animation on switch
- Replaced hardcoded `rgba(0, 0, 0, 0.2)` in code block rules with `var(--code-bg)`

### `frontend/script.js`
- Added `themeToggleButton` DOM reference
- Added `initTheme()` (reads `localStorage`) and `toggleTheme()` (toggles `data-theme` on `<html>`)
- Called `initTheme()` in `DOMContentLoaded` and wired toggle button click

### Behaviour
- Default theme is dark; clicking the toggle switches to light mode and persists to `localStorage`
- All transitions are smooth (0.3s ease)
