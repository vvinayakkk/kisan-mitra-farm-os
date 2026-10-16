import { afterEach, beforeEach, expect, it, vi } from 'vitest';
let context: any;
beforeEach(() => {
  vi.resetModules();
  context = {state:'suspended', resume:vi.fn(async()=>{context.state='running';}), destination:{}, decodeAudioData:vi.fn(async()=>({length:10})), createBufferSource:vi.fn(()=>({connect:vi.fn(),disconnect:vi.fn(),start:vi.fn(),stop:vi.fn(),onended:null}))};
  vi.stubGlobal('AudioContext', class { constructor() { return context; } });
});
afterEach(()=>vi.unstubAllGlobals());
it('resumes the output synchronously with the gesture and uses decoded provider audio', async()=>{
  const {SpeechAudio,unlockSpeechAudio}=await import('./speechAudio');
  const unlock=unlockSpeechAudio(); expect(context.resume).toHaveBeenCalledOnce(); await unlock;
  const output=new SpeechAudio(); const ended=vi.fn(); await output.play('UklGRg==',ended);
  const source=context.createBufferSource.mock.results[0].value;
  expect(source.start).toHaveBeenCalledOnce(); expect(source.connect).toHaveBeenCalledWith(context.destination);
  source.onended(); expect(ended).toHaveBeenCalledOnce();
});
it('cancelling during decoding prevents late audio from playing', async()=>{
  const {SpeechAudio,unlockSpeechAudio}=await import('./speechAudio'); await unlockSpeechAudio();
  let resolve!: (value:unknown)=>void; context.decodeAudioData.mockReturnValue(new Promise(r=>{resolve=r;}));
  const output=new SpeechAudio(); const playing=output.play('UklGRg==',vi.fn()); output.stop(); resolve({length:10}); await playing;
  expect(context.createBufferSource).not.toHaveBeenCalled();
});
it('stops and disconnects output without closing the unlocked context', async()=>{
  const {SpeechAudio,unlockSpeechAudio}=await import('./speechAudio'); await unlockSpeechAudio();
  const output=new SpeechAudio(); await output.play('UklGRg==',vi.fn()); const source=context.createBufferSource.mock.results[0].value; output.stop();
  expect(source.stop).toHaveBeenCalledOnce(); expect(source.disconnect).toHaveBeenCalledOnce(); expect(context.state).toBe('running'); expect(source.onended).toBeNull();
});
it('reports a suspended output rather than pretending speech played', async()=>{
  const {SpeechAudio}=await import('./speechAudio'); await expect(new SpeechAudio().play('UklGRg==',vi.fn())).rejects.toThrow('Retry audio');
});
