import { AlertTriangle, TrendingDown } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function ForecastChart({ forecast, loading }) {
  if (loading || !forecast) return <div className="glass rounded-2xl h-[420px] animate-pulse"/>;
  const chartData = forecast.dates.map((date, i) => ({ date, stock: forecast.predicted_stock[i] }));
  const crossing = chartData.find(x => x.stock <= forecast.reorder_threshold);
  return <section className="glass rounded-2xl p-5">
    <div className="flex items-start justify-between gap-3">
      <div><div className="flex items-center gap-2"><TrendingDown className="w-5 h-5 text-cyanx"/><h2 className="font-bold">Stockout Forecast</h2></div><p className="text-xs text-slate-500 mt-1">{forecast.drug} · ML service output</p></div>
      {crossing && <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amberx/10 text-amberx border border-amberx/20 text-[10px] font-semibold"><AlertTriangle className="w-3.5 h-3.5"/> Threshold {crossing.date}</div>}
    </div>
    <div className="h-[300px] mt-5">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{top:10,right:8,left:-18,bottom:0}}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,.10)"/>
          <XAxis dataKey="date" tick={{fill:"#64748b",fontSize:10}} axisLine={false} tickLine={false}/>
          <YAxis tick={{fill:"#64748b",fontSize:10}} axisLine={false} tickLine={false}/>
          <Tooltip contentStyle={{background:"#0d1b2a",border:"1px solid rgba(112,157,181,.2)",borderRadius:12,fontSize:12}} labelStyle={{color:"#94a3b8"}}/>
          <ReferenceLine y={forecast.reorder_threshold} stroke="#f6b84b" strokeDasharray="5 5" label={{value:"REORDER", fill:"#f6b84b", fontSize:9, position:"insideTopRight"}}/>
          <Line type="monotone" dataKey="stock" stroke="#42d9ff" strokeWidth={3} dot={{r:3,fill:"#42d9ff",strokeWidth:0}} activeDot={{r:5}}/>
        </LineChart>
      </ResponsiveContainer>
    </div>
    <div className="flex items-center justify-between text-[10px] text-slate-500"><span>Predicted on-hand units</span><span>Reorder threshold: {forecast.reorder_threshold.toLocaleString()}</span></div>
  </section>;
}
