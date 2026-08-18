import { AlertTriangle, Check, Clock3, ExternalLink, FileSearch } from "lucide-react";

export default function AnomalyFeed({ anomalies, batches, onResolve, onAudit, loading }) {
  const batchName = id => batches.find(b => b.id === id)?.batch_number || id;
  if (loading) return <div className="glass rounded-2xl p-5 h-[420px] animate-pulse"/>;
  return <section className="glass rounded-2xl overflow-hidden">
    <div className="p-5 border-b border-white/5 flex items-center justify-between">
      <div><div className="flex items-center gap-2"><FileSearch className="w-5 h-5 text-danger"/><h2 className="font-bold">Anomaly & Validation Engine</h2></div><p className="text-xs text-slate-500 mt-1">Rule-triggered records from the validation pipeline</p></div>
      <span className="px-2.5 py-1 rounded-full bg-danger/10 text-danger border border-danger/20 text-[10px] uppercase tracking-wider">{anomalies.filter(a=>!a.resolved).length} open</span>
    </div>
    <div className="divide-y divide-white/5">
      {anomalies.map(a => <div key={a.id} className={`p-4 ${a.resolved ? "opacity-55" : ""}`}>
        <div className="flex gap-3">
          <div className={`mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${a.resolved ? "bg-tealx/10 text-tealx" : "bg-danger/10 text-danger"}`}>{a.resolved ? <Check className="w-4 h-4"/> : <AlertTriangle className="w-4 h-4"/>}</div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap gap-2 items-center"><span className="font-semibold text-sm">Batch #{batchName(a.batch_id)}</span><span className="text-[9px] px-2 py-0.5 rounded-full bg-white/5 text-slate-400 font-mono">{a.rule_triggered}</span></div>
            <p className="text-xs text-slate-400 mt-1 leading-5">
              {typeof a.details === "string"
                ? a.details
                : a.details?.conflict || a.details?.message || JSON.stringify(a.details)}
            </p>
            <div className="flex items-center gap-3 mt-3 text-[10px] text-slate-600"><Clock3 className="w-3 h-3"/>{new Date(a.created_at).toLocaleString()}</div>
          </div>
          <div className="flex flex-col sm:flex-row items-end gap-2">
            <button onClick={() => onAudit(a.batch_id)} className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300" title="View audit chain"><ExternalLink className="w-3.5 h-3.5"/></button>
            {!a.resolved && <button onClick={() => onResolve(a.id)} className="text-[10px] font-semibold px-2.5 py-2 rounded-lg bg-danger/10 text-danger hover:bg-danger/20">Acknowledge</button>}
          </div>
        </div>
      </div>)}
    </div>
  </section>;
}
