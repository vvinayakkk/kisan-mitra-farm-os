import { useState } from 'react';
import { Search, SlidersHorizontal, X } from 'lucide-react';
import './collection-filters.css';
export type FilterState = {query:string; status:string; from:string; to:string};
export function matchesCollection(text:string, status:string, date:string, filters:FilterState) {
  const query = filters.query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return query.every(word => text.toLocaleLowerCase().includes(word)) && (!filters.status || status === filters.status) &&
    (!filters.from || (!!date && date.slice(0,10) >= filters.from)) && (!filters.to || (!!date && date.slice(0,10) <= filters.to));
}
export function useCollectionFilters<T>(rows:T[], text:(row:T)=>string, status?:(row:T)=>string, date?:(row:T)=>string) {
  const [filters,setFilters] = useState<FilterState>({query:'',status:'',from:'',to:''});
  const items = rows.filter(row => matchesCollection(text(row),status?.(row)||'',date?.(row)||'',filters));
  return {items,filters,setFilters,total:rows.length,statuses:status ? [...new Set(rows.map(status).filter(Boolean))].sort() : [],dates:!!date};
}
export function CollectionFilters<T>({control,label}:{control:ReturnType<typeof useCollectionFilters<T>>;label:string}) {
  const {filters,setFilters,total,items,statuses,dates}=control;
  const change=(key:keyof FilterState,value:string)=>setFilters(previous=>({...previous,[key]:value}));
  const active=Object.values(filters).some(Boolean);
  return <div className="collection-filters" aria-label={`${label} filters`}>
    <SlidersHorizontal size={14}/><label className="collection-search"><Search size={14}/><input aria-label={`Search ${label}`} placeholder={`Search ${label.toLowerCase()}…`} value={filters.query} onChange={e=>change('query',e.target.value)}/></label>
    {statuses.length>0 && <select aria-label={`${label} status or type`} value={filters.status} onChange={e=>change('status',e.target.value)}><option value="">All types / states</option>{statuses.map(status=><option key={status} value={status}>{status.replace(/_/g,' ')}</option>)}</select>}
    {dates && <><label>From<input type="date" aria-label={`${label} from date`} value={filters.from} onChange={e=>change('from',e.target.value)}/></label><label>To<input type="date" aria-label={`${label} to date`} value={filters.to} min={filters.from||undefined} onChange={e=>change('to',e.target.value)}/></label></>}
    <span className="collection-count" aria-live="polite">{items.length} of {total}</span>
    {active && <button type="button" onClick={()=>setFilters({query:'',status:'',from:'',to:''})}><X size={12}/> Clear filters</button>}
  </div>;
}
