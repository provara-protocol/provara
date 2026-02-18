/**
 * Playground Store — Zustand-based state management
 * 
 * Single source of truth for:
 * - Vault state (events, manifest, hashes)
 * - Key management
 * - UI state (view mode, selections)
 */

import { create } from 'zustand';

export interface Event {
  event_id: string;
  actor: string;
  event_type: 'GENESIS' | 'OBSERVATION' | 'ATTESTATION' | 'RETRACTION' | string;
  timestamp: string;
  prev_event_hash: string | null;
  content?: string;
  sig?: string;
  namespace?: 'canonical' | 'local' | 'contested' | 'archived';
}

export interface KeyPair {
  public_key: string;
  key_id: string;
  private_key?: string; // Only if generated locally
}

export interface VerificationResult {
  valid: boolean;
  chain_integrity: boolean;
  all_sigs_valid: boolean;
  errors: string[];
}

interface PlaygroundStore {
  // Vault state
  vault: {
    events: Event[];
    state_hash: string;
    merkle_root: string;
  };

  // Keys
  keys: KeyPair[];
  current_key_id: string | null;

  // UI state
  ui: {
    selected_event_id: string | null;
    view_mode: 'list' | 'graph' | 'merkle';
    sidebar_open: boolean;
    theme: 'light' | 'dark';
  };

  // Verification state
  verification: VerificationResult | null;

  // Actions
  actions: {
    appendEvent: (event: Event) => void;
    verifyChain: () => void;
    setSelectedEvent: (id: string | null) => void;
    setViewMode: (mode: 'list' | 'graph' | 'merkle') => void;
    toggleSidebar: () => void;
    setCurrentKey: (key_id: string) => void;
    addKey: (key: KeyPair) => void;
    resetVault: () => void;
    exportVaultJSON: () => string;
  };
}

export const usePlaygroundStore = create<PlaygroundStore>((set, get) => ({
  vault: {
    events: [],
    state_hash: '',
    merkle_root: '',
  },

  keys: [],
  current_key_id: null,

  ui: {
    selected_event_id: null,
    view_mode: 'list',
    sidebar_open: true,
    theme: 'light',
  },

  verification: null,

  actions: {
    appendEvent: (event: Event) => {
      set((state) => ({
        vault: {
          ...state.vault,
          events: [...state.vault.events, event],
        },
      }));
    },

    verifyChain: () => {
      const { vault } = get();
      // TODO: Call WASM verify_chain(vault.events)
      const result: VerificationResult = {
        valid: true,
        chain_integrity: true,
        all_sigs_valid: true,
        errors: [],
      };
      set({ verification: result });
    },

    setSelectedEvent: (id: string | null) => {
      set((state) => ({
        ui: { ...state.ui, selected_event_id: id },
      }));
    },

    setViewMode: (mode) => {
      set((state) => ({
        ui: { ...state.ui, view_mode: mode },
      }));
    },

    toggleSidebar: () => {
      set((state) => ({
        ui: { ...state.ui, sidebar_open: !state.ui.sidebar_open },
      }));
    },

    setCurrentKey: (key_id) => {
      set({ current_key_id: key_id });
    },

    addKey: (key) => {
      set((state) => ({
        keys: [...state.keys, key],
        current_key_id: key.key_id,
      }));
    },

    resetVault: () => {
      set({
        vault: { events: [], state_hash: '', merkle_root: '' },
        current_key_id: null,
      });
    },

    exportVaultJSON: () => {
      const { vault } = get();
      return JSON.stringify(
        {
          manifest: {
            version: '1.0',
            created_at: new Date().toISOString(),
          },
          events: vault.events,
        },
        null,
        2
      );
    },
  },
}));
