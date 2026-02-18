# Provara Interactive Playground

This is a browser-based WASM playground for the Provara Protocol. It allows users to create vaults, append events, and verify causal chains entirely in the browser.

## Tech Stack

- **Framework**: [Next.js](https://nextjs.org/)
- **Styling**: Tailwind CSS
- **Core Logic**: Rust via WASM (`provara-rs`)
- **Icons**: Lucide React

## Development

1.  **Build the WASM core**:
    ```bash
    npm run wasm:build
    ```
2.  **Install dependencies**:
    ```bash
    npm install
    ```
3.  **Run the development server**:
    ```bash
    npm run dev
    ```

## Project Structure

- `src/components`: UI components (Vault visualizer, Event editor, etc.)
- `src/hooks`: React hooks for vault state management.
- `src/lib/wasm`: Generated WASM bindings from `provara-rs`.
- `src/lib/store.ts`: Client-side state for the current vault session.

## Architecture

The playground is **Zero Backend**. All cryptographic operations and vault storage (in `localStorage`) happen on the client side. This demonstrates the self-sovereign nature of the protocol.
