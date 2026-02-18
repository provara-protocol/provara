import React from 'react';

export default function Header() {
  return (
    <header className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-6 py-4">
      <div className="flex items-center justify-between max-w-full">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-provara-600 rounded-lg flex items-center justify-center text-white font-bold">
            P
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
              Provara Playground
            </h1>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Interactive Cryptographic Event Vault
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button className="px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md transition">
            Help
          </button>
          <button className="px-4 py-2 text-sm font-medium bg-provara-600 text-white rounded-md hover:bg-provara-700 transition">
            Export
          </button>
        </div>
      </div>
    </header>
  );
}
