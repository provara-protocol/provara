import { usePlaygroundStore } from '../store/playground';

export default function RightSidebar() {
  const verification = usePlaygroundStore((s) => s.verification);
  const vault = usePlaygroundStore((s) => s.vault);
  const loading = usePlaygroundStore((s) => s.ui.loading);
  const verifyVault = usePlaygroundStore((s) => s.actions.verifyVault);

  return (
    <div className="p-6 space-y-6">
      {/* Verification Report */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">
          Verification
        </h2>

        <button
          onClick={verifyVault}
          disabled={loading || vault.events.length === 0}
          className="w-full px-4 py-2 mb-4 bg-provara-600 text-white rounded-md hover:bg-provara-700 disabled:opacity-50 transition font-medium text-sm"
        >
          {loading ? 'Verifying…' : 'Verify Chain'}
        </button>

        {verification ? (
          <div className="space-y-2">
            {/* Overall badge */}
            <div
              className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-semibold ${
                verification.valid
                  ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
                  : 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200'
              }`}
            >
              <span>{verification.valid ? '✓' : '✗'}</span>
              <span>{verification.valid ? 'Chain Valid' : 'Chain Invalid'}</span>
            </div>

            {/* Error list */}
            {verification.errors.length > 0 && (
              <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/40 border border-red-200 dark:border-red-700 rounded-md">
                <p className="text-xs font-semibold text-red-900 dark:text-red-100 mb-1">
                  Errors:
                </p>
                <ul className="text-xs text-red-800 dark:text-red-200 space-y-1 font-mono">
                  {verification.errors.map((error, i) => (
                    <li key={i}>• {error}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Success detail */}
            {verification.valid && (
              <div className="text-xs text-slate-500 dark:text-slate-400 space-y-0.5 pt-1">
                <p>✓ Causal chain integrity verified</p>
                <p>✓ All Ed25519 signatures valid</p>
                <p>✓ {vault.events.length} event{vault.events.length !== 1 ? 's' : ''} checked</p>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {vault.events.length === 0
              ? 'Add events to enable verification.'
              : 'Click "Verify Chain" to check integrity.'}
          </p>
        )}
      </section>

      {/* State Snapshot */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">
          State
        </h2>

        <div className="space-y-2 text-sm">
          <div className="flex justify-between items-center">
            <span className="font-medium text-slate-700 dark:text-slate-300">Events:</span>
            <span className="text-slate-600 dark:text-slate-400 font-mono text-xs">
              {vault.events.length}
            </span>
          </div>

          {vault.events.length > 0 && (
            <div>
              <span className="font-medium text-slate-700 dark:text-slate-300 text-xs">
                Last event:
              </span>
              <code className="block mt-1 font-mono text-xs bg-slate-100 dark:bg-slate-800 p-2 rounded break-all text-slate-700 dark:text-slate-300">
                {vault.events[vault.events.length - 1].event_id}
              </code>
            </div>
          )}
        </div>
      </section>

      {/* Help */}
      <section className="text-xs text-slate-600 dark:text-slate-400">
        <details>
          <summary className="font-semibold cursor-pointer hover:text-slate-900 dark:hover:text-slate-200">
            What is this?
          </summary>
          <div className="mt-2 space-y-2 text-slate-600 dark:text-slate-400">
            <p>
              <strong>Verification:</strong> Checks every Ed25519 signature and the
              causal chain linkage (<code className="font-mono">prev_event_hash</code>)
              in your browser using WebCrypto — no server involved.
            </p>
            <p>
              <strong>Tamper test:</strong> Paste the JSON into a text editor, modify
              any field, paste it back — verify should fail.
            </p>
          </div>
        </details>
      </section>
    </div>
  );
}
