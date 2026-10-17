import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, Leaf, Mic, Square, Sprout, Volume2 } from "lucide-react";
import { workspaceRequest } from "@/lib/farmWorkspaceClient";
import { FarmSetupProfile, StarterPlan, needsFarmSetup, skipSetup } from "@/lib/farmSetup";
import { useLocalDraft } from "@/hooks/useLocalDraft";
import { useVoiceInput, voiceLanguageCode } from "@/hooks/useVoiceInput";
import { APP_LANGUAGES, applyLanguagePreference } from "@/lib/languagePreference";
import { SpeechPlayback } from "@/components/SpeechPlayback";
import { parseSpokenNumber } from "@/lib/voiceNumbers";
import "./onboarding.css";

type Form = {name:string;region:string;language:string;crops:string;area:string};
type Region = {id:string;name:string};
const steps=["A little hello","Your place","Your farm","Ready to grow"];
const prompts=["What should I call you? Choose the language you feel most at home with.","Which state or union territory is your farm in? This helps me find useful local information.","Tell me what you grow and how much land you farm. You can say it naturally, then check the details.","Let’s check your details and the starter routines. Nothing is saved until you choose to save it."];
const headings=["A little hello.\nA lot of possibility.","Your corner\nof the world.","Tell me about\nyour patch of earth.","A good beginning,\nmade for you."];
function FarmIllustration({stage}:{stage:number}) {return <svg viewBox="0 0 300 230" role="img" aria-label="An illustrated farm taking shape"><circle cx="239" cy="47" r="24" fill="#e6cb8c"/><path d="M0 157Q85 93 179 154T300 145V230H0Z" fill="#d4dec0"/><path d="M0 184Q100 130 205 184T300 166V230H0Z" fill="#a9bd8b"/>{[0,1,2,3,4].map(i=><path key={i} d={`M${-20+i*54} 230Q${35+i*42} 181 ${110+i*27} 170`} fill="none" stroke="#f1f1df" strokeWidth="2"/>)}<g className={stage>0?"farm-art-visible":"farm-art-ghost"}><path d="M94 152V104L139 74L181 104V158" fill="#f5f0de" stroke="#5c7452" strokeWidth="2"/><path d="M85 108L139 69L188 105" fill="none" stroke="#5c7452" strokeWidth="4" strokeLinecap="round"/><path d="M130 151V122H149V154M106 111H118V124H106Z" fill="#b1c69c" stroke="#5c7452" strokeWidth="2"/></g><g className={stage>1?"farm-art-visible":"farm-art-ghost"}><path d="M229 169V107M229 138Q207 133 206 114Q229 115 229 138M229 125Q253 120 254 101Q231 102 229 125" fill="#769564" stroke="#5c7452" strokeWidth="2"/><path d="M49 180V149M49 162Q30 157 34 141Q49 146 49 162M49 155Q63 144 72 149Q65 162 49 163" fill="#769564" stroke="#5c7452" strokeWidth="2"/></g></svg>;}

