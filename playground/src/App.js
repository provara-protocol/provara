import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { usePlaygroundStore } from './store/playground';
import Header from './components/Header';
import LeftSidebar from './components/LeftSidebar';
import CentralCanvas from './components/CentralCanvas';
import RightSidebar from './components/RightSidebar';
export default function App() {
    const ui = usePlaygroundStore((state) => state.ui);
    const toggleSidebar = usePlaygroundStore((state) => state.actions.toggleSidebar);
    return (_jsxs("div", { className: "min-h-screen bg-white dark:bg-slate-900 flex flex-col", children: [_jsx(Header, {}), _jsxs("div", { className: "flex flex-1 overflow-hidden", children: [ui.sidebar_open && (_jsx("aside", { className: "w-72 border-r border-slate-200 dark:border-slate-700 overflow-y-auto", children: _jsx(LeftSidebar, {}) })), _jsx("main", { className: "flex-1 overflow-hidden", children: _jsx(CentralCanvas, {}) }), _jsx("aside", { className: "w-80 border-l border-slate-200 dark:border-slate-700 overflow-y-auto hidden lg:block", children: _jsx(RightSidebar, {}) })] }), _jsx("button", { onClick: toggleSidebar, className: "fixed bottom-4 right-4 lg:hidden p-2 bg-provara-600 text-white rounded-full shadow-lg", children: "\u2630" })] }));
}
//# sourceMappingURL=App.js.map