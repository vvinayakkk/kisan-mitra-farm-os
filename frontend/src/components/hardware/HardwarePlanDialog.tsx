import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { workspaceRequest } from '@/lib/farmWorkspaceClient';
export function HardwarePlanDialog({open,onClose}:{open:boolean;onClose:()=>void}) {
  const [notes,setNotes]=useState(''); const [busy,setBusy]=useState(false); const [saved,setSaved]=useState(false); const [error,setError]=useState('');
  async function save() {
    setBusy(true); setError('');
    try {
      await workspaceRequest('/api/farm-workspace/service-requests','POST',{title:'Arrange an AgriSense farm station',service_type:'machinery',status:'planned',notes});
      setSaved(true);
    } catch(e) {setError(e instanceof Error?e.message:'Could not save your plan.');} finally {setBusy(false);}
  }
  return <Dialog.Root open={open} onOpenChange={value=>{if(!value&&!busy)onClose();}}><Dialog.Portal>
    <Dialog.Overlay style={{position:'fixed',inset:0,background:'#0008',zIndex:1000}}/>
    <Dialog.Content style={{position:'fixed',top:'50%',left:'50%',transform:'translate(-50%,-50%)',width:'min(90vw,500px)',padding:28,borderRadius:20,background:'#f7f8f2',color:'#193c26',zIndex:1001}}>
      <Dialog.Title>Plan your farm station</Dialog.Title>
      <Dialog.Description>Save this to your shared farm records. Confirm a supplier, price and any subsidy separately; this does not place an order or take payment.</Dialog.Description>
      {saved ? <p role="status">Your equipment plan is saved across app and web. <a href="/workspace?view=notebook">Open your farm notebook</a></p> : <><label>Requirements<textarea value={notes} maxLength={2000} onChange={e=>setNotes(e.target.value)} style={{display:'block',width:'100%',margin:'16px 0',border:'1px solid #829876',padding:12}}/></label><button disabled={busy} onClick={()=>void save()}>{busy?'Saving…':'Save equipment plan'}</button></>}
      {error&&<p role="alert">{error}</p>}<Dialog.Close disabled={busy} style={{marginLeft:20}}>Close</Dialog.Close>
    </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
