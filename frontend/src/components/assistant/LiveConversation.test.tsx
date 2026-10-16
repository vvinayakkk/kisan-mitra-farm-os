import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ fetch: vi.fn(), unlock: vi.fn(), play: vi.fn(), stopAudio: vi.fn(), start: vi.fn(), cancel: vi.fn(), stop: vi.fn(), voice: { phase: 'idle', draft: '', interim: '', level: 0, error: '' } }));
vi.mock('@/lib/speechAudio', () => ({ unlockSpeechAudio: mocks.unlock, SpeechAudio: class { stop = mocks.stopAudio; play = mocks.play; } }));
vi.mock('@/lib/apiClient', () => ({ apiFetch: mocks.fetch }));
vi.mock('@/hooks/useVoiceInput', () => ({ voiceLanguageCode: () => 'en-IN', useVoiceInput: () => ({ ...mocks.voice, start: mocks.start, cancel: mocks.cancel, stop: mocks.stop }) }));
import { LiveConversation } from './LiveConversation';
let slot: HTMLDivElement;
const props = () => ({ container: slot, disabled: false, running: false, pending: false, onSend: vi.fn(async () => {}), onInterrupt: vi.fn(), onActive: vi.fn() });
beforeEach(() => { vi.clearAllMocks(); mocks.unlock.mockResolvedValue(undefined); mocks.play.mockResolvedValue(undefined); mocks.voice = { phase: 'idle', draft: '', interim: '', level: 0, error: '' }; slot = document.createElement('div'); document.body.append(slot); mocks.fetch.mockResolvedValue({ ok: true, json: async () => ({ conversation_available: true, playback_languages: ['en-IN'] }) }); });
afterEach(() => { cleanup(); slot.remove(); vi.restoreAllMocks(); });
async function start() { await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Start live voice' }))); }
it('never requests a microphone or provider before an explicit start and mounts inline, not a dialog', async () => {
  const p = props(); render(<LiveConversation {...p}/>); expect(mocks.fetch).not.toHaveBeenCalled(); expect(mocks.start).not.toHaveBeenCalled();
  await start(); expect(slot).toContainElement(screen.getByRole('region', { name: 'Live voice conversation' })); expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await waitFor(() => expect(mocks.start).toHaveBeenCalledWith('en-IN', false, true)); expect(p.onActive).toHaveBeenCalledWith(true);
});
it('sends the final spoken turn through the shared agent exactly once', async () => {
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start();
  mocks.voice.phase = 'review'; mocks.voice.draft = 'Plan my wheat harvest';
  await act(async () => rerender(<LiveConversation {...p}/>));
  expect(p.onSend).toHaveBeenCalledOnce(); expect(p.onSend).toHaveBeenCalledWith('Plan my wheat harvest'); expect(mocks.cancel).toHaveBeenCalled();
});
it('holds listening for approval cards and allows end without approving anything', async () => {
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start();
  rerender(<LiveConversation {...p} pending/>); expect(screen.getByText('Review the card to continue')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'End live conversation' })); expect(screen.queryByRole('region')).not.toBeInTheDocument(); expect(p.onSend).not.toHaveBeenCalled(); expect(p.onActive).toHaveBeenLastCalledWith(false);
});
it('mutes the microphone and releases recording without losing typed chat state', async () => {
  const p = props(); render(<LiveConversation {...p}/>); await start(); mocks.cancel.mockClear();
  fireEvent.click(screen.getByRole('button', { name: 'Mute microphone' })); expect(mocks.cancel).toHaveBeenCalled(); expect(screen.getByText('Microphone off')).toBeInTheDocument(); expect(p.onSend).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Unmute microphone' })); expect(screen.getByText('Listening')).toBeInTheDocument();
});
it('finishes recording with an icon-only stop control', async () => {
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start();
  mocks.voice.phase = 'recording'; rerender(<LiveConversation {...p}/>);
  const stop = screen.getByRole('button', { name: 'Done speaking' });
  expect(stop).toHaveClass('live-stop-recording');
  expect(stop).toHaveTextContent('');
  fireEvent.click(stop); expect(mocks.stop).toHaveBeenCalledOnce();
});
it('reports unavailable providers without pretending a live call started', async () => {
  mocks.fetch.mockResolvedValue({ ok: true, json: async () => ({ conversation_available: false }) });
  const p = props(); render(<LiveConversation {...p}/>); await start(); expect(screen.getByRole('alert')).toHaveTextContent('unavailable'); expect(screen.queryByRole('region')).not.toBeInTheDocument(); expect(mocks.start).not.toHaveBeenCalled(); expect(p.onActive).not.toHaveBeenCalled();
});
it('ending live voice does not cancel a separately typed farm response', async () => {
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start(); rerender(<LiveConversation {...p} running/>);
  fireEvent.click(screen.getByRole('button', { name: 'End live conversation' })); expect(p.onInterrupt).not.toHaveBeenCalled(); expect(mocks.cancel).toHaveBeenCalled();
});
it('cancels an in-flight synthesis and ignores audio that arrives after end', async () => {
  let finish!: (value: unknown) => void;
  const delayed = new Promise(resolve => { finish = resolve; });
  const capabilities = { ok: true, json: async () => ({ conversation_available: true, playback_languages: ['en-IN'] }) };
  mocks.fetch.mockImplementation((url: string) => url.includes('capabilities') ? Promise.resolve(capabilities) : delayed);
  const audio = vi.fn(); vi.stubGlobal('Audio', audio);
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start();
  rerender(<LiveConversation {...p} latest={{ id: 'new-answer', role: 'assistant', text: 'Check soil before sowing.', activities: [], status: 'done' }}/>);
  await waitFor(() => expect(mocks.fetch).toHaveBeenCalledTimes(2));
  const signal = mocks.fetch.mock.calls[1][1].signal as AbortSignal;
  fireEvent.click(screen.getByRole('button', { name: 'End live conversation' })); expect(signal.aborted).toBe(true);
  await act(async () => finish({ ok: true, json: async () => ({ audio: 'UklGRg==', mime_type: 'audio/wav' }) }));
  expect(audio).not.toHaveBeenCalled(); vi.unstubAllGlobals();
});
it('interrupt cancels playback preparation and the active farm response', async () => {
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start(); rerender(<LiveConversation {...p} running/>);
  fireEvent.click(screen.getByRole('button', { name: 'Interrupt Mitra' })); expect(p.onInterrupt).toHaveBeenCalledOnce(); expect(mocks.cancel).toHaveBeenCalled();
});
it('provider quota failure is reported and does not re-record automatically', async () => {
  mocks.fetch.mockImplementation((url: string) => Promise.resolve(url.includes('capabilities') ? { ok: true, json: async () => ({ conversation_available: true, playback_languages: ['en-IN'] }) } : { ok: false, status: 429, json: async () => ({}) }));
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start(); mocks.start.mockClear();
  rerender(<LiveConversation {...p} latest={{ id: 'answer', role: 'assistant', text: 'Your farm plan is ready.', activities: [], status: 'done' }}/>);
  await screen.findByText('Playback unavailable. Your answer is in the chat.'); expect(mocks.start).not.toHaveBeenCalled(); expect(screen.getByRole('button', { name: 'Retry audio' })).toBeInTheDocument();
});
it('unmount aborts capability requests before any late microphone start', async () => {
  let finish!: (value: unknown) => void; mocks.fetch.mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const p = props(); const { unmount } = render(<LiveConversation {...p}/>); fireEvent.click(screen.getByRole('button', { name: 'Start live voice' }));
  await waitFor(() => expect(mocks.fetch).toHaveBeenCalledOnce()); const signal = mocks.fetch.mock.calls[0][1].signal as AbortSignal; unmount(); expect(signal.aborted).toBe(true);
  await act(async () => finish({ ok: true, json: async () => ({ conversation_available: true, playback_languages: ['en-IN'] }) })); expect(mocks.start).not.toHaveBeenCalled();
});

