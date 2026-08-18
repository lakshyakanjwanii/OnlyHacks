import { Check, Fingerprint, Link2 } from "lucide-react";

export default function AuditTrail({ entries }) {
  return <div>
    <div className="mb-5 rounded-xl border border-tealx/15 bg-tealx/5 p-4 flex gap-3">
      <Fingerprint className="w-5 h-5 text-tealx shrink-0"/>
      <div><div className="text-sm font-semibold">Tamper-evident chain</div><p className="text-xs text-slate-400 mt-1">Each event commits to the previous hash. Any modified record breaks the visible chain.</p></div>
    </div>
    <div className="relative ml-2 sm:ml-4">
      <div className="absolute left-[15px] top-4 bottom-4 w-px bg-gradient-to-b from-tealx/50 via-cyanx/30 to-danger/30"/>
      <div className="space-y-5">
        {entries.map((e,i) => <div key={i} className="relative flex gap-4">
          <div className="relative z-10 mt-1 w-8 h-8 rounded-full bg-[#0d1b2a] border border-tealx/30 flex items-center justify-center"><Check className="w-3.5 h-3.5 text-tealx"/></div>
          <div className="flex-1 rounded-xl border border-white/5 bg-white/[.025] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-sm font-bold">{e.action}</span><span className="text-[10px] text-slate-500 font-mono">{new Date(e.timestamp).toLocaleString()}</span></div>
            <div className="text-xs text-slate-400 mt-1">{e.actor}</div>
            <div className="grid sm:grid-cols-2 gap-2 mt-3">
              <div className="rounded-lg bg-black/15 p-2"><div className="text-[9px] text-slate-600 uppercase tracking-wider">Hash</div><div className="font-mono text-[11px] text-cyanx mt-1 break-all">{e.hash}</div></div>
              <div className="rounded-lg bg-black/15 p-2"><div className="text-[9px] text-slate-600 uppercase tracking-wider flex items-center gap-1"><Link2 className="w-3 h-3"/> Previous</div><div className="font-mono text-[11px] text-slate-400 mt-1 break-all">{e.prev_hash}</div></div>
            </div>
          </div>
        </div>)}
      </div>
    </div>
  </div>;
}
