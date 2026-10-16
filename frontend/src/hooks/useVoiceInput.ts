import { useCallback, useEffect, useRef, useState } from 'react';
import { preferredLanguage, normalizeLanguage } from '@/lib/languagePreference';
import { apiFetch } from '@/lib/apiClient';

export const VOICE_LIMIT_SECONDS = 30;
const AUDIO_LIMIT = 5 * 1024 * 1024;
export type VoicePhase = 'idle' | 'requesting' | 'recording' | 'transcribing' | 'review' | 'error';
export const VOICE_LANGUAGES = [
  ['en-IN', 'English'], ['hi-IN', 'हिन्दी'], ['bn-IN', 'বাংলা'], ['mr-IN', 'मराठी'],
  ['te-IN', 'తెలుగు'], ['ta-IN', 'தமிழ்'], ['gu-IN', 'ગુજરાતી'], ['kn-IN', 'ಕನ್ನಡ'],
  ['ml-IN', 'മലയാളം'], ['pa-IN', 'ਪੰਜਾਬੀ'], ['od-IN', 'ଓଡ଼ିଆ'], ['as-IN', 'অসমীয়া'], ['ur-IN', 'اردو'],
] as const;

export function voiceLanguageCode(language?: string): string {
  const code = normalizeLanguage(language) || preferredLanguage();
  return (code === 'or' ? 'od' : code) + '-IN';
}

export function preferredRecorderType() {
  return ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/webm']
    .find(type => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type)) || '';
}

export function voiceError(error: unknown) {
  if (error instanceof DOMException) {
    if (error.name === 'NotAllowedError') return 'Allow microphone access in your browser, or type your words.';
    if (error.name === 'NotFoundError') return 'No microphone was found. Connect one, or type your words.';
    if (error.name === 'NotReadableError') return 'Another app may be using your microphone. Close it and try again.';
  }
  return error instanceof Error ? error.message : 'Voice is unavailable. Your typed words are safe.';
}


