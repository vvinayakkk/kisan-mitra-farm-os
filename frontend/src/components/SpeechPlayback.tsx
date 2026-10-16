import { useEffect, useRef, useState } from 'react';
import { Volume2, Square, Loader2 } from 'lucide-react';
import { apiFetch } from '@/lib/apiClient';
import { SpeechAudio, unlockSpeechAudio } from '@/lib/speechAudio';
import { voiceLanguageCode } from '@/hooks/useVoiceInput';


export function SpeechPlayback({ text, language, compact = false }: { text: string; language?: string; compact?: boolean }) {
  const [phase, setPhase] = useState<'idle' | 'loading' | 'playing'>('idle');
  const [error, setError] = useState('');
  const audio = useRef(new SpeechAudio());
  const pending = useRef<AbortController | null>(null);
  const version = useRef(0);
  function stop() {
    version.current++; pending.current?.abort(); audio.current.stop(); setPhase('idle');
  }
  useEffect(() => () => { version.current++; pending.current?.abort(); audio.current.stop(); }, []);
  async function play() {
    if (phase !== 'idle') { stop(); return; }
    stop(); const token = version.current;
    const abort = new AbortController(); pending.current = abort; setPhase('loading'); setError('');
    const timeout = setTimeout(() => abort.abort(), 25000);
    try {
      await unlockSpeechAudio();
      const spoken = text.replace(/!\[[^\]]*\]\([^)]*\)/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[*#`]/g, '').slice(0, 2500);
      const response = await apiFetch(`${import.meta.env.VITE_API_URL || ''}/api/speech/synthesize`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: spoken, language: voiceLanguageCode(language) }), signal: abort.signal });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Read aloud is unavailable.');
      if (token !== version.current) return;
      await audio.current.play(body.audio, () => { if (token === version.current) stop(); });
      if (token === version.current) setPhase('playing');
    } catch (failure) {
      if (token !== version.current) return;
      stop(); setError(abort.signal.aborted ? 'Read aloud timed out. Please retry.' : failure instanceof Error ? failure.message : 'Read aloud is unavailable.');
    } finally { clearTimeout(timeout); }
  }
  return <span className={compact ? "speech-playback-compact" : "inline-flex flex-col items-start mt-2"}><button type="button" className={compact ? "answer-action" : "inline-flex gap-1.5 items-center text-xs opacity-70 hover:opacity-100"} data-hint={compact ? phase === "idle" ? "Read aloud" : "Stop audio" : undefined} aria-label={phase === 'idle' ? 'Read response aloud' : 'Stop reading aloud'} onClick={() => void play()}>{phase === 'loading' ? <Loader2 size={14} className="animate-spin" /> : phase === 'playing' ? <Square size={13} /> : <Volume2 size={14} />}{!compact && (phase === 'idle' ? 'Read aloud' : phase === 'loading' ? 'Cancel audio' : 'Stop audio')}</button>{error && <span role="alert" className="text-xs text-red-700">{error}</span>}</span>;
}
