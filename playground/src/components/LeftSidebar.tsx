import React from 'react';
import { usePlaygroundStore } from '../store/playground';

export default function LeftSidebar() {
  const keys = usePlaygroundStore((state) => state.keys);
  const current_key_id = usePlaygroundStore((state) => state.current_key_id);
  const setCurrentKey = usePlaygroundStore((state) => state.actions.setCurrentKey);

  return (
    <div className="p-6 space-y-6">
      {/* Key Manager */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          Keys
        </h2>

        {keys.length === 0 ? (
          <button className="w-full px-4 py-2 bg-provara-600 text-white rounded-md hover:bg-provara-700 transition font-medium">
            Generate New Key
          </button>
        ) : (
          <div className="space-y-2">
            {keys.map((key) => (
              <button
                key={key.key_id}
                onClick={() => setCurrentKey(key.key_id)}
                className={`w-full text-left px-3 py-2 rounded-md transition ${
                  current_key_id === key.key_id
                    ? 'bg-provara-100 dark:bg-provara-900 border-l-2 border-provara-600'
                    : 'hover:bg-slate-100 dark:hover:bg-slate-800'
                }`}
              >
                <div className="font-mono text-sm text-slate-700 dark:text-slate-300">
                  {key.key_id}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Actions */}
      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
          Actions
        </h2>

        <div className="space-y-2">
          <button className="w-full px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white rounded-md hover:bg-slate-200 dark:hover:bg-slate-700 transition">
            New Event
          </button>
          <button className="w-full px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white rounded-md hover:bg-slate-200 dark:hover:bg-slate-700 transition">
            Import Vault
          </button>
          <button className="w-full px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white rounded-md hover:bg-slate-200 dark:hover:bg-slate-700 transition">
            Verify Chain
          </button>
        </div>
      </section>

      {/* Info */}
      <section className="text-sm text-slate-600 dark:text-slate-400">
        <p>
          🔐 All cryptography runs locally in your browser. No servers involved.
        </p>
      </section>
    </div>
  );
}
