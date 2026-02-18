# Provara Interactive Playground

Browser-based, zero-install Provara vault editor and visualizer.

## Quick Start

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build
```

## Architecture

See [`docs/PLAYGROUND_ARCHITECTURE.md`](../../docs/PLAYGROUND_ARCHITECTURE.md) for detailed design.

### Directory Structure

```
playground/
├── src/
│   ├── components/        # React components
│   │   ├── Header.tsx
│   │   ├── LeftSidebar.tsx
│   │   ├── CentralCanvas.tsx
│   │   └── RightSidebar.tsx
│   ├── store/             # Zustand state management
│   │   └── playground.ts
│   ├── App.tsx            # Main app component
│   ├── main.tsx           # Entry point
│   └── index.css          # Tailwind styles
├── public/                # Static assets
├── index.html             # HTML template
├── package.json
├── vite.config.ts
├── tsconfig.json
└── tailwind.config.ts
```

## Features (MVP)

- ✅ Create cryptographic keypairs locally
- ✅ Append events (OBSERVATION, ATTESTATION, etc.)
- ✅ Real-time chain verification (when WASM integrated)
- ✅ Event list view with JSON inspector
- ✅ Vault export as NDJSON
- ✅ Dark mode support
- 🚧 D3 chain visualization (Phase 2)
- 🚧 Merkle tree viewer (Phase 2)

## Integration with WASM

Once `provara-rs/provara-core` is built and published:

```bash
npm run wasm:build
npm install @provara/core
```

Then in components, import and use the WASM functions:

```typescript
import * as Provara from '@provara/core';

const signed = Provara.sign_event(eventJson, privateKeyB64);
const verified = Provara.verify_chain(eventsJson);
```

## Performance Targets

- Load time: <2s
- Key generation: <100ms
- Event creation: <50ms
- Chain verification (100 events): <250ms

## License

Apache 2.0
