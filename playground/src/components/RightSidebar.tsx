import React from 'react';
import { usePlaygroundStore } from '../store/playground';

export default function RightSidebar() {
  const verification = usePlaygroundStore((state) => state.verification);
  const vault = usePlaygroundStore((state) => state.vault);
  const verifyChain = usePlaygroundStore((state) => state.actions.verifyChain);

  return (
    <div className="p-6 space-y-6">
      {/* Verification Report */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          Verification
        </h2>

        <button
          onClick={verifyChain}
          className="w-full px-4 py-2 mb-4 bg-provara-600 text-white rounded-md hover:bg-provara-700 transition font-medium"
        >
          Verify Chain
        </button>

        {verification ? (
          <div className="space-y-2">
            <div className={`verification-badge ${verification.valid ? 'valid' : 'invalid'}`}>
              {verification.valid ? '✓' : '✗'} Chain Valid
            </div>
            <div className={`verification-badge ${verification.chain_integrity ? 'valid' : 'invalid'}`}>
              {verification.chain_integrity ? '✓' : '✗'} Chain Integrity
            </div>
            <div className={`verification-badge ${verification.all_sigs_valid ? 'valid' : 'invalid'}`}>
              {verification.all_sigs_valid ? '✓' : '✗'} Signatures Valid
            </div>

            {verification.errors.length > 0 && (
              <div className="mt-3 p-3 bg-red-50 dark:bg-red-900 rounded-md">
                <p className="text-sm font-semibold text-red-900 dark:text-red-100 mb-1">
                  Errors:
                </p>
                <ul className="text-xs text-red-800 dark:text-red-200 space-y-1">
                  {verification.errors.map((error, i) => (
                    <li key={i}>• {error}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Click "Verify Chain" to check integrity.
          </p>
        )}
      </section>

      {/* State Snapshot */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          State
        </h2>

        <div className="space-y-2 text-sm">
          <div>
            <span className="font-medium text-slate-700 dark:text-slate-300">
              Events:
            </span>
            <span className="ml-2 text-slate-600 dark:text-slate-400">
              {vault.events.length}
            </span>
          </div>

          <div>
            <span className="font-medium text-slate-700 dark:text-slate-300">
              State Hash:
            </span>
            <code className="block mt-1 font-mono text-xs bg-slate-100 dark:bg-slate-800 p-2 rounded break-all text-slate-700 dark:text-slate-300">
              {vault.state_hash || '(not computed)'}
            </code>
          </div>

          <div>
            <span className="font-medium text-slate-700 dark:text-slate-300">
              Merkle Root:
            </span>
            <code className="block mt-1 font-mono text-xs bg-slate-100 dark:bg-slate-800 p-2 rounded break-all text-slate-700 dark:text-slate-300">
              {vault.merkle_root || '(not computed)'}
            </code>
          </div>
        </div>
      </section>

      {/* Help */}
      <section className="text-xs text-slate-600 dark:text-slate-400">
        <details>
          <summary className="font-semibold cursor-pointer hover:text-slate-900 dark:hover:text-slate-200">
            💡 What is this?
          </summary>
          <div className="mt-2 space-y-1 text-slate-600 dark:text-slate-400">
            <p>
              <strong>Verification Report:</strong> Real-time cryptographic validation of
              your vault. Green ✓ = valid, red ✗ = tampered.
            </p>
            <p>
              <strong>State Hash:</strong> SHA-256 of all events. Changes if vault is modified.
            </p>
            <p>
              <strong>Merkle Root:</strong> Hash of vault's file tree. Proves integrity of
              all files.
            </p>
          </div>
        </details>
      </section>
    </div>
  );
}
