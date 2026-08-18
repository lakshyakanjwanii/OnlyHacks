import { useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, ArrowRight, Bell, Boxes, Check, ChevronRight,
  CircleHelp, ClipboardList, Factory, FileSearch, FlaskConical, Hospital,
  LogOut, MapPin, Moon, RefreshCw, ShieldCheck, Sun, Truck, UserRound, Users, X
} from "lucide-react";
import { loadDashboardData, getForecast, acknowledgeAnomaly, getMockAuditTrail, setAuthToken } from "./api";
import { supabase } from "./supabaseClient";
import LoginPage from "./components/LoginPage";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import KpiGrid from "./components/KpiGrid";
import AnomalyFeed from "./components/AnomalyFeed";
import ForecastChart from "./components/ForecastChart";
import ShipmentMap from "./components/ShipmentMap";
import AuditTrail from "./components/AuditTrail";

const ROLES = ["State", "District", "Hospital / Pharmacist", "Vendor"];

const roleMeta = {
  State: { title: "State Control Tower", subtitle: "Maharashtra · network-wide visibility", icon: ShieldCheck },
  District: { title: "District Operations", subtitle: "Distribution health · node performance", icon: Boxes },
  "Hospital / Pharmacist": { title: "Hospital Pharmacy", subtitle: "Patient-facing inventory · FEFO readiness", icon: Hospital },
  Vendor: { title: "Vendor Console", subtitle: "Purchase orders · dispatch compliance", icon: Truck }
};

