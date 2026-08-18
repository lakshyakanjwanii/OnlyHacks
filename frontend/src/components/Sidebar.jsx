import { Boxes, Factory, FlaskConical, Hospital, LayoutDashboard, ShieldCheck, Truck, Users } from "lucide-react";

export default function Sidebar({ role, setRole, roles }) {
  const icons = { State: ShieldCheck, District: Boxes, "Hospital / Pharmacist": Hospital, Vendor: Truck };
  return (
    <aside className="hidden lg:flex fixed left-0 top-0 bottom-0 w-[250px] z-50 flex-col border-r border-white/5 bg-[#07111f]/95 backdrop-blur-xl">
      <div className="p-6 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-tealx/10 border border-tealx/20 flex items-center justify-center">
            <FlaskConical className="w-5 h-5 text-tealx"/>
          </div>
          <div><div className="font-extrabold tracking-tight">PHARMA<span className="text-tealx">.TOWER</span></div><div className="text-[10px] text-slate-500 tracking-[.2em]">CONTROL SYSTEM</div></div>
        </div>
      </div>
      <div className="p-4">
        <div className="text-[10px] uppercase tracking-[.2em] text-slate-600 px-2 mb-2">Workspace</div>
        <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-white/[.05] text-white text-sm"><LayoutDashboard className="w-4 h-4 text-cyanx"/> Control Tower</button>
      </div>
      <div className="px-4">
        <div className="text-[10px] uppercase tracking-[.2em] text-slate-600 px-2 mb-2">Role views</div>
        <div className="space-y-1">
          {roles.map(r => {
            const Icon = icons[r];
            const active = r === role;
            return <button key={r} onClick={() => setRole(r)} className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition ${active ? "bg-tealx/10 text-tealx border border-tealx/15" : "text-slate-400 hover:text-white hover:bg-white/[.04]"}`}>
              <Icon className="w-4 h-4"/><span className="truncate">{r}</span>
            </button>
          })}
        </div>
      </div>
      <div className="mt-auto p-4">
        <div className="rounded-xl border border-white/5 bg-white/[.025] p-3">
          <div className="flex items-center gap-2 text-xs font-semibold"><Users className="w-4 h-4 text-tealx"/> Demo session</div>
          <div className="text-[11px] text-slate-500 mt-1">Authenticated · JWT active</div>
        </div>
      </div>
    </aside>
  );
}
