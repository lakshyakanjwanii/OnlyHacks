import { ArrowUpRight, LoaderCircle } from "lucide-react";

export default function KpiGrid({ items, loading }) {
  if (loading) return <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">{[1,2,3,4].map(i => <div key={i} className="h-32 rounded-2xl bg-white/[.035] border border-white/5 animate-pulse"/>)}</div>;
  const tones = {
    danger: "text-danger bg-danger/10 border-danger/20",
    cyan: "text-cyanx bg-cyanx/10 border-cyanx/20",
    amber: "text-amberx bg-amberx/10 border-amberx/20"
  };
  return <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
    {items.map(({label,value,trend,tone,icon:Icon}) => <div key={label} className="glass rounded-2xl p-4 sm:p-5 scanline">
      <div className="flex justify-between gap-3"><span className="text-xs sm:text-sm text-slate-400">{label}</span><span className={`w-8 h-8 rounded-lg border flex items-center justify-center ${tones[tone]}`}><Icon className="w-4 h-4"/></span></div>
      <div className="mt-3 flex items-end gap-2"><span className="text-2xl sm:text-3xl font-extrabold">{value}</span><span className="text-[10px] text-slate-500 mb-1">{trend}</span></div>
    </div>)}
  </div>;
}