export default function Onboarding(){
  const navigate=useNavigate(),[params]=useSearchParams();
  const [draft,setDraft,clearDraft]=useLocalDraft("farm-setup");
  const [profile,setProfile]=useState<FarmSetupProfile|null>(null),[regions,setRegions]=useState<Region[]>([]),[plans,setPlans]=useState<StarterPlan[]>([]);
  const [form,setForm]=useState<Form>({name:"",region:"",language:"en",crops:"",area:""});
  const [step,setStep]=useState(0),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(""),[revision,setRevision]=useState(0),[consent,setConsent]=useState(false),[includePlans,setIncludePlans]=useState(true),[done,setDone]=useState(false);
  const [voiceNotice,setVoiceNotice]=useState(""),[extracting,setExtracting]=useState(false);
  const voice=useVoiceInput();
  const extraction=useRef<AbortController|null>(null);
  const title=useRef<HTMLHeadingElement>(null);
  useEffect(()=>()=>extraction.current?.abort(),[]);
  useEffect(()=>{
    let active=true;setLoading(true);setError("");
    void Promise.all([workspaceRequest<{profile:FarmSetupProfile}>("/api/profile","GET",undefined,{fresh:true}),workspaceRequest<{regions:Region[]}>("/api/onboarding/options"),workspaceRequest<{plans:StarterPlan[]}>("/api/onboarding/starter-plans")]).then(([p,o,r])=>{
      if(!active)return;
      if(!p.profile)throw new Error("Your saved profile is unavailable. Please retry.");
      setProfile(p.profile);setRegions(o.regions);setPlans(r.plans);
      const initial:Form={name:p.profile.name||"",region:p.profile.region_id||o.regions.find(r=>r.name===p.profile.state)?.id||"",language:p.profile.preferred_language?.split("-")[0]||"en",crops:(p.profile.crops||[]).join(", "),area:p.profile.land_size_acres?.toString()||""};
      let resume=0;
      try {const saved=JSON.parse(draft||"null");if(saved&&needsFarmSetup(p.profile)){for(const key of ["name","region","language","crops","area"] as const)if(typeof saved[key]==="string")initial[key]=saved[key];if(Number.isInteger(saved.step))resume=Math.max(0,Math.min(3,saved.step));}} catch {/* Use the database values if a local draft is damaged. */}
      setForm(initial);setStep(params.get("review")==="1"?3:resume);
      if(!needsFarmSetup(p.profile)&&params.get("review")!=="1"&&!draft)navigate("/workspace",{replace:true});
    }).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[revision]);
  useEffect(()=>{if(!loading&&profile&&!done)setDraft(JSON.stringify({...form,step}));},[form,step,loading,profile,done,setDraft]);
  function change(key:keyof Form,value:string){setForm(f=>({...f,[key]:value}));setConsent(false);}
  function move(next:number){voice.cancel();extraction.current?.abort();setExtracting(false);setError("");setVoiceNotice("");setStep(next);requestAnimationFrame(()=>title.current?.focus());}
  function leave(){voice.cancel();extraction.current?.abort();skipSetup();navigate("/workspace",{replace:true});}
  function valid(current:number){
    if(current===0&&form.name.trim().length<2)return "Tell Mitra your name, or type at least two characters.";
    if(current===1&&!regions.some(r=>r.id===form.region))return "Choose your state so Mitra can use the right region.";
    if(current===2&&(!form.crops.split(",").some(c=>c.trim())||!Number.isFinite(Number(form.area))||Number(form.area)<=0||Number(form.area)>100000))return "Add your crops and a land area greater than zero, in acres.";
    return "";
  }
  function next(){const message=valid(step);if(message){setError(message);return;}move(Math.min(3,step+1));}
  async function useWords(){
    const text=voice.draft.trim();if(!text)return;
    setError("");setVoiceNotice("");
    if(step===0){change("name",text.replace(/^(my name is|i am|i’m)\s+/i,"").slice(0,100));voice.cancel();setVoiceNotice("I’ve added your name. Check it before continuing.");return;}
    if(step===1){const candidate=regions.find(r=>text.toLowerCase().includes(r.name.toLowerCase()));if(candidate){change("region",candidate.id);voice.cancel();setVoiceNotice("Check the state I selected for you.");}else setError("I couldn’t match that to a state. Choose from the list, or try saying the state name.");return;}
    setExtracting(true);const controller=new AbortController();extraction.current=controller;
    try {
      const result=await workspaceRequest<{identified_fields:{crops?:string[]|string;land_size_acres?:number|string}}>("/api/profile/voice-update","POST",{transcript:text},{signal:controller.signal});
      if(controller.signal.aborted)return;
      const fields=result.identified_fields||{};let area="";
      if(fields.land_size_acres!=null)try{area=String(parseSpokenNumber(String(fields.land_size_acres),{unit:"acres",min:0.0001,max:100000}));}catch{/* Keep the existing number when extraction is ambiguous. */}
      const crops=Array.isArray(fields.crops)?fields.crops.filter(c=>typeof c==="string").join(", "):typeof fields.crops==="string"?fields.crops:"";
      if(!crops.trim()&&!area)throw new Error("I couldn’t pick out the crops or land size. Try saying ‘I grow groundnut on four acres’, or type below.");
      setForm(f=>({...f,...(crops.trim()?{crops:crops.slice(0,500)}:{}),...(area?{area}:{})}));setConsent(false);voice.cancel();setVoiceNotice("Your words are in the fields. Please check the crops, number and acres before continuing.");
    }catch(e){if(!controller.signal.aborted)setError((e as Error).message);}finally{if(!controller.signal.aborted)setExtracting(false);}
  }
  async function finish(){
    for(let index=0;index<3;index++){const message=valid(index);if(message){move(index);setError(message);return;}}
    if(!consent){setError("Please confirm that these details can be saved to your farm account.");return;}
    setBusy(true);setError("");voice.cancel();
    try {
      await workspaceRequest("/api/onboarding","POST",{display_name:form.name.trim(),region_id:form.region,preferred_language:form.language,consent_to_store_profile:true});
      await workspaceRequest("/api/profile/save","POST",{name:form.name.trim(),preferred_language:form.language,crops:form.crops.split(",").map(c=>c.trim()).filter(Boolean),land_size_acres:Number(form.area)});
      if(includePlans&&!plans.every(p=>p.saved))await workspaceRequest("/api/onboarding/starter-plans","POST",{approved:true});
      applyLanguagePreference(form.language);setDone(true);clearDraft();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  const recording=voice.phase==="recording",voiceBusy=voice.phase==="requesting"||voice.phase==="transcribing"||extracting;
  const stateName=regions.find(r=>r.id===form.region)?.name;
  if(loading)return <main className="mitra-onboarding onboarding-loading" role="status"><span className="onboarding-orb"><i/><i/></span><p>Mitra is getting your place ready…</p></main>;
  if(!profile)return <main className="mitra-onboarding onboarding-loading"><p role="alert">{error}</p><button onClick={()=>setRevision(r=>r+1)}>Try again</button><button onClick={leave}>Skip for now</button></main>;
  return <main className="mitra-onboarding">
    <header className="onboarding-top"><a href="/workspace" onClick={e=>{e.preventDefault();if(!busy)leave();}}><Leaf size={21}/>kisan mitra<span>MAKE YOURSELF AT HOME</span></a><nav aria-label="Setup progress">{steps.map((label,index)=><button key={label} aria-current={index===step?"step":undefined} disabled={busy||done||index>step} onClick={()=>move(index)}><span>{index<step||done?<Check size={13}/>:index+1}</span>{label}</button>)}</nav><button className="onboarding-skip" disabled={busy} onClick={leave}>{done?"Open workspace":"Skip for now"}<ArrowRight size={15}/></button></header>
    <div className="onboarding-layout">
      <aside className="onboarding-companion"><div className={`onboarding-orb ${recording?"is-listening":""}`} aria-hidden="true"><Sprout/><i/><i/><b/></div><span className="onboarding-eyebrow">YOUR LITTLE FARM COMPANION</span><h2>We can just <br/>talk this through.</h2><p>{done?"You’re all set. Your saved details will be there on your phone and laptop.":prompts[step]}</p><SpeechPlayback key={step} text={done?"Your farm is ready. Welcome to Kisan Mitra.":prompts[step]} language={form.language}/>
        {!done&&step<3&&<div className="onboarding-voice">
          {recording?<button className="onboarding-talk" onClick={voice.stop}><Square size={18}/>Finish speaking</button>:<button className="onboarding-talk" disabled={voiceBusy||busy} onClick={()=>void voice.start(voiceLanguageCode(form.language),true)}><Mic size={19}/>{voiceBusy?extracting?"Filling your details…":"Listening to your words…":"Talk to Mitra"}</button>}
          <small>{recording?`Listening · ${voice.seconds}s / 30s`:step===2?'Try “I grow groundnut on four acres.”':"Speak naturally. You can always type instead."}</small>
          <div className="onboarding-wave" aria-hidden="true">{Array.from({length:19},(_,i)=><i key={i} style={{height:recording?`${8+voice.level*(20-Math.abs(i-9))*3}px`:`${6+(i%4)*3}px`}}/>)}</div>
          <p className="onboarding-caption" aria-live="polite">{voice.interim|| (recording?"I’m listening…":"")}</p>
          {voice.phase==="review"&&<label className="onboarding-voice-review">Your words<textarea aria-label="Review spoken words" rows={3} value={voice.draft} onChange={e=>voice.setDraft(e.target.value)}/><button disabled={extracting} onClick={()=>void useWords()}>Use these words<Check size={15}/></button><button onClick={voice.cancel}>Discard recording</button></label>}
          {voice.error&&<p role="alert">{voice.error}</p>}
          {voiceNotice&&<p role="status">{voiceNotice}</p>}
          <small>Voice is sent for transcription when you finish. You review details before saving.</small>
        </div>}
        <div className="onboarding-note"><Check size={16}/><p>Already told us in the app?<br/><strong>Your saved details come with you.</strong></p></div>
      </aside>
      <section className="onboarding-main" aria-label="Farm setup">
        {done?<div className="onboarding-done"><span><Check size={32}/></span><p className="onboarding-eyebrow">YOUR FARM, CONNECTED</p><h1>You’re right<br/>where you belong.</h1><p>Your details{includePlans?" and reviewed starter routines are":" are"} saved. Let’s make something good grow.</p><button className="onboarding-primary" onClick={()=>navigate("/workspace",{replace:true})}>Meet your workspace<ArrowRight size={18}/></button></div>:<div className="onboarding-step" key={step}>
          <span className="onboarding-eyebrow">{String(step+1).padStart(2,"0")} / 04 · {steps[step]}</span><h1 ref={title} tabIndex={-1}>{headings[step]}</h1><p className="onboarding-intro">{step===0?"A few little details help Mitra feel a little more like yours.":step===1?"Local weather, nearby markets, and support that makes sense for you.":step===2?"Just the basics for now. Your fields and seasons can come later.":"A quick look together before we open your workspace."}</p>
          {error&&<p className="onboarding-error" role="alert">{error}</p>}
          {step===0&&<><label className="onboarding-field">What should Mitra call you?<input autoComplete="given-name" maxLength={100} value={form.name} onChange={e=>change("name",e.target.value)} placeholder="Your name"/></label><label className="onboarding-field">The language you feel at home in<select value={form.language} onChange={e=>change("language",e.target.value)}>{APP_LANGUAGES.map(([code,label])=><option key={code} value={code}>{label}</option>)}</select></label></>}
          {step===1&&<><label className="onboarding-field">Your state or union territory<select value={form.region} onChange={e=>change("region",e.target.value)}><option value="">Choose your state</option>{regions.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label><div className="onboarding-detail"><Leaf size={21}/><p>A starting point, not an exact field location. Add your farm’s location in the notebook when you’re ready.</p></div></>}
          {step===2&&<><label className="onboarding-field">What do you grow?<input aria-label="What do you grow?" maxLength={500} value={form.crops} onChange={e=>change("crops",e.target.value)} placeholder="Groundnut, maize…"/><small>Separate different crops with a comma.</small></label><label className="onboarding-field">How much land do you farm?<div className="onboarding-unit"><input aria-label="Land area in acres" type="number" min="0.0001" max="100000" step="any" value={form.area} onChange={e=>change("area",e.target.value)} placeholder="0"/><span>acres</span></div></label></>}
          {step===3&&<><div className="onboarding-summary"><div><span>YOUR FARMER PROFILE</span><h2>{form.name}</h2><p>{stateName} · {form.area} acres</p><p>{form.crops}</p></div><button aria-label="Edit profile details" onClick={()=>move(0)}>Edit<ArrowLeft size={14}/></button></div><div className="onboarding-routines"><span className="onboarding-eyebrow">A LITTLE HEAD START · BY MITRA</span>{plans.map(p=><details key={p.key}><summary><span><Sprout size={16}/>{p.title}</span>{p.saved?<Check size={16}/>:<span>+</span>}</summary><ul>{p.steps.map(s=><li key={s}>{s}</li>)}</ul></details>)}</div><label className="onboarding-check"><input type="checkbox" checked={includePlans} onChange={e=>setIncludePlans(e.target.checked)}/>Add these editable starter routines to my notebook.</label><p className="onboarding-small">Routines are drafts to make your own, not scheduled tasks. Plans already saved in the app will not be duplicated.</p><label className="onboarding-check"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>I’ve checked my details. Save them to my farm account.</label></>}
          <footer className="onboarding-actions">{step>0?<button disabled={busy} onClick={()=>move(step-1)}><ArrowLeft size={16}/>Back</button>:<span>About two minutes.<br/>At your pace.</span>}<button className="onboarding-primary" disabled={busy||voiceBusy||recording} onClick={()=>step===3?void finish():next()}>{busy?"Saving your farm…":step===3?"Make yourself at home":"Next step"}<ArrowRight size={17}/></button></footer>
          {step<3&&<div className="onboarding-up-next"><span>{String(step+2).padStart(2,"0")}</span><strong>{steps[step+1]}</strong><small>UP NEXT</small></div>}
        </div>}
      </section>
      <aside className="onboarding-preview"><span className="onboarding-eyebrow">A LITTLE SPACE, ALL YOURS</span><h2>{form.name?`${form.name.split(" ")[0]}’s farm` : "Your farm is taking shape."}</h2><FarmIllustration stage={done?3:step}/><div className="onboarding-progress" role="progressbar" aria-label="Setup progress" aria-valuenow={done?100:step*25} aria-valuemin={0} aria-valuemax={100}><i style={{width:`${done?100:step*25}%`}}/></div><p>{done?"Ready for a fresh beginning.":`${step*25}% · Little by little, we’re getting there.`}</p><div className="onboarding-preview-details"><span><Leaf size={15}/>{stateName||"Your place"}</span><span><Sprout size={15}/>{form.crops||"Your growing season"}</span></div><small>One account.<br/>Your phone. Your laptop. Your farm.</small></aside>
    </div><footer className="onboarding-bottom">A little company. A better farm day.<span>Saved details stay with your account. Unfinished edits stay in this browser.</span></footer>
  </main>;
}
