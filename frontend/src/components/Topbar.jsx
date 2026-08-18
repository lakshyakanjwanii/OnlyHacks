import { Bell, ChevronDown, Moon, RefreshCw, Sun } from "lucide-react";

export default function Topbar({ role, roles, setRole, dark, setDark, onRefresh, lastUpdated }) {
  return (
    <header className="sticky top-0 z-40 h-[72px] border-b border-white/5 bg-[#07111f]/85 backdrop-blur-xl">
      <div className="h-full px-4 sm:px-6 lg:px-7 flex items-center justify-between gap-4">
        <div className="lg:hidden font-extrabold">PHARMA<span className="text-tealx">.TOWER</span></div>
        <div className="hidden sm:flex items-center gap-2 text-xs text-slate-500">
          <span className="w-2 h-2 rounded-full bg-tealx"/> Secure operations channel
        </div>
        <div className="ml-auto flex items-center gap-2">
          <label className="hidden md:flex items-center gap-2 glass rounded-xl px-3 py-2">
            <span className="text-[10px] uppercase tracking-widest text-slate-500">View</span>
            <select value={role} onChange={e => setRole(e.target.value)} className="bg-transparent text-sm outline-none">
              {roles.map(r => <option key={r} value={r} className="bg-[#0d1b2a]">{r}</option>)}
            </select>
          </label>
          <button title="Refresh" onClick={onRefresh} className="p-2.5 rounded-xl glass hover:bg-white/10"><RefreshCw className="w-4 h-4"/></button>
          <button title="Alerts" className="relative p-2.5 rounded-xl glass hover:bg-white/10"><Bell className="w-4 h-4"/><span className="absolute top-2 right-2 w-1.5 h-1.5 bg-danger rounded-full"/></button>
          <button title="Toggle theme" onClick={() => setDark(!dark)} className="p-2.5 rounded-xl glass hover:bg-white/10">{dark ? <Sun className="w-4 h-4"/> : <Moon className="w-4 h-4"/>}</button>
        </div>
      </div>
    </header>
  );
}
