import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Mic, Square, Check, RotateCcw, Loader2, X } from 'lucide-react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Dialog, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { useVoiceInput, VOICE_LANGUAGES, VOICE_LIMIT_SECONDS, voiceLanguageCode } from '@/hooks/useVoiceInput';
import './VoiceInput.css';

interface VoiceInputProps {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  label?: string;
  language?: string;
  className?: string;
  presentation?: 'dialog' | 'side';
  panelContainer?: HTMLElement | null;
  onOpen?: () => void;
}


export function VoiceInput({ onTranscript, disabled, label = 'Speak your words', language, className = '', presentation = 'dialog', panelContainer, onOpen }: VoiceInputProps) {
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [selectedLanguage, setLanguage] = useState(voiceLanguageCode(language));
  const [live, setLive] = useState(false);
  const voice = useVoiceInput();
  const recording = voice.phase === 'recording';
  const busy = voice.phase === 'requesting' || voice.phase === 'transcribing';
  const liveSupported = typeof window !== 'undefined' && Boolean((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  function changeOpen(next: boolean) { if (next) setLanguage(voiceLanguageCode(language)); if (!next) voice.cancel(); setOpen(next); if (!next && presentation === 'side') requestAnimationFrame(() => trigger.current?.focus()); }
  useEffect(() => { if (disabled && open) changeOpen(false); }, [disabled, open]);
  const Title = presentation === 'side' ? 'h2' : DialogTitle;
  const Description = presentation === 'side' ? 'p' : DialogDescription;
  const content = <>
        <div className="voice-input-heading"><span className="voice-input-mark"><Mic size={19} /></span><div><Title>Say it your way</Title><Description>Speak, check your words, then add them.</Description></div></div>
        <div className="voice-input-settings">
          <label>Language<select aria-label="Voice language" value={selectedLanguage} disabled={recording || busy} onChange={event => setLanguage(event.target.value)}>{VOICE_LANGUAGES.map(([code, name]) => <option key={code} value={code}>{name}</option>)}</select></label>
          {liveSupported && <label className="voice-input-caption-switch"><input type="checkbox" checked={live} disabled={recording || busy} onChange={event => setLive(event.target.checked)} />Live captions</label>}
        </div>
        <div className="voice-input-stage" aria-live="polite">
          <div className="voice-input-meter" aria-hidden="true">{Array.from({ length: 25 }, (_, i) => <i key={i} style={{ height: `${6 + (recording ? voice.level * (30 - Math.abs(12 - i)) * 2 : 0)}px` }} />)}</div>
          <strong>{recording ? 'Listening to you' : voice.phase === 'transcribing' ? 'Turning your speech into words' : voice.phase === 'requesting' ? 'Opening your microphone' : voice.phase === 'review' ? 'Your words, ready to check' : voice.phase === 'error' ? 'Let’s try that again' : 'A little easier than typing'}</strong>
          <span>{recording ? `${String(voice.seconds).padStart(2, '0')} / ${VOICE_LIMIT_SECONDS}s · stop whenever you’re ready` : voice.phase === 'review' ? voice.source : `Up to ${VOICE_LIMIT_SECONDS} seconds · words are reviewed before they’re used`}</span>
          {voice.interim && <p className="voice-input-interim">{voice.interim}</p>}
        </div>
        {voice.error && <p role="alert" className="voice-input-error">{voice.error}</p>}
        {voice.phase === 'review' && <label className="voice-input-review">Check names, numbers and units<textarea aria-label="Review spoken words" value={voice.draft} onChange={event => voice.setDraft(event.target.value)} rows={4} maxLength={6000} autoFocus /></label>}
        <div className="voice-input-actions">
          <button type="button" className="voice-input-secondary" onClick={() => changeOpen(false)}>Cancel</button>
          {recording ? <button type="button" className="voice-input-primary" onClick={voice.stop}><Square size={15} />Finish recording</button> : busy ? <button type="button" className="voice-input-primary" disabled><Loader2 className="voice-input-spin" size={16} />{voice.phase === 'transcribing' ? 'Transcribing' : 'Opening mic'}</button> : voice.phase === 'review' ? <><button type="button" className="voice-input-secondary" onClick={() => void voice.start(selectedLanguage, live)} aria-label="Record again"><RotateCcw size={16} /></button><button type="button" className="voice-input-primary" disabled={!voice.draft.trim()} onClick={() => { onTranscript(voice.draft.trim()); changeOpen(false); }}><Check size={16} />Use these words</button></> : <button type="button" className="voice-input-primary" onClick={() => void voice.start(selectedLanguage, live)}><Mic size={16} />Start speaking</button>}
        </div>
        <p className="voice-input-note">{presentation === 'side' ? 'Recording is sent for transcription when you finish. Review your words before adding.' : 'Your recording is sent for transcription when you finish. Cancelling discards this input; an already transmitted recording may have reached the provider. Type anytime instead.'}</p>
  </>;
  const sidePanel = <aside className="voice-input-side" aria-label="Voice input" onKeyDown={event => { if (event.key === "Escape") { event.stopPropagation(); changeOpen(false); } }}>
    <button type="button" className="voice-input-close" aria-label="Close voice input" onClick={() => changeOpen(false)}><X size={16} /></button>
    {content}
  </aside>;
  return <>
    <button ref={trigger} type="button" aria-expanded={open} className={`voice-input-trigger ${className}`} aria-label={label} title={label} disabled={disabled} onClick={() => { setLanguage(voiceLanguageCode(language)); setOpen(true); onOpen?.(); }}><Mic size={18} /></button>
    {presentation === "side" ? (open && (panelContainer ? createPortal(sidePanel, panelContainer) : sidePanel)) : <Dialog open={open} onOpenChange={changeOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="voice-input-overlay" />
        <DialogPrimitive.Content className="voice-input-dialog">
        <DialogPrimitive.Close className="voice-input-close" aria-label="Close voice input"><X size={16} /></DialogPrimitive.Close>
        {content}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </Dialog>}
  </>;
}
