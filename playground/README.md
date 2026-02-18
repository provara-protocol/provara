# Provara Interactive Playground

Browser-based playground for the Provara Protocol. Create vaults, append events, and verify causal chains entirely in the browser using WebCrypto.

**Live Demo:** https://provara-protocol.github.io/provara/

## Tech Stack

- **Framework**: React + Vite + TypeScript
- **Crypto**: WebCrypto API (Ed25519 via WebCrypto)
- **Styling**: Tailwind CSS
- **Icons**: Lucide React

## Quick Start

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build
```

## Project Structure

```
playground/
├── src/
│   ├── components/     # UI components
│   ├── hooks/          # React hooks for vault state
│   ├── lib/
│   │   ├── crypto/     # WebCrypto Ed25519 primitives
│   │   └── store.ts    # Client-side vault state
│   └── App.tsx
├── public/
│   └── CNAME           # Custom domain (playground.provara.dev)
├── dist/               # Production build (deployed to GitHub Pages)
└── index.html
```

## Architecture

**Zero Backend.** All cryptographic operations run in the browser. Vault state persists in `localStorage`. No data leaves your machine.

## Deployment

The playground deploys automatically to GitHub Pages on push to `main` when files in `playground/` change.

### Custom Domain

To activate the custom domain:

1. In GitHub repo **Settings → Pages → Custom domain**, enter `playground.provara.dev`
2. In your DNS provider, add a CNAME record:
   ```
   playground.provara.dev.  CNAME  provara-protocol.github.io.
   ```
3. Wait for DNS propagation (up to 48 hours)

The `public/CNAME` file is already configured. GitHub Pages will pick it up automatically once the domain is added in Settings.

## License

Apache 2.0
