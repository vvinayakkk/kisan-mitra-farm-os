import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Search, RotateCw, X, ArrowUpRight } from 'lucide-react';
import { apiFetch } from '@/lib/apiClient';
import { MitraHelper } from './MitraHelper';
import './farmer-map.css';

export type MapFarmer = {
  id: string; name: string; location: string; state: string; reference: boolean;
  latitude: number | null; longitude: number | null;
  crops: string[]; excess_resources: string[]; required_resources: string[];
  exchange_listings: { id: string; kind: string }[];
};
export function normalizeMapFarmers(records: unknown[]): MapFarmer[] {
  const coordinate = (value: unknown, limit: number) => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value)) && Math.abs(Number(value)) <= limit ? Number(value) : null;
  const strings = (value: unknown) => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
  return records.filter((row): row is Record<string, unknown> => !!row && typeof row === 'object').map(row => ({
    reference: row.origin === 'synthetic' || row.data_origin === 'synthetic', id: String(row.id), name: String(row.name || 'Farmer'), location: String(row.location || row.district || ''), state: String(row.state || ''),
    latitude: coordinate(row.latitude, 90), longitude: coordinate(row.longitude, 180),
    crops: strings(row.crops), excess_resources: strings(row.excess_resources), required_resources: strings(row.required_resources),
    exchange_listings: Array.isArray(row.exchange_listings) ? row.exchange_listings : [],
  }));
}
export function filterMapFarmers(farmers: MapFarmer[], query: string) {
  const words = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  return farmers.filter(farmer => words.every(word => [farmer.name, farmer.location, farmer.state, ...farmer.crops, ...farmer.excess_resources, ...farmer.required_resources].join(' ').toLowerCase().includes(word)));
}
let leafletPromise: Promise<any> | undefined;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (!leafletPromise) leafletPromise = new Promise((resolve, reject) => {
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'; document.head.append(css);
    const script = document.createElement('script'); script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.onload = () => resolve(window.L);
    script.onerror = () => { script.remove(); leafletPromise = undefined; reject(new Error('The map could not be opened. You can still browse the farmer list.')); };
    document.head.append(script);
  });
  return leafletPromise;
}

