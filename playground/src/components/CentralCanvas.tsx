import React from 'react';
import { usePlaygroundStore } from '../store/playground';

export default function CentralCanvas() {
  const vault = usePlaygroundStore((state) => state.vault);
  const view_mode = usePlaygroundStore((state) => state.ui.view_mode);
  const setViewMode = usePlaygroundStore((state) => state.actions.setViewMode);
  const selected_event_id = usePlaygroundStore((state) => state.ui.selected_event_id);
  const setSelectedEvent = usePlaygroundStore((state) => state.actions.setSelectedEvent);

  return (
    <div className="h-full flex flex-col">
      {/* View Mode Tabs */}
      <div className="border-b border-slate-200 dark:border-slate-700 flex gap-4 px-6 py-4">
        {(['list', 'graph', 'merkle'] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className={`px-4 py-2 font-medium transition ${
              view_mode === mode
                ? 'text-provara-600 border-b-2 border-provara-600'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
          >
            {mode === 'list' && '📋 List'}
            {mode === 'graph' && '🔗 Chain'}
            {mode === 'merkle' && '🌳 Tree'}
          </button>
        ))}
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-6">
        {vault.events.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-6xl mb-4">📦</div>
              <h3 className="text-xl font-semibold text-slate-900 dark:text-white mb-2">
                No Events Yet
              </h3>
              <p className="text-slate-600 dark:text-slate-400 mb-4">
                Create a key and append your first event to get started.
              </p>
              <button className="px-4 py-2 bg-provara-600 text-white rounded-md hover:bg-provara-700 transition">
                New Event
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {vault.events.map((event) => (
              <div
                key={event.event_id}
                onClick={() =>
                  setSelectedEvent(
                    selected_event_id === event.event_id ? null : event.event_id
                  )
                }
                className="chain-node cursor-pointer"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
                    {event.event_id.slice(0, 12)}…
                  </span>
                  <span className="px-2 py-1 bg-provara-100 dark:bg-provara-900 text-provara-900 dark:text-provara-100 text-xs font-semibold rounded">
                    {event.event_type}
                  </span>
                </div>

                <div className="space-y-1 text-sm">
                  <p className="text-slate-700 dark:text-slate-300">
                    <span className="font-medium">Actor:</span> {event.actor}
                  </p>
                  <p className="text-slate-700 dark:text-slate-300">
                    <span className="font-medium">Time:</span> {event.timestamp}
                  </p>
                  {event.content && (
                    <p className="text-slate-600 dark:text-slate-400">
                      <span className="font-medium">Content:</span>{' '}
                      {event.content.length > 50
                        ? event.content.slice(0, 50) + '…'
                        : event.content}
                    </p>
                  )}
                </div>

                {selected_event_id === event.event_id && (
                  <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
                    <details className="text-xs">
                      <summary className="font-mono cursor-pointer text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white">
                        Show JSON
                      </summary>
                      <pre className="json-editor mt-2 text-xs overflow-x-auto">
                        {JSON.stringify(event, null, 2)}
                      </pre>
                    </details>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
