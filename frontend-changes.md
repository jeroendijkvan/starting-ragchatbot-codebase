# Frontend Changes: Dark/Light Theme Toggle

## Summary
Added a dark/light theme toggle button to the header that lets users switch between the existing dark theme and a new light theme.

## Files Modified

### `frontend/index.html`
- Wrapped the existing `#newChatButton` in a new `.header-actions` flex container
- Added `#themeToggleButton` before the new chat button with two inline SVG icons (sun and moon) and proper `aria-label`/`title` attributes for accessibility

### `frontend/style.css`
- Added `--code-bg` CSS variable to `:root` (dark default: `rgba(0,0,0,0.2)`)
- Added `[data-theme="light"]` block with all light theme variable overrides:
  - `--background: #f1f5f9` (light slate background)
  - `--surface: #ffffff` (white surfaces)
  - `--surface-hover: #e2e8f0`
  - `--text-primary: #0f172a` (near-black for contrast)
  - `--text-secondary: #64748b`
  - `--border-color: #cbd5e1`
  - `--code-bg: rgba(0,0,0,0.06)` (subtle code block tint)
- Added smooth `transition` rule on `body, body *` for background-color, color, border-color, and box-shadow (0.3s ease)
- Added `.header-actions` flex container styles
- Added `.theme-toggle-btn` styles matching the existing design aesthetic
- Added CSS-driven sun/moon icon visibility: sun visible in dark mode, moon visible in light mode, with rotate+scale animation on switch
- Replaced hardcoded `rgba(0, 0, 0, 0.2)` in code block rules with `var(--code-bg)`

### `frontend/script.js`
- Added `themeToggleButton` DOM reference
- Added `initTheme()`: reads `localStorage` key `theme` on load and applies `data-theme="light"` to `<html>` if saved
- Added `toggleTheme()`: toggles `data-theme` attribute on `<html>` element and persists the choice to `localStorage`
- Called `initTheme()` in `DOMContentLoaded` before other setup
- Wired `themeToggleButton` click to `toggleTheme()` in `setupEventListeners()`

## Behaviour
- Default theme is dark (no `data-theme` attribute)
- Clicking the toggle button switches to light mode (`data-theme="light"` on `<html>`)
- Clicking again returns to dark mode
- Preference is saved in `localStorage` and restored on page reload
- All transitions are smooth (0.3s ease)
- Button shows sun icon in dark mode (indicating "switch to light") and moon icon in light mode (indicating "switch to dark")
- Button is keyboard-navigable and has an accessible label
