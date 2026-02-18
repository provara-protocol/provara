# Sites Deployment

This repository publishes one GitHub Pages site from `sites/provara.dev/`.

## Domains
- `provara.dev` -> main documentation + spec site
- `playground.provara.dev` -> recommended as a separate Pages project/repo, or DNS redirect to `https://provara.dev/playground/`

## Why this layout
GitHub Pages supports one active Pages deployment per repository. To avoid collisions:
- `.github/workflows/site.yml` is the only Pages deploy workflow.
- `.github/workflows/playground.yml` now builds playground artifacts without deploying Pages.

## Current paths
- Landing: `/`
- Version-locked spec: `/spec/v1.0/`
- Docs hub: `/docs/`
- Playground redirect page: `/playground/`
- Blog + RSS: `/blog/`, `/rss.xml`

## Build locally
```bash
python tools/site/build_provara_dev.py
```

The builder is deterministic and emits only static HTML/CSS plus sitemap/RSS/robots.