export default function WorkspaceFarmerMap() {
  const [farmers, setFarmers] = useState<MapFarmer[]>([]);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<MapFarmer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<any>(null);
  const markers = useRef<any>(null);
  const filtered = useMemo(() => filterMapFarmers(farmers, query), [farmers, query]);
  const located = useMemo(() => filtered.filter(f => f.latitude !== null && f.longitude !== null), [filtered]);
  async function refresh() {
    setLoading(true); setError('');
    try {
      const response = await apiFetch(`${import.meta.env.VITE_API_URL || ''}/api/marketplace/farmers`);
      if (!response.ok) throw new Error('The farmer directory could not be refreshed. Please try again.');
      const data = await response.json();
      if (!Array.isArray(data.farmers)) throw new Error('The farmer directory is temporarily unavailable.');
      setFarmers(normalizeMapFarmers(data.farmers));
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Unable to open the directory.'); }
    finally { setLoading(false); }
  }
  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    let disposed = false; let observer: ResizeObserver | undefined;
    loadLeaflet().then(L => {
      if (disposed || !container.current) return;
      map.current = L.map(container.current, { zoomControl: false }).setView([22.97, 78.65], 5);
      L.control.zoom({position: 'bottomright'}).addTo(map.current);
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom: 19 }).addTo(map.current);
      markers.current = L.layerGroup().addTo(map.current);
      observer = new ResizeObserver(() => map.current?.invalidateSize()); observer.observe(container.current);
      setReady(true);
    }).catch(failure => { if (!disposed) setError(failure.message); });
    return () => { disposed = true; observer?.disconnect(); map.current?.remove(); map.current = null; markers.current = null; };
  }, []);
  function choose(farmer: MapFarmer) {
    setSelected(farmer);
    if (farmer.latitude !== null && farmer.longitude !== null) map.current?.flyTo([farmer.latitude, farmer.longitude], 10, {duration: 0.6});
  }
  useEffect(() => {
    if (!ready || !map.current || !markers.current) return;
    markers.current.clearLayers();
    located.forEach(farmer => {
      const icon = window.L.divIcon({ className: 'mitra-farmer-marker', html: '<span></span>', iconSize: [22,22], iconAnchor: [11,11] });
      const marker = window.L.marker([farmer.latitude, farmer.longitude], {icon, title: farmer.name, alt: `View ${farmer.name}`, keyboard: true});
      const label = document.createElement('span'); label.textContent = farmer.name;
      marker.bindTooltip(label).on('click', () => choose(farmer)).addTo(markers.current);
    });
    if (located.length) map.current.fitBounds(located.map(f => [f.latitude, f.longitude]), {padding: [36,36], maxZoom: 10});
  }, [located, ready]);
  const listing = selected?.exchange_listings.find(item => item.kind === 'offer');
  const profile = selected ? <article className="farmer-network-profile"><button className="farmer-network-close" aria-label="Close farmer details" onClick={() => setSelected(null)}><X size={18}/></button><span className="farmer-network-eyebrow">YOUR FARMING NETWORK</span><h2>{selected.name}</h2><p><MapPin size={14}/> {[...new Set([selected.location, selected.state].filter(Boolean))].join(', ') || 'Location not shared'}</p><div className="farmer-network-facts">{[['Grows',selected.crops],['Can share',selected.excess_resources],['Looking for',selected.required_resources]].map(([label, values]) => <div key={String(label)}><h3>{String(label)}</h3><p>{(values as string[]).join(' · ') || 'Not listed yet'}</p></div>)}</div><Link className="farmer-network-connect" to={`/workspace?view=exchange&from=map${listing ? `&listing=${encodeURIComponent(listing.id)}` : ''}`}>Explore exchange listings <ArrowUpRight size={15}/></Link></article> : null;
  return <section className="farmer-network">
    <header className="farmer-network-heading"><div><span className="farmer-network-eyebrow">GROW BETTER, TOGETHER</span><h1>Your farming neighbourhood</h1><p>Find farmers, discover shared resources, and plan the next step with Mitra.</p></div><button className="farmer-network-refresh" onClick={refresh} disabled={loading} aria-label="Refresh farmer map"><RotateCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh</button></header>
    <div className="farmer-network-layout"><div className="farmer-network-main">
      <label className="farmer-network-search"><Search size={17}/><input aria-label="Search farmers and resources" placeholder="Filter map by resource or state..." value={query} onChange={event => {setQuery(event.target.value); setSelected(null);}}/><span>{filtered.length} farmers</span></label>
      {error && <p role="alert" className="farmer-network-error">{error} <button onClick={refresh}>Retry</button></p>}
      <div className="farmer-network-canvas"><div ref={container} className="farmer-network-map" aria-label="Farmer locations"/><div className="farmer-network-legend"><i/> {located.length} locations <span>· {located.some(f => f.reference) ? "Reference data" : "Approximate areas"}</span></div></div>
      {!selected && <div className="farmer-network-hint"><MapPin size={16}/><p>Select a green dot or a farmer below to see crops and resources.</p></div>}
      <div className="farmer-network-list" aria-label="Farmers in the map search">{filtered.slice(0,60).map(farmer => <button key={farmer.id} onClick={() => choose(farmer)} aria-pressed={selected?.id === farmer.id}><span className="farmer-network-avatar">{farmer.name.slice(0,1)}</span><span><strong>{farmer.name}</strong><small>{farmer.location || farmer.state || 'Location not shared'} · {farmer.excess_resources[0] || farmer.crops[0] || 'View profile'}</small></span><ArrowUpRight size={15}/></button>)}</div>
      {!loading && !filtered.length && <p className="farmer-network-hint">No shared farmers match this search. Try a crop, resource or state.</p>}
    </div><aside className="farmer-network-assistant">{profile}<MitraHelper context="map"/><p className="farmer-network-note">Mitra can help find resources and plan a handover. Contact details are shared only through available exchange listings.</p></aside></div>
  </section>;
}
