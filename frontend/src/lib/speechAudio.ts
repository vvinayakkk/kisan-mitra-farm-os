/** Unlock output during the click, before network work loses browser activation.
 * Microphone capture has its own context; cancelling capture cannot close output.
 */
let outputContext: AudioContext | null = null;
export function unlockSpeechAudio(): Promise<void> {
  const AudioCtor = window.AudioContext || (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtor) return Promise.reject(new Error('Audio playback is unavailable in this browser.'));
  try {
    if (!outputContext || outputContext.state === 'closed') outputContext = new AudioCtor();
    const context = outputContext;
    // Call resume synchronously within the gesture (Safari/iOS require this).
    const resumed = context.state === 'running' ? Promise.resolve() : context.resume();
    return new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(() => reject(new Error('Tap Retry audio to enable your speaker.')), 3000);
      resumed.then(() => { window.clearTimeout(timer); resolve(); }, error => { window.clearTimeout(timer); reject(error); });
    }).then(() => {
      if (context.state !== 'running') throw new Error('Tap Retry audio to enable your speaker.');
    });
  } catch (error) { return Promise.reject(error); }
}

export class SpeechAudio {
  private source: AudioBufferSourceNode | null = null;
  private version = 0;
  stop() {
    this.version++;
    if (this.source) { this.source.onended = null; this.source.stop(); this.source.disconnect(); this.source = null; }
  }
  async play(encoded: string, onEnded: () => void) {
    this.stop();
    const version = this.version;
    const context = outputContext;
    if (!context || context.state !== 'running') throw new Error('Tap Retry audio to enable your speaker.');
    const bytes = Uint8Array.from(atob(encoded), character => character.charCodeAt(0));
    const buffer = await context.decodeAudioData(bytes.buffer);
    if (version !== this.version) return;
    if (!buffer.length) throw new Error('The voice reply contained no audio.');
    const source = context.createBufferSource();
    source.buffer = buffer; source.connect(context.destination); this.source = source;
    source.onended = () => {
      if (version !== this.version) return;
      source.disconnect(); this.source = null; onEnded();
    };
    source.start();
  }
}
