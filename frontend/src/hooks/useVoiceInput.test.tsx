import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useVoiceInput, voiceError, voiceLanguageCode } from './useVoiceInput';
import { apiFetch } from '@/lib/apiClient';
vi.mock('@/lib/apiClient', () => ({ apiFetch: vi.fn() }));

class Recorder {
  static instance: Recorder;
  static isTypeSupported() { return true; }
  state = 'inactive';
  mimeType = 'audio/webm';
  ondataavailable?: (event: { data: Blob }) => void;
  onstop?: () => void;
  constructor() { Recorder.instance = this; }
  start() { this.state = 'recording'; }
  stop() {
    this.state = 'inactive';
    this.ondataavailable?.({ data: new Blob(['audio bytes'], { type: this.mimeType }) });
    void this.onstop?.();
  }
}
let trackStop: ReturnType<typeof vi.fn>;
beforeEach(() => {
  trackStop = vi.fn();
  vi.stubGlobal('MediaRecorder', Recorder);
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: trackStop }] }) } });
  vi.mocked(apiFetch).mockReset();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers(); });

describe('reviewed voice input lifecycle', () => {
  it('records once, releases microphone, and waits for explicit review', async () => {
    vi.mocked(apiFetch).mockResolvedValue(new Response(JSON.stringify({ transcript: 'I grow गेहूँ on 2 acres', source: 'Fixture transcription' }), { status: 200 }));
    const { result } = renderHook(() => useVoiceInput());
    await act(() => result.current.start('hi-IN'));
    expect(result.current.phase).toBe('recording');
    act(() => result.current.stop());
    await waitFor(() => expect(result.current.phase).toBe('review'));
    expect(result.current.draft).toBe('I grow गेहूँ on 2 acres');
    expect(result.current.source).toBe('Fixture transcription');
    expect(trackStop).toHaveBeenCalled();
    expect(apiFetch).toHaveBeenCalledTimes(1);
    act(() => result.current.setDraft('I grow wheat on 3 acres'));
    expect(result.current.draft).toContain('3 acres');
  });

  it('cancel discards recording without uploading it', async () => {
    const { result } = renderHook(() => useVoiceInput());
    await act(() => result.current.start());
    act(() => result.current.cancel());
    expect(apiFetch).not.toHaveBeenCalled();
    expect(trackStop).toHaveBeenCalled();
    expect(result.current.phase).toBe('idle');
  });

  it('closing while microphone permission is pending releases late streams', async () => {
    let resolve!: (input: unknown) => void;
    vi.mocked(navigator.mediaDevices.getUserMedia).mockImplementation(() => new Promise(done => { resolve = done; }) as Promise<MediaStream>);
    const { result } = renderHook(() => useVoiceInput());
    let pending!: Promise<void>;
    act(() => { pending = result.current.start(); });
    act(() => result.current.cancel());
    await act(async () => { resolve({ getTracks: () => [{ stop: trackStop }] }); await pending; });
    expect(trackStop).toHaveBeenCalled();
    expect(apiFetch).not.toHaveBeenCalled();
    expect(result.current.phase).toBe('idle');
  });

  it('cancel during transcription ignores a late provider response', async () => {
    let resolve!: (response: Response) => void;
    vi.mocked(apiFetch).mockImplementation(() => new Promise(done => { resolve = done; }));
    const { result } = renderHook(() => useVoiceInput());
    await act(() => result.current.start());
    act(() => result.current.stop());
    act(() => result.current.cancel());
    await act(async () => { resolve(new Response(JSON.stringify({ transcript: 'late words' }))); });
    expect(result.current.phase).toBe('idle');
    expect(result.current.draft).toBe('');
  });

  it('auto-stops at 30 seconds and shows provider failure without inventing words', async () => {
    vi.useFakeTimers();
    vi.mocked(apiFetch).mockResolvedValue(new Response(JSON.stringify({ detail: 'Provider unavailable' }), { status: 503 }));
    const { result } = renderHook(() => useVoiceInput());
    await act(() => result.current.start());
    await act(async () => { vi.advanceTimersByTime(30000); });
    expect(Recorder.instance.state).toBe('inactive');
    expect(result.current.phase).toBe('error');
    expect(result.current.error).toBe('Provider unavailable');
    expect(result.current.draft).toBe('');
  });

  it('unmount stops the microphone and never starts an upload', async () => {
    const { result, unmount } = renderHook(() => useVoiceInput());
    await act(() => result.current.start());
    unmount();
    expect(trackStop).toHaveBeenCalled();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it('explains permission and microphone errors in usable terms', () => {
    expect(voiceError(new DOMException('Denied', 'NotAllowedError'))).toContain('Allow microphone');
    expect(voiceError(new DOMException('Missing', 'NotFoundError'))).toContain('No microphone');
  });
});

it('uses the currently selected app language rather than a fixed English default', () => {
  localStorage.setItem('app_language', 'kn');
  expect(voiceLanguageCode()).toBe('kn-IN');
  expect(voiceLanguageCode('hi-IN')).toBe('hi-IN');
  expect(voiceLanguageCode('or')).toBe('od-IN');
  localStorage.removeItem('app_language');
});

it('ends an automatic conversation turn after speech followed by silence', async () => {
  let tick!: FrameRequestCallback;
  let loud = true;
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { tick = callback; return 1; });
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  vi.stubGlobal('AudioContext', class {
    createAnalyser() { return { fftSize: 256, getByteTimeDomainData: (samples: Uint8Array) => samples.fill(loud ? 148 : 128) }; }
    createMediaStreamSource() { return { connect: vi.fn() }; }
    resume() { return Promise.resolve(); } close() { return Promise.resolve(); }
  });
  vi.mocked(apiFetch).mockResolvedValue(new Response(JSON.stringify({ transcript: 'Help plan my farm week' }), { status: 200 }));
  const { result } = renderHook(() => useVoiceInput());
  await act(() => result.current.start('en-IN', false, true));
  const now = performance.now(); act(() => tick(now + 200)); loud = false;
  await act(async () => tick(now + 2000));
  await waitFor(() => expect(result.current.phase).toBe('review'));
  expect(apiFetch).toHaveBeenCalledOnce(); expect(trackStop).toHaveBeenCalled();
});
it('pauses silent automatic listening without uploading empty ambient audio', async () => {
  let tick!: FrameRequestCallback;
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { tick = callback; return 1; });
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  vi.stubGlobal('AudioContext', class {
    createAnalyser() { return { fftSize: 256, getByteTimeDomainData: (samples: Uint8Array) => samples.fill(128) }; }
    createMediaStreamSource() { return { connect: vi.fn() }; }
    resume() { return Promise.resolve(); } close() { return Promise.resolve(); }
  });
  const { result } = renderHook(() => useVoiceInput());
  await act(() => result.current.start('en-IN', false, true));
  act(() => tick(performance.now() + 13000));
  expect(result.current.phase).toBe('error'); expect(result.current.error).toContain('No speech heard'); expect(apiFetch).not.toHaveBeenCalled(); expect(trackStop).toHaveBeenCalled();
});
