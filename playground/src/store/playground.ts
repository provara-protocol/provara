/**
 * Playground Store — Zustand state management
 *
 * Single source of truth for vault events, keypair, verification state, and UI.
 * All crypto operations call provara-crypto.ts (WebCrypto-based implementation).
 */

import { create } from 'zustand';
import {
  generateKeypair,
  createEvent,
  verifyChain,
  type ProvaraKeypair,
  type ProvaraEvent,
  type ChainVerifyResult,
} from '../lib/provara-crypto';

interface VaultState {
  events: ProvaraEvent[];
}

interface UiState {
  selected_event_id: string | null;
  view_mode: 'list' | 'graph' | 'merkle';
  sidebar_open: boolean;
  loading: boolean;
  error: string | null;
}

interface PlaygroundStore {
  // Vault
  vault: VaultState;

  // Active keypair (single actor per session)
  keypair: ProvaraKeypair | null;

  // Verification result
  verification: ChainVerifyResult | null;

  // UI state
  ui: UiState;

  // Actions
  actions: {
    initVault: () => Promise<void>;
    appendEvent: (eventType: string, payload: unknown) => Promise<void>;
    verifyVault: () => Promise<void>;
    setSelectedEvent: (id: string | null) => void;
    setViewMode: (mode: 'list' | 'graph' | 'merkle') => void;
    toggleSidebar: () => void;
    resetVault: () => void;
    exportVaultJson: () => string;
    clearError: () => void;
  };
}

export const usePlaygroundStore = create<PlaygroundStore>((set, get) => ({
  vault: { events: [] },
  keypair: null,
  verification: null,

  ui: {
    selected_event_id: null,
    view_mode: 'list',
    sidebar_open: true,
    loading: false,
    error: null,
  },

  actions: {
    // Generate a new keypair and create the genesis OBSERVATION event
    initVault: async () => {
      set((s) => ({ ui: { ...s.ui, loading: true, error: null } }));
      try {
        const kp = await generateKeypair();
        const genesis = await createEvent(
          'OBSERVATION',
          { subject: 'vault', predicate: 'created', value: 'genesis' },
          kp.private_key_b64,
          kp.key_id,
          undefined,
        );
        set({
          keypair: kp,
          vault: { events: [genesis] },
          verification: null,
          ui: {
            selected_event_id: null,
            view_mode: 'list',
            sidebar_open: true,
            loading: false,
            error: null,
          },
        });
      } catch (err) {
        set((s) => ({
          ui: { ...s.ui, loading: false, error: String(err) },
        }));
      }
    },

    // Append a signed event to the vault
    appendEvent: async (eventType: string, payload: unknown) => {
      const { keypair, vault } = get();
      if (!keypair) {
        set((s) => ({
          ui: { ...s.ui, error: 'No keypair — create vault first.' },
        }));
        return;
      }
      set((s) => ({ ui: { ...s.ui, loading: true, error: null } }));
      try {
        // prev_event_hash = event_id of the last event by this actor
        const actorEvents = vault.events.filter((e) => e.actor === keypair.key_id);
        const prevHash =
          actorEvents.length > 0
            ? actorEvents[actorEvents.length - 1].event_id
            : undefined;

        const event = await createEvent(
          eventType,
          payload,
          keypair.private_key_b64,
          keypair.key_id,
          prevHash,
        );
        set((s) => ({
          vault: { events: [...s.vault.events, event] },
          verification: null, // stale — needs re-verify
          ui: { ...s.ui, loading: false },
        }));
      } catch (err) {
        set((s) => ({
          ui: { ...s.ui, loading: false, error: String(err) },
        }));
      }
    },

    // Verify the entire chain: causal integrity + signatures
    verifyVault: async () => {
      const { keypair, vault } = get();
      if (!keypair || vault.events.length === 0) {
        set({ verification: { valid: false, errors: ['Vault is empty'] } });
        return;
      }
      set((s) => ({ ui: { ...s.ui, loading: true, error: null } }));
      try {
        const result = await verifyChain(vault.events, keypair.public_key_b64);
        set((s) => ({
          verification: result,
          ui: { ...s.ui, loading: false },
        }));
      } catch (err) {
        set((s) => ({
          verification: { valid: false, errors: [String(err)] },
          ui: { ...s.ui, loading: false },
        }));
      }
    },

    setSelectedEvent: (id) =>
      set((s) => ({ ui: { ...s.ui, selected_event_id: id } })),

    setViewMode: (mode) =>
      set((s) => ({ ui: { ...s.ui, view_mode: mode } })),

    toggleSidebar: () =>
      set((s) => ({ ui: { ...s.ui, sidebar_open: !s.ui.sidebar_open } })),

    resetVault: () =>
      set({
        vault: { events: [] },
        keypair: null,
        verification: null,
        ui: {
          selected_event_id: null,
          view_mode: 'list',
          sidebar_open: true,
          loading: false,
          error: null,
        },
      }),

    exportVaultJson: () => {
      const { vault, keypair } = get();
      return JSON.stringify(
        {
          version: '1.0',
          exported_at: new Date().toISOString(),
          actor_key_id: keypair?.key_id ?? null,
          events: vault.events,
        },
        null,
        2,
      );
    },

    clearError: () => set((s) => ({ ui: { ...s.ui, error: null } })),
  },
}));
