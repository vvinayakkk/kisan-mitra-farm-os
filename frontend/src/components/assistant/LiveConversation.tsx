import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { AudioLines, Mic, MicOff, Square, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { apiFetch } from '@/lib/apiClient';
import { useVoiceInput, voiceLanguageCode } from '@/hooks/useVoiceInput';
import type { ChatMessage } from '@/lib/assistantClient';
import './live-conversation.css';
import { SpeechAudio, unlockSpeechAudio } from '@/lib/speechAudio';
import { voiceStatus } from '@/lib/voiceStatus';


export function LiveConversation({ visible = true, startRequest = 0, container, disabled, running, pending, latest, onSend, onInterrupt, onActive }: {
  visible?: boolean; startRequest?: number; container: HTMLElement | null; disabled: boolean; running: boolean; pending: boolean;
  latest?: ChatMessage; onSend: (text: string) => Promise<void> | void;
  onInterrupt: () => void; onActive: (active: boolean) => void;
}) {
  const voice = useVoiceInput();
  const apiBase = import.meta.env.VITE_API_URL || "";
  const [active, setActive] = useState(false);
  const [muted, setMuted] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [sending, setSending] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [error, setError] = useState('');
  const generation = useRef(0);
  const lastSpoken = useRef('');
  const submittedDraft = useRef('');
  const ownsRun = useRef(false);
  const playback = useRef(new SpeechAudio());
  const failedAnswer = useRef('');
  const [retry, setRetry] = useState(0);
  const request = useRef<AbortController | null>(null);
  const options = useRef({ onSend, onActive }); options.current = { onSend, onActive };
  const voiceRef = useRef(voice); voiceRef.current = voice;
  function stopAudio() {
    request.current?.abort(); request.current = null;
    playback.current.stop();
  }
  function end() {
    generation.current++; stopAudio(); voice.cancel(); if (ownsRun.current && running) onInterrupt(); ownsRun.current = false;
    setActive(false); setConnecting(false); setSending(false); setSpeaking(false); setPreparing(false); setError('');
    options.current.onActive(false);
  }
  useEffect(() => () => {
    generation.current++; stopAudio(); voiceRef.current.cancel(); options.current.onActive(false);
  }, []);
  async function begin() {
    if (connecting || active) return;
    const token = ++generation.current;
    setConnecting(true); setError('');
    const abort = new AbortController(); request.current = abort;
    const timeout = setTimeout(() => abort.abort(), 12000);
    try {
      await unlockSpeechAudio();
      if (token !== generation.current) return;
      const result = await apiFetch(`${apiBase}/api/speech/capabilities`, { signal: abort.signal });
      if (!result.ok) throw new Error('Voice could not connect. Please retry.');
      const capabilities = await result.json();
      if (!capabilities.conversation_available || !capabilities.playback_languages?.includes(voiceLanguageCode()))
        throw new Error('Live voice is unavailable for this language. You can still type or use voice input.');
      if (token !== generation.current) return;
      lastSpoken.current = latest?.id || '';
      setMuted(false); setActive(true); options.current.onActive(true);
    } catch (failure) {
      if (token === generation.current) setError(failure instanceof Error ? failure.message : 'Voice could not connect.');
    } finally { clearTimeout(timeout); if (token === generation.current) setConnecting(false); }
  }
  const endRef = useRef(end); endRef.current = end;
  useEffect(() => { if (!visible) endRef.current(); }, [visible]);
  const beginRef = useRef(begin); beginRef.current = begin;
  useEffect(() => { if (startRequest > 0 && !disabled) void beginRef.current(); }, [startRequest]);
  useEffect(() => {
    if (!active || muted || running || pending || speaking || preparing || sending || error) return;
    if (latest?.id && latest.id !== lastSpoken.current && latest.text && latest.status !== 'working') return;
    if (voice.phase === 'idle') {
      const timer = setTimeout(() => void voice.start(voiceLanguageCode(), false, true), 200);
      return () => clearTimeout(timer);
    }
  }, [active, muted, running, pending, speaking, preparing, sending, error, latest, voice.phase, voice.start]);
  useEffect(() => {
    if (voice.phase === 'recording') submittedDraft.current = '';
    if (!active || voice.phase !== 'review' || sending || submittedDraft.current === voice.draft) return;
    submittedDraft.current = voice.draft;
    const text = voice.draft.trim(); const token = generation.current;
    voice.cancel(); if (!text) return;
    setSending(true); ownsRun.current = true;
    void Promise.resolve(options.current.onSend(text)).catch(failure => {
      if (token === generation.current) setError(failure instanceof Error ? failure.message : 'Mitra could not respond. Please retry.');
    }).finally(() => {
      if (token === generation.current) { ownsRun.current = false; setSending(false); }
    });
  }, [active, voice.phase, voice.draft, sending, voice.cancel]);
  useEffect(() => {
    if (active && (running || pending)) { voice.cancel(); stopAudio(); setSpeaking(false); setPreparing(false); }
  }, [active, running, pending, voice.cancel]);
  useEffect(() => {
    if (!active || running || sending || pending || !latest || latest.status === 'working' || lastSpoken.current === latest.id) return;
    if (!latest.text && !latest.error) return;
    lastSpoken.current = latest.id;
    if (latest.error) { setError(latest.error); return; }
    const token = generation.current;
    const abort = new AbortController(); request.current = abort;
    const timeout = setTimeout(() => abort.abort(), 30000);
    failedAnswer.current = '';
    setPreparing(true); setError(''); voice.cancel();
    const text = latest.text.replace(/```[\s\S]*?```/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[#*_`]/g, '').slice(0, 2500);
    void (async () => {
      try {
        const response = await apiFetch(`${apiBase}/api/speech/synthesize`, { method: 'POST', signal: abort.signal,
          headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, language: voiceLanguageCode() }) });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Playback unavailable. Your answer is in the chat.');
        if (token !== generation.current || abort.signal.aborted) return;
        if (typeof result.audio !== 'string' || result.mime_type !== 'audio/wav') throw new Error('Playback unavailable. Your answer is in the chat.');
        await playback.current.play(result.audio, () => {
          if (token === generation.current) { request.current = null; setSpeaking(false); }
        });
        if (token === generation.current && !abort.signal.aborted) { setPreparing(false); setSpeaking(true); }
      } catch (failure) {
        if (token === generation.current) { if (!abort.signal.aborted) { failedAnswer.current = latest.id; setError(failure instanceof Error ? failure.message : 'Playback unavailable.'); } stopAudio(); setSpeaking(false); setPreparing(false); }
      } finally { clearTimeout(timeout); }
    })();
  }, [active, running, sending, pending, latest, retry, voice.cancel]);
  async function resume() {
    voice.cancel();
    try {
      await unlockSpeechAudio();
      if (failedAnswer.current) { lastSpoken.current = ''; setRetry(value => value + 1); }
      setError('');
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Audio unavailable.'); }
  }
  function interrupt() {
    generation.current++; stopAudio(); onInterrupt(); voice.cancel();
    ownsRun.current = false; lastSpoken.current = latest?.id || ''; setSpeaking(false); setPreparing(false); setSending(false); setError('');
  }
  const status = error || voice.error || voiceStatus(pending ? 'review' : running || sending ? 'working' : speaking ? 'speaking' : preparing ? 'preparing' : muted ? 'muted' : voice.phase === 'transcribing' ? 'understanding' : voice.phase === 'requesting' ? 'connecting' : 'listening');
  return <>
    <button type="button" className={`live-voice-trigger ${active ? 'is-active' : ''}`} aria-label={active ? 'End live voice' : 'Start live voice'} title="Live voice" disabled={disabled || connecting} onClick={() => active ? end() : void begin()}><AudioLines size={18}/></button>
    {!active && error && <span className="live-voice-error" role="alert">{error}</span>}
    {active && container && createPortal(<section className="live-conversation" aria-label="Live voice conversation">
      <div className={`live-voice-orb ${speaking ? 'is-speaking' : ''} ${voice.phase === 'recording' ? 'is-listening' : ''}`} style={{ '--voice-level': voice.level } as CSSProperties} aria-hidden="true"><span/><span/></div>
      <div key={voice.interim || status} className="live-voice-caption" translate={error || voice.error ? undefined : 'no'} aria-live="polite">{voice.interim || status}</div>

    </section>, container)}
    {active && (<div className="live-voice-controls">
        {(running || speaking || preparing) && <button type="button" aria-label="Interrupt Mitra" onClick={interrupt}><Square size={15}/></button>}
        {(voice.error || error) && <button type="button" className="live-resume" onClick={() => void resume()}>{failedAnswer.current ? 'Retry audio' : 'Resume'}</button>}
        {voice.phase === 'recording' && <button type="button" className="live-stop-recording" aria-label="Done speaking" title="Done speaking" onClick={voice.stop}><Square size={15}/></button>}
        <button type="button" aria-label={muted ? 'Unmute microphone' : 'Mute microphone'} onClick={() => { voice.cancel(); setMuted(value => !value); }}>{muted ? <MicOff size={17}/> : <Mic size={17}/>}</button>
        <button type="button" className="live-end" aria-label="End live conversation" onClick={end}><X size={18}/></button>
      </div>)}
  </>;
}