export function useVoiceInput() {
  const [phase, setPhase] = useState<VoicePhase>('idle');
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [draft, setDraft] = useState('');
  const [interim, setInterim] = useState('');
  const [source, setSource] = useState('');
  const [error, setError] = useState('');
  const generation = useRef(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const context = useRef<AudioContext | null>(null);
  const frame = useRef<number>();
  const timer = useRef<ReturnType<typeof setInterval>>();
  const recognition = useRef<any>(null);
  const request = useRef<AbortController | null>(null);
  const active = useRef(false);

  const release = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    if (frame.current !== undefined) cancelAnimationFrame(frame.current);
    recognition.current?.abort?.();
    recognition.current = null;
    stream.current?.getTracks().forEach(track => track.stop());
    stream.current = null;
    void context.current?.close().catch(() => {});
    context.current = null;
    active.current = false;
  }, []);

  const cancel = useCallback(() => {
    generation.current++;
    request.current?.abort();
    if (recorder.current?.state !== 'inactive') recorder.current?.stop();
    recorder.current = null;
    release();
    setPhase('idle'); setSeconds(0); setLevel(0); setDraft(''); setInterim(''); setError(''); setSource('');
  }, [release]);

  useEffect(() => () => {
    generation.current++;
    request.current?.abort();
    if (recorder.current?.state !== 'inactive') recorder.current?.stop();
    release();
  }, [release]);

  const stop = useCallback(() => {
    if (recorder.current?.state === 'recording') {
      setPhase('transcribing');
      recorder.current.stop();
      release();
      setLevel(0);
    }
  }, [release]);

  const start = useCallback(async (language = 'en-IN', liveCaptions = false, autoStop = false) => {
    if (active.current) return;
    cancel();
    const token = generation.current;
    active.current = true;
    setPhase('requesting');
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
        throw new Error('This browser cannot record audio. Open a supported browser on HTTPS, or type your words.');
      }
      const input = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      if (token !== generation.current) { input.getTracks().forEach(track => track.stop()); return; }
      stream.current = input;
      const mimeType = preferredRecorderType();
      const recording = new MediaRecorder(input, mimeType ? { mimeType } : undefined);
      recorder.current = recording;
      const chunks: Blob[] = [];
      let size = 0;
      recording.ondataavailable = event => {
        if (token !== generation.current || !event.data.size) return;
        size += event.data.size; chunks.push(event.data);
        if (size > AUDIO_LIMIT) stop();
      };
      recording.onerror = () => {
        if (token !== generation.current) return;
        generation.current++; release(); setPhase('error'); setError('The recording stopped unexpectedly. Please try again.');
      };
      recording.onstop = async () => {
        if (token !== generation.current) return;
        release();
        setLevel(0);
        setPhase('transcribing');
        const audio = new Blob(chunks, { type: recording.mimeType || 'audio/webm' });
        if (!audio.size || audio.size > AUDIO_LIMIT) {
          setPhase('error'); setError('Use a short recording below 5 MB. Nothing was sent.'); return;
        }
        const abort = new AbortController();
        request.current = abort;
        const timeout = setTimeout(() => abort.abort(), 48000);
        try {
          const form = new FormData();
          const extension = audio.type.includes('mp4') ? 'm4a' : audio.type.includes('ogg') ? 'ogg' : 'webm';
          form.append('file', audio, `recording.${extension}`);
          form.append('language_code', language);
          const response = await apiFetch(`${import.meta.env.VITE_API_URL || ''}/api/speech/transcribe`, { method: 'POST', body: form, signal: abort.signal });
          const body = await response.json();
          if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Transcription is unavailable. Retry or type your words.');
          if (typeof body.transcript !== 'string' || !body.transcript.trim()) throw new Error('No words were heard. Please try again.');
          if (token !== generation.current) return;
          setDraft(body.transcript.trim()); setSource(body.source || 'Speech transcription'); setInterim(''); setPhase('review');
        } catch (failure) {
          if (token !== generation.current) return;
          setError(abort.signal.aborted ? 'Transcription took too long. Please try a shorter recording.' : voiceError(failure));
          setPhase('error');
        } finally { clearTimeout(timeout); }
      };
      recording.start(250);
      setPhase('recording');
      const began = Date.now();
      timer.current = setInterval(() => {
        if (token !== generation.current) return;
        const elapsed = Math.floor((Date.now() - began) / 1000);
        setSeconds(Math.min(elapsed, VOICE_LIMIT_SECONDS));
        if (elapsed >= VOICE_LIMIT_SECONDS) stop();
      }, 200);

      try {
        const AudioCtor = window.AudioContext || (window as any).webkitAudioContext;
        if (AudioCtor) {
          const audioContext = new AudioCtor(); context.current = audioContext;
          const analyser = audioContext.createAnalyser(); analyser.fftSize = 256;
          audioContext.createMediaStreamSource(input).connect(analyser);
          void audioContext.resume();
          const samples = new Uint8Array(analyser.fftSize);
          let measuredAt = 0;
          let heardAt = 0;
          const meterBegan = performance.now();
          const measure = (now: number) => {
            if (token !== generation.current || !active.current) return;
            if (now - measuredAt > 80) {
              analyser.getByteTimeDomainData(samples);
              const rms = Math.sqrt(samples.reduce((sum, v) => sum + ((v - 128) / 128) ** 2, 0) / samples.length);
              setLevel(Math.min(1, rms * 6)); measuredAt = now;
              if (rms > 0.018) heardAt = now;
              if (autoStop && heardAt && now - heardAt > 1300 && now - meterBegan > 1700) { stop(); return; }
              if (autoStop && !heardAt && now - meterBegan > 12000) {
                generation.current++; recording.stop(); release(); setLevel(0);
                setPhase('error'); setError('No speech heard. Resume when you are ready.'); return;
              }
            }
            frame.current = requestAnimationFrame(measure);
          };
          frame.current = requestAnimationFrame(measure);
        }
      } catch {                                                                     }
      if (liveCaptions) {
        const Recognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (Recognition) {
          const browserSpeech = new Recognition(); recognition.current = browserSpeech;
          browserSpeech.lang = language; browserSpeech.continuous = true; browserSpeech.interimResults = true;
          browserSpeech.onresult = (event: any) => {
            if (token !== generation.current) return;
            setInterim(Array.from(event.results as ArrayLike<any>).map(result => result[0]?.transcript || '').join(' '));
          };
          browserSpeech.onerror = () => { if (token === generation.current) setInterim('Live captions unavailable; your recording continues.'); };
          try { browserSpeech.start(); } catch {                                                     }
        }
      }
    } catch (failure) {
      if (token !== generation.current) return;
      release(); setError(voiceError(failure)); setPhase('error');
    }
  }, [cancel, release, stop]);

  return { phase, seconds, level, draft, setDraft, interim, source, error, start, stop, cancel };
}
