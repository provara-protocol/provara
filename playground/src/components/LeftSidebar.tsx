import { useState } from 'react';
import { usePlaygroundStore } from '../store/playground';

const EVENT_TYPES = ['OBSERVATION', 'ATTESTATION', 'RETRACTION'] as const;

export default function LeftSidebar() {
  const keypair = usePlaygroundStore((s) => s.keypair);
  const loading = usePlaygroundStore((s) => s.ui.loading);
  const error = usePlaygroundStore((s) => s.ui.error);
  const { initVault, appendEvent, resetVault, clearError } = usePlaygroundStore(
    (s) => s.actions,
  );

  const [eventType, setEventType] = useState<string>('OBSERVATION');
  const [payloadText, setPayloadText] = useState<string>(
    '{"subject":"door","predicate":"state","value":"open"}',
  );
  const [payloadError, setPayloadError] = useState<string | null>(null);

  const handleAddEvent = async () => {
    setPayloadError(null);
    let payload: unknown;
    try {
      payload = JSON.parse(payloadText);
    } catch {
      setPayloadError('Invalid JSON payload');
      return;
    }
    await appendEvent(eventType, payload);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Error banner */}
      {error && (
        <div className="p-3 bg-red-50 dark:bg-red-900 border border-red-200 dark:border-red-700 rounded-md text-sm text-red-800 dark:text-red-200 flex justify-between items-start">
          <span>{error}</span>
          <button
            onClick={clearError}
            className="ml-2 text-red-500 hover:text-red-700 font-bold leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* Vault / keypair section */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">
          Vault
        </h2>

        {!keypair ? (
          <button
            onClick={initVault}
            disabled={loading}
            className="w-full px-4 py-2 bg-provara-600 text-white rounded-md hover:bg-provara-700 disabled:opacity-50 transition font-medium"
          >
            {loading ? 'Generating…' : 'Create Vault'}
          </button>
        ) : (
          <div className="space-y-2 text-sm">
            <p className="text-slate-600 dark:text-slate-400 font-medium">
              Active key:
            </p>
            <code className="block font-mono text-xs bg-slate-100 dark:bg-slate-800 p-2 rounded break-all text-slate-700 dark:text-slate-300">
              {keypair.key_id}
            </code>
            <details className="text-xs">
              <summary className="cursor-pointer text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200">
                Show public key
              </summary>
              <code className="block mt-1 font-mono bg-slate-100 dark:bg-slate-800 p-2 rounded break-all text-slate-600 dark:text-slate-300">
                {keypair.public_key_b64}
              </code>
            </details>
            <button
              onClick={resetVault}
              className="w-full px-3 py-1.5 text-sm bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-md hover:bg-slate-300 dark:hover:bg-slate-600 transition"
            >
              Reset Vault
            </button>
          </div>
        )}
      </section>

      {/* Add Event form */}
      {keypair && (
        <section>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-3">
            Add Event
          </h2>

          <div className="space-y-3">
            {/* Event type selector */}
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Type
              </label>
              <select
                value={eventType}
                onChange={(e) => setEventType(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-md bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-provara-500"
              >
                {EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </div>

            {/* Payload textarea */}
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                Payload (JSON)
              </label>
              <textarea
                value={payloadText}
                onChange={(e) => {
                  setPayloadText(e.target.value);
                  setPayloadError(null);
                }}
                rows={4}
                className="w-full px-3 py-2 text-xs font-mono border border-slate-300 dark:border-slate-600 rounded-md bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-provara-500"
                placeholder='{"subject":"...","predicate":"...","value":"..."}'
              />
              {payloadError && (
                <p className="text-xs text-red-600 mt-1">{payloadError}</p>
              )}
            </div>

            <button
              onClick={handleAddEvent}
              disabled={loading}
              className="w-full px-4 py-2 bg-provara-600 text-white rounded-md hover:bg-provara-700 disabled:opacity-50 transition font-medium text-sm"
            >
              {loading ? 'Signing…' : 'Sign & Append'}
            </button>
          </div>
        </section>
      )}

      {/* Info */}
      <section className="text-xs text-slate-500 dark:text-slate-400">
        <p>🔐 All cryptography runs locally in your browser via WebCrypto. No server involved.</p>
      </section>
    </div>
  );
}
