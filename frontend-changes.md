# Frontend Code Quality Changes

## What was added

### Prettier (code formatter — frontend equivalent of black)

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

## Files formatted by Prettier on initial run

| File | Result |
|---|---|
| `frontend/index.html` | reformatted |
| `frontend/script.js` | reformatted |
| `frontend/style.css` | reformatted |