function App() {
  const [role, setRole] = useState("State");
  const [dark, setDark] = useState(true);
  const [data, setData] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [audit, setAudit] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(new Date());
  // Auth state — null = no session (anon mode), object = logged-in session
  // Start as null so the dashboard renders immediately; Supabase auth
  // upgrades it in the background if a valid session exists.
  const [session, setSession] = useState(null);

  const refresh = async () => {
    try {
      setLoading(true);
      setError("");
      const next = await loadDashboardData();
      setData(next);
      const drugId = next.drugs[1]?.id || next.drugs[0]?.id;
      if (drugId) setForecast(await getForecast(drugId));
      setLastUpdated(new Date());
    } catch (e) {
      setError(e.message || "Unable to load control-tower data.");
    } finally {
      setLoading(false);
    }
  };

  // ── Auth bootstrap ────────────────────────────────────────────────────────
  // Runs ONCE on mount. Restores any stored token, then resolves the live
  // Supabase session. The dashboard data load (below) is DECOUPLED from this
  // — token updates happen silently in the background.
  useEffect(() => {
    // Restore token from localStorage immediately (avoids a flash of anon state)
    const stored = localStorage.getItem("sb_access_token");
    if (stored) setAuthToken(stored);

    // Check for a live Supabase session
    supabase.auth.getSession().then(({ data: { session: s } }) => {
      if (s) {
        setSession(s);
        setAuthToken(s.access_token);
        localStorage.setItem("sb_access_token", s.access_token);
      }
      // If no session, leave session=null — dashboard stays in anon mode
    });

    // Keep token in sync if the user signs in/out in another tab, or token
    // is refreshed. Does NOT re-fetch dashboard data — call refresh() manually
    // after sign-in if you want role-scoped data.
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, s) => {
        setSession(s);
        if (s) {
          setAuthToken(s.access_token);
          localStorage.setItem("sb_access_token", s.access_token);
        } else if (event === "SIGNED_OUT") {
          // Only clear token on an explicit sign-out, not on INITIAL_SESSION null
          setAuthToken("");
          localStorage.removeItem("sb_access_token");
        }
      }
    );
    return () => subscription.unsubscribe();
  }, []);

  // ── Data load ─────────────────────────────────────────────────────────────
  // Runs ONCE on mount. Uses whatever auth token is set at call time.
  // The manual refresh() button re-fetches with the current token.
  useEffect(() => {
    refresh();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  const handleSignOut = async () => {
    await supabase.auth.signOut();
    setAuthToken("");
    localStorage.removeItem("sb_access_token");
  };

  const openAudit = async (batchId) => {
    setSelectedBatch(batchId);
    setAudit(await getMockAuditTrail(batchId));
  };

  const resolve = async (id) => {
    await acknowledgeAnomaly(id);
    setData(prev => ({
      ...prev,
      anomalies: prev.anomalies.map(a => a.id === id ? { ...a, resolved: true } : a)
    }));
  };

  const kpis = useMemo(() => {
    if (!data) return [];
    const open = data.anomalies.filter(a => !a.resolved).length;
    const expiring = data.batches.filter(b => {
      const days = (new Date(b.expiry_date) - new Date()) / 86400000;
      return days <= 60;
    }).length;
    const transit = data.purchase_orders.filter(p => p.status.toLowerCase().includes("transit")).length;
    return [
      { label: "Stockout risks", value: "03", trend: "+1 today", tone: "danger", icon: AlertTriangle },
      { label: "Open anomalies", value: String(open).padStart(2,"0"), trend: "2 critical", tone: "danger", icon: FileSearch },
      { label: "Batches in transit", value: String(transit).padStart(2,"0"), trend: "live scans", tone: "cyan", icon: Truck },
      { label: "Expiring ≤60 days", value: String(expiring).padStart(2,"0"), trend: "FEFO priority", tone: "amber", icon: FlaskConical }
    ];
  }, [data]);

  return (
    <div className={dark ? "dark min-h-screen" : "min-h-screen"} style={{background: dark ? "#07111f" : "#f2f7f9", color: dark ? "#e8f1f7" : "#12212d"}}>
      <div className="min-h-screen grid-bg">
        <Sidebar role={role} setRole={setRole} roles={ROLES} />
        <main className="lg:ml-[250px] min-h-screen">
          <Topbar role={role} roles={ROLES} setRole={setRole} dark={dark} setDark={setDark} onRefresh={refresh} lastUpdated={lastUpdated} />
          <div className="p-4 sm:p-6 lg:p-7 max-w-[1800px] mx-auto">
            <section className="mb-6 flex flex-col xl:flex-row xl:items-end justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-xs uppercase tracking-[.2em] text-cyanx font-semibold">
                  <span className="h-2 w-2 rounded-full bg-tealx animate-pulse" /> SYSTEM ONLINE
                  <span className="text-slate-500 tracking-normal normal-case">/ API v1</span>
                </div>
                <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight mt-2">{roleMeta[role].title}</h1>
                <p className="text-sm text-slate-400 mt-1">{roleMeta[role].subtitle}</p>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-400">
                <Activity className="w-4 h-4 text-tealx" />
                Auto-refresh ready · Last sync {lastUpdated.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}
                {session ? (
                  <button
                    id="sign-out-btn"
                    onClick={handleSignOut}
                    title={`Signed in as ${session.user?.email}`}
                    className="ml-2 flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-white/10 transition-colors"
                    style={{ color: "#64748b" }}
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span className="hidden sm:inline">Sign out</span>
                  </button>
                ) : (
                  <span
                    className="ml-2 px-2 py-0.5 rounded-full text-xs"
                    style={{ background: "rgba(0,180,216,0.1)", color: "#00b4d8", border: "1px solid rgba(0,180,216,0.2)" }}
                  >
                    anon · read-only
                  </span>
                )}
              </div>
            </section>

            {error && (
              <div className="glass rounded-2xl p-4 mb-5 border border-danger/30 flex items-center justify-between">
                <div className="flex items-center gap-3"><AlertTriangle className="text-danger" /><span>{error}</span></div>
                <button onClick={refresh} className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10"><RefreshCw className="w-4 h-4"/></button>
              </div>
            )}

            <KpiGrid items={kpis} loading={loading} />

            <div className="grid grid-cols-1 xl:grid-cols-[1.1fr_.9fr] gap-5 mt-5">
              <AnomalyFeed
                anomalies={data?.anomalies || []}
                batches={data?.batches || []}
                onResolve={resolve}
                onAudit={openAudit}
                loading={loading}
              />
              <ForecastChart forecast={forecast} loading={loading} />
            </div>

            <div className="mt-5">
              <ShipmentMap events={data?.scan_events || []} batches={data?.batches || []} />
            </div>

            <div className="mt-5 glass rounded-2xl p-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <div>
                  <div className="flex items-center gap-2"><ClipboardList className="w-5 h-5 text-cyanx"/><h2 className="font-bold">Operational Snapshot</h2></div>
                  <p className="text-xs text-slate-500 mt-1">Role-aware actions are surfaced here for demo readiness.</p>
                </div>
                <span className="text-xs px-3 py-1.5 rounded-full bg-tealx/10 text-tealx border border-tealx/20">{role}</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {[
                  ["Route integrity", "98.4%", "All active routes within expected corridor", ShieldCheck],
                  ["Scan compliance", "94.8%", "Latest node scans received on schedule", Activity],
                  ["FEFO readiness", "91.2%", "Expiry-first allocation coverage", FlaskConical]
                ].map(([label,value,desc,Icon]) => (
                  <div key={label} className="rounded-xl border border-white/5 bg-white/[.025] p-4">
                    <div className="flex justify-between items-center"><span className="text-xs text-slate-400">{label}</span><Icon className="w-4 h-4 text-tealx"/></div>
                    <div className="text-2xl font-bold mt-2">{value}</div>
                    <p className="text-xs text-slate-500 mt-1">{desc}</p>
                  </div>
                ))}
              </div>
            </div>

            <footer className="py-8 text-xs text-slate-600 flex flex-wrap gap-x-5 gap-y-2">
              <span>SIH PSS04 · Drug Supply Chain Control Tower</span>
              <span>GS1-ready scan workflow</span>
              <span>JWT-secured API contract</span>
            </footer>
          </div>
        </main>
      </div>

      {selectedBatch && (
        <div className="fixed inset-0 z-[1000] bg-black/70 backdrop-blur-sm p-4 sm:p-8 flex items-center justify-center">
          <div className="w-full max-w-4xl max-h-[90vh] overflow-auto glass rounded-2xl p-5 sm:p-7">
            <div className="flex items-center justify-between mb-5">
              <div><p className="text-xs uppercase tracking-widest text-cyanx">Cryptographic audit</p><h2 className="text-xl font-bold mt-1">Batch {selectedBatch}</h2></div>
              <button onClick={() => setSelectedBatch(null)} className="p-2 rounded-lg hover:bg-white/10"><X/></button>
            </div>
            <AuditTrail entries={audit} />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
