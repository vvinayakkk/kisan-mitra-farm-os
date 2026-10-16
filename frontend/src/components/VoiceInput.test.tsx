import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { VoiceInput } from './VoiceInput';
const voice = vi.hoisted(() => ({ phase: 'review', seconds: 0, level: 0, draft: 'I grow wheat on 2 acres', setDraft: vi.fn(), interim: '', source: 'Actual provider', error: '', start: vi.fn(), stop: vi.fn(), cancel: vi.fn() }));
vi.mock('@/hooks/useVoiceInput', () => ({ useVoiceInput: () => voice, VOICE_LANGUAGES: [['en-IN', 'English'], ['hi-IN', 'हिन्दी']], VOICE_LIMIT_SECONDS: 30, voiceLanguageCode: () => 'en-IN' }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it('keeps dictation hidden until requested and inserts only after review', () => {
  const onTranscript = vi.fn();
  render(<VoiceInput onTranscript={onTranscript} label="Speak to Mitra" />);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Speak to Mitra' }));
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  expect(screen.getByRole('textbox', { name: 'Review spoken words' })).toHaveValue('I grow wheat on 2 acres');
  expect(onTranscript).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Use these words' }));
  expect(onTranscript).toHaveBeenCalledWith('I grow wheat on 2 acres');
  expect(voice.cancel).toHaveBeenCalled();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
it('cancel never inserts or sends words', () => {
  const onTranscript = vi.fn();
  render(<VoiceInput onTranscript={onTranscript} />);
  fireEvent.click(screen.getByRole('button', { name: 'Speak your words' }));
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(onTranscript).not.toHaveBeenCalled();
  expect(voice.cancel).toHaveBeenCalled();
});
it('opens a side panel without an overlay and keeps review before insertion', () => {
  const onTranscript = vi.fn();
  render(<VoiceInput presentation="side" onTranscript={onTranscript} />);
  fireEvent.click(screen.getByRole('button', { name: 'Speak your words' }));
  expect(screen.getByRole('complementary', { name: 'Voice input' })).toBeInTheDocument();
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(document.querySelector('.voice-input-overlay')).toBeNull();
  expect(voice.start).not.toHaveBeenCalled();
  expect(onTranscript).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Use these words' }));
  expect(onTranscript).toHaveBeenCalledWith('I grow wheat on 2 acres');
  expect(screen.queryByRole('complementary')).toBeNull();
});
it('cancels side input when the chat becomes inactive', () => {
  const onTranscript = vi.fn();
  const { rerender } = render(<VoiceInput presentation="side" onTranscript={onTranscript} />);
  fireEvent.click(screen.getByRole('button', { name: 'Speak your words' }));
  rerender(<VoiceInput presentation="side" disabled onTranscript={onTranscript} />);
  expect(screen.queryByRole('complementary')).toBeNull();
  expect(voice.cancel).toHaveBeenCalled();
  expect(onTranscript).not.toHaveBeenCalled();
});