it('end cancels the current voice-owned farm run while keeping approval decisions manual', async () => {
  let finish!: () => void;
  const p = props(); p.onSend = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
  const { rerender } = render(<LiveConversation {...p}/>); await start();
  mocks.voice.phase = 'review'; mocks.voice.draft = 'Create a crop plan'; rerender(<LiveConversation {...p}/>);
  await waitFor(() => expect(p.onSend).toHaveBeenCalledOnce());
  rerender(<LiveConversation {...p} running/>); fireEvent.click(screen.getByRole('button', { name: 'End live conversation' }));
  expect(p.onInterrupt).toHaveBeenCalledOnce(); await act(async () => finish()); expect(screen.queryByRole('region')).not.toBeInTheDocument();
});

it('uses the configured backend origin for capability checks and synthesis', async () => {
  vi.stubEnv('VITE_API_URL', 'https://farm-api.example');
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start();
  expect(mocks.fetch.mock.calls[0][0]).toBe('https://farm-api.example/api/speech/capabilities');
  rerender(<LiveConversation {...p} latest={{ id: 'origin-answer', role: 'assistant', text: 'Farm answer.', activities: [], status: 'done' }}/>);
  await waitFor(() => expect(mocks.fetch.mock.calls[1][0]).toBe('https://farm-api.example/api/speech/synthesize'));
  vi.unstubAllEnvs();
});

