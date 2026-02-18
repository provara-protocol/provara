import { usePlaygroundStore } from '../store/playground';

export default function Header() {
  const exportVaultJson = usePlaygroundStore((s) => s.actions.exportVaultJson);
  const vault = usePlaygroundStore((s) => s.vault);

  const handleExport = () => {
    const json = exportVaultJson();
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `provara-vault-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <header className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-6 py-4 flex-shrink-0">
      <div className="flex items-center justify-between max-w-full">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-provara-600 rounded-lg flex items-center justify-center text-white font-bold text-lg select-none">
            P
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900 dark:text-white leading-tight">
              Provara Playground
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Ed25519 · SHA-256 · RFC 8785 · All crypto in-browser
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <a
            href="https://provara.dev"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 text-sm font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md transition"
          >
            Docs
          </a>
          <button
            onClick={handleExport}
            disabled={vault.events.length === 0}
            className="px-4 py-1.5 text-sm font-medium bg-provara-600 text-white rounded-md hover:bg-provara-700 disabled:opacity-40 transition"
          >
            Export JSON
          </button>
        </div>
      </div>
    </header>
  );
}
