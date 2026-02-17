# Cloudflare Pages Deployment Guide

This file maps each domain to the static site directory in this repo and provides exact setup steps.

## 1) Domain -> Directory Mapping

- `provara.dev` -> `sites/provara-dev/`
- `provara.app` -> `sites/provara-app/`
- `huntinformationsystems.com` -> `sites/huntinformationsystems/`

No build step is required for any site.

## 2) Create Cloudflare Pages Projects

Create three separate Cloudflare Pages projects connected to this repo.

### Project A: `provara-dev`

- Production branch: `main`
- Framework preset: `None`
- Build command: *(leave empty)*
- Build output directory: `sites/provara-dev`
- Root directory (optional): `/`

### Project B: `provara-app`

- Production branch: `main`
- Framework preset: `None`
- Build command: *(leave empty)*
- Build output directory: `sites/provara-app`
- Root directory (optional): `/`

### Project C: `huntinformationsystems`

- Production branch: `main`
- Framework preset: `None`
- Build command: *(leave empty)*
- Build output directory: `sites/huntinformationsystems`
- Root directory (optional): `/`

## 3) Attach Custom Domains in Cloudflare Pages

Attach these domains to their corresponding Pages projects:

- Project `provara-dev`:
  - `provara.dev`
  - `www.provara.dev` (optional)
- Project `provara-app`:
  - `provara.app`
  - `www.provara.app` (optional)
- Project `huntinformationsystems`:
  - `huntinformationsystems.com`
  - `www.huntinformationsystems.com` (optional)

Cloudflare will prompt for DNS records; accept auto-creation when offered.

## 4) DNS Records (if adding manually)

In Cloudflare DNS for each zone, use `CNAME` records to the Pages target shown in each project (for example: `project-name.pages.dev`).

Typical pattern:

- Apex/root: `@` -> `project-name.pages.dev` (`CNAME`, proxied)
- WWW: `www` -> `project-name.pages.dev` (`CNAME`, proxied)

If your registrar is outside Cloudflare, delegate nameservers to Cloudflare first.

## 5) SSL/TLS

In Cloudflare SSL/TLS settings:

- Mode: `Full` (or `Full (strict)` if origin cert setup requires it)
- Enable `Always Use HTTPS`
- Enable `Automatic HTTPS Rewrites`

## 6) Cache and Performance Baseline

For all three projects:

- Caching level: Standard
- Auto minify: optional (HTML/CSS/JS)
- Brotli: enabled
- Rocket Loader: disabled (not needed)

## 7) Deployment Verification Checklist

After first deploy, verify:

- `https://provara.dev/` loads and nav links work.
- `https://provara.app/` loads hero/features/how-it-works/CTAs.
- `https://huntinformationsystems.com/` loads about/contact/legal links.
- Mobile rendering at ~390px width is usable (no horizontal overflow).
- OG metadata resolves in social preview tools.
- Favicons load on all three domains.

## 8) Optional: branch previews

Enable preview deployments on pull requests for visual QA before merging.

Recommended:

- Keep production on `main`
- Use preview URLs for design/content review

## 9) Rollback

Cloudflare Pages supports rollback to prior deployments from the project Deployments tab.

If a bad deploy lands:

1. Open project -> Deployments
2. Select previous healthy deployment
3. Click rollback/redeploy

## 10) Ownership Notes

- `provara.dev`: protocol/spec/compliance audience
- `provara.app`: product narrative + conversion
- `huntinformationsystems.com`: corporate/legal presence

Keep content boundaries clean to avoid brand drift.
