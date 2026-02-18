import { usePlaygroundStore } from './store/playground';
import Header from './components/Header';
import LeftSidebar from './components/LeftSidebar';
import CentralCanvas from './components/CentralCanvas';
import RightSidebar from './components/RightSidebar';

export default function App() {
  const ui = usePlaygroundStore((state) => state.ui);
  const toggleSidebar = usePlaygroundStore((state) => state.actions.toggleSidebar);

  return (
    <div className="min-h-screen bg-white dark:bg-slate-900 flex flex-col">
      <Header />

      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar */}
        {ui.sidebar_open && (
          <aside className="w-72 border-r border-slate-200 dark:border-slate-700 overflow-y-auto">
            <LeftSidebar />
          </aside>
        )}

        {/* Main Canvas */}
        <main className="flex-1 overflow-hidden">
          <CentralCanvas />
        </main>

        {/* Right Sidebar */}
        <aside className="w-80 border-l border-slate-200 dark:border-slate-700 overflow-y-auto hidden lg:block">
          <RightSidebar />
        </aside>
      </div>

      {/* Mobile toggle */}
      <button
        onClick={toggleSidebar}
        className="fixed bottom-4 right-4 lg:hidden p-2 bg-provara-600 text-white rounded-full shadow-lg"
      >
        ☰
      </button>
    </div>
  );
}
