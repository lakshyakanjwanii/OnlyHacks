import { useMemo } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import L from "leaflet";
import { MapPin } from "lucide-react";

const icon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25,41], iconAnchor: [12,41], popupAnchor: [1,-34]
});

// Node locations — used when the DB has a plain-text location string
// (real API returns location as text; mock data returned {lat,lng,label})
const NODE_COORDS = {
  "CIPLA-FACTORY-MUM":        { lat: 19.076,  lng: 72.8777, label: "Mumbai Factory" },
  "MH-STATE-WAREHOUSE-01":   { lat: 18.5204, lng: 73.8567, label: "Pune Warehouse" },
  "DISTRICT-HOSPITAL-NASHIK":{ lat: 20.0059, lng: 73.7796, label: "Nashik Hospital" },
  "SUNPHARMA-DIST-PUNE":     { lat: 18.5204, lng: 73.8567, label: "Pune Vendor Hub" },
  "AIIMS-DELHI-PHARMACY":    { lat: 28.5672, lng: 77.2100, label: "AIIMS Delhi" },
};

// Accepts either {lat,lng,label} object OR a plain text string OR node_id fallback
function parseLocation(event) {
  const loc = event.location;
  if (loc && typeof loc === "object" && loc.lat != null) return loc;
  // Try to look up by node_id
  if (event.node_id && NODE_COORDS[event.node_id]) return NODE_COORDS[event.node_id];
  // Default to Mumbai if unknown
  return { lat: 19.076, lng: 72.8777, label: typeof loc === "string" ? loc : event.node_id || "Unknown" };
}

export default function ShipmentMap({ events, batches }) {
  const validEvents = useMemo(() => events.map(e => ({ ...e, _loc: parseLocation(e) })), [events]);
  const center = useMemo(() => {
    const first = validEvents[0];
    return first ? [first._loc.lat, first._loc.lng] : [19.076, 72.8777];
  }, [validEvents]);

  return <section className="glass rounded-2xl overflow-hidden">
    <div className="p-5 flex items-center justify-between">
      <div><div className="flex items-center gap-2"><MapPin className="w-5 h-5 text-tealx"/><h2 className="font-bold">Shipment & Logistics Network</h2></div><p className="text-xs text-slate-500 mt-1">Live scan locations · map layer is ready for production coordinates</p></div>
      <span className="text-[10px] text-slate-500">{events.length} nodes reporting</span>
    </div>
    <div className="h-[360px]">
      <MapContainer center={center} zoom={6} scrollWheelZoom={false} style={{height:"100%",width:"100%"}}>
        <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/>
        {validEvents.map(event => {
          const batch = batches.find(b => b.id === event.batch_id);
          return <Marker key={event.id} position={[event._loc.lat, event._loc.lng]} icon={icon}>
            <Popup><div><strong>{event.node_type}</strong><br/>{event._loc.label}<br/><span style={{opacity:.7}}>Batch {batch?.batch_number || event.batch_id}</span></div></Popup>
          </Marker>;
        })}
      </MapContainer>
    </div>
  </section>;
}
