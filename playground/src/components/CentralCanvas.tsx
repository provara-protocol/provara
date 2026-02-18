import { usePlaygroundStore } from '../store/playground';
import type { ProvaraEvent } from '../lib/provara-crypto';

function EventCard({
  event,
  index,
  isSelected,
  onSelect,
}: {
  event: ProvaraEvent;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`p-4 border rounded-lg cursor-pointer transition-shadow ${
        isSelected
          ? 'border-provara-500 shadow-md bg-provara-50 dark:bg-slate-800'
          : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:shadow-md'
      }`}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-slate-400 dark:text-slate-500 font-mono">
          #{index + 1} · {event.event_id.slice(0, 14)}…
        </span>
        <span
          className={`px-2 py-0.5 rounded text-xs font-semibold ${
            event.type === 'OBSERVATION'
              ? 'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200'
              : event.type === 'ATTESTATION'
              ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
              : 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200'
          }`}
        >
          {event.type}
        </span>
      </div>

      {/* Metadata */}
      <div className="text-sm space-y-1">
        <p className="text-slate-600 dark:text-slate-300">
          <span className="font-medium">Actor:</span>{' '}
          <code className="font-mono text-xs">{event.actor}</code>
        </p>
        {event.timestamp_utc && (
          <p className="text-slate-600 dark:text-slate-300">
            <span className="font-medium">Time:</span>{' '}
            {new Date(event.timestamp_utc).toLocaleTimeString()}
          </p>
        )}
        {event.prev_event_hash && (
          <p className="text-slate-500 dark:text-slate-400 text-xs font-mono">
            ← {event.prev_event_hash.slice(0, 14)}…
          </p>
        )}
      </div>

      {/* Expanded JSON */}
      {isSelected && (
        <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
          <details open>
            <summary className="text-xs font-medium cursor-pointer text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 mb-1">
              Full JSON
            </summary>
            <pre className="text-xs font-mono bg-slate-100 dark:bg-slate-900 p-3 rounded overflow-x-auto text-slate-700 dark:text-slate-300">
              {JSON.stringify(event, null, 2)}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}

export default function CentralCanvas() {
  const vault = usePlaygroundStore((s) => s.vault);
  const view_mode = usePlaygroundStore((s) => s.ui.view_mode);
  const selected_event_id = usePlaygroundStore((s) => s.ui.selected_event_id);
  const setViewMode = usePlaygroundStore((s) => s.actions.setViewMode);
  const setSelectedEvent = usePlaygroundStore((s) => s.actions.setSelectedEvent);
  const initVault = usePlaygroundStore((s) => s.actions.initVault);
  const loading = usePlaygroundStore((s) => s.ui.loading);
  const keypair = usePlaygroundStore((s) => s.keypair);

  return (
    <div className="h-full flex flex-col">
      {/* Tab bar */}
      <div className="border-b border-slate-200 dark:border-slate-700 flex gap-1 px-6 py-3">
        {(['list', 'graph', 'merkle'] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className={`px-4 py-1.5 text-sm font-medium rounded transition ${
              view_mode === mode
                ? 'bg-provara-100 dark:bg-provara-900 text-provara-700 dark:text-provara-300'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
            }`}
          >
            {mode === 'list' && '📋 Events'}
            {mode === 'graph' && '🔗 Chain'}
            {mode === 'merkle' && '🌳 Tree'}
          </button>
        ))}

        <div className="flex-1" />
        <span className="text-xs text-slate-400 dark:text-slate-500 self-center">
          {vault.events.length} event{vault.events.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {vault.events.length === 0 ? (
          /* Empty state */
          <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-sm">
              <div className="text-5xl mb-4">📦</div>
              <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                No Events Yet
              </h3>
              <p className="text-slate-500 dark:text-slate-400 mb-6 text-sm">
                Click <strong>Create Vault</strong> to generate an Ed25519 keypair
                and append your first signed event.
              </p>
              {!keypair && (
                <button
                  onClick={initVault}
                  disabled={loading}
                  className="px-5 py-2 bg-provara-600 text-white rounded-md hover:bg-provara-700 disabled:opacity-50 transition font-medium"
                >
                  {loading ? 'Generating…' : 'Create Vault'}
                </button>
              )}
            </div>
          </div>
        ) : view_mode === 'list' ? (
          /* Event list */
          <div className="space-y-3 max-w-2xl mx-auto">
            {vault.events.map((event, idx) => (
              <EventCard
                key={event.event_id}
                event={event}
                index={idx}
                isSelected={selected_event_id === event.event_id}
                onSelect={() =>
                  setSelectedEvent(
                    selected_event_id === event.event_id ? null : event.event_id,
                  )
                }
              />
            ))}
          </div>
        ) : view_mode === 'graph' ? (
          /* Simple chain graph */
          <div className="max-w-2xl mx-auto">
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
              Causal chain — each event references its predecessor via{' '}
              <code className="font-mono text-xs">prev_event_hash</code>.
            </p>
            <div className="space-y-0">
              {vault.events.map((event, idx) => (
                <div key={event.event_id} className="flex items-start gap-3">
                  <div className="flex flex-col items-center">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0 ${
                        event.type === 'OBSERVATION'
                          ? 'bg-blue-500'
                          : event.type === 'ATTESTATION'
                          ? 'bg-green-500'
                          : 'bg-red-500'
                      }`}
                    >
                      {idx + 1}
                    </div>
                    {idx < vault.events.length - 1 && (
                      <div className="w-0.5 h-8 bg-slate-300 dark:bg-slate-600" />
                    )}
                  </div>
                  <div className="pb-6">
                    <p className="font-medium text-sm text-slate-800 dark:text-slate-200">
                      {event.type}
                    </p>
                    <p className="font-mono text-xs text-slate-500 dark:text-slate-400">
                      {event.event_id}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      {event.timestamp_utc
                        ? new Date(event.timestamp_utc).toLocaleTimeString()
                        : ''}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          /* Merkle placeholder */
          <div className="flex items-center justify-center h-full text-slate-400 dark:text-slate-600">
            <div className="text-center">
              <div className="text-4xl mb-3">🌳</div>
              <p className="text-sm">Merkle tree visualization coming soon.</p>
              <p className="text-xs mt-1">Use the Verify button to check integrity.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