it('ends microphone and playback when the chat view is hidden', async () => {
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start();
  mocks.cancel.mockClear(); rerender(<LiveConversation {...p} visible={false}/>);
  expect(mocks.cancel).toHaveBeenCalled(); expect(screen.queryByRole('region')).not.toBeInTheDocument(); expect(p.onActive).toHaveBeenLastCalledWith(false);
});
it('starts from the companion Talk request only after explicit request', async () => {
  const p = props(); const { rerender } = render(<LiveConversation {...p} startRequest={0}/>);
  expect(mocks.fetch).not.toHaveBeenCalled(); rerender(<LiveConversation {...p} startRequest={1}/>);
  await screen.findByRole('button', { name: 'End live conversation' }); expect(mocks.fetch).toHaveBeenCalledOnce();
});

it('unlocks audio before the capability request and plays the actual completed reply', async () => {
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start();
  expect(mocks.unlock.mock.invocationCallOrder[0]).toBeLessThan(mocks.fetch.mock.invocationCallOrder[0]);
  mocks.fetch.mockResolvedValue({ok:true,json:async()=>({audio:'UklGRg==',mime_type:'audio/wav'})});
  rerender(<LiveConversation {...p} latest={{id:'spoken',role:'assistant',text:'नमस्ते',activities:[],status:'completed'}}/>);
  await waitFor(()=>expect(mocks.play).toHaveBeenCalledOnce());
  expect(mocks.play.mock.calls[0][0]).toBe('UklGRg==');
  expect(screen.getByText('Mitra is speaking')).toBeInTheDocument();
  await act(async()=>mocks.play.mock.calls[0][1]());
  await waitFor(()=>expect(screen.getByText('Listening')).toBeInTheDocument());
});
it('retries the same failed reply instead of skipping it as already spoken', async () => {
  const p = props(); const { rerender } = render(<LiveConversation {...p}/>); await start();
  mocks.fetch.mockResolvedValueOnce({ok:false,json:async()=>({detail:'Temporarily unavailable'})});
  rerender(<LiveConversation {...p} latest={{id:'retry-me',role:'assistant',text:'Try this plan.',activities:[],status:'completed'}}/>);
  await screen.findByText('Temporarily unavailable');
  mocks.fetch.mockResolvedValue({ok:true,json:async()=>({audio:'UklGRg==',mime_type:'audio/wav'})});
  fireEvent.click(screen.getByRole('button',{name:'Retry audio'}));
  await waitFor(()=>expect(mocks.play).toHaveBeenCalledOnce());
  expect(mocks.unlock).toHaveBeenCalledTimes(2);
});

it('surfaces a failed agent turn even when no answer text was generated', async () => {
  const p = props(); const {rerender} = render(<LiveConversation {...p}/>); await start();
  rerender(<LiveConversation {...p} latest={{id:'failed', role:'assistant', text:'', activities:[], status:'done', error:'The provider is unavailable'}}/>);
  expect(await screen.findByText('The provider is unavailable')).toBeInTheDocument();
  expect(mocks.play).not.toHaveBeenCalled();
});
