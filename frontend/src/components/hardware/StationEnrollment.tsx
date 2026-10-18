import { useEffect, useState } from 'react';
import { workspaceRequest } from '@/lib/farmWorkspaceClient';
type Plot={id:string;name?:string;plot_key:string};
export function StationEnrollment() {
  const [plots,setPlots]=useState<Plot[]>([]),[plot,setPlot]=useState(''),[label,setLabel]=useState(''),[physical,setPhysical]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [result,setResult]=useState<{station_id:string;device_key:string;note:string}|null>(null);
  useEffect(()=>{const c=new AbortController();void workspaceRequest<{plots:Plot[]}>('/api/plots','GET',undefined,{signal:c.signal}).then(d=>setPlots(d.plots||[])).catch(e=>{if(!c.signal.aborted)setError(e.message);});return()=>c.abort();},[]);
  async function enroll() {setBusy(true);setError('');try {setResult(await workspaceRequest('/api/stations/enroll','POST',{plot_id:plot,device_label:label,physical_device:true}));}catch(e){setError(e instanceof Error?e.message:'Could not enroll device.');}finally{setBusy(false);}}
  return <section style={{marginTop:24,padding:24,border:'1px solid #829876',borderRadius:20}}>
    <h2>Register your physical station</h2><p>Associate your device with a saved plot. Readings appear after the device sends authenticated sensor packets.</p>
    {result ? <div><p role="status">Station registered: {result.station_id}</p><label>Device key — shown once<input readOnly value={result.device_key} style={{width:'100%'}}/></label><p>Keep this key private and configure it on your device. Send packets to /api/sensors/ingest with Authorization: Device &lt;device key&gt;.</p><p>{result.note}</p></div> : <>
      {!plots.length?<a href="/workspace?view=notebook">Add your farm and plot in the notebook first</a>:<label>Farm plot<select value={plot} onChange={e=>setPlot(e.target.value)}><option value="">Choose a plot</option>{plots.map(p=><option key={p.id} value={p.id}>{p.name||p.plot_key}</option>)}</select></label>}
      <label style={{display:'block',margin:'12px 0'}}>Device label <input value={label} maxLength={120} onChange={e=>setLabel(e.target.value)} placeholder="North field station"/></label>
      <label><input type="checkbox" checked={physical} onChange={e=>setPhysical(e.target.checked)}/> I have a physical device to configure.</label><br/>
      <button disabled={busy||!physical||!plot||label.trim().length<2} onClick={()=>void enroll()}>{busy?'Registering…':'Register station'}</button>
    </>}{error&&<p role="alert">{error}</p>}
  </section>;
}
