import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AnswerActions } from './AnswerActions';
vi.mock('@/components/SpeechPlayback', () => ({ SpeechPlayback: () => <button>Read aloud</button> }));
beforeEach(() => sessionStorage.clear());
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it('copies only selected answer and reports clipboard failure honestly', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
  render(<AnswerActions text="Seeds ₹150" messageId="a" scope="farmer-a" />);
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Copy answer' })));
  expect(writeText).toHaveBeenCalledWith('Seeds ₹150');
  expect(screen.getByRole('status')).toHaveTextContent('Answer copied.');
  writeText.mockRejectedValue(new Error('Denied'));
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Copy answer' })));
  expect(screen.getByRole('status')).toHaveTextContent('Copy is unavailable');
});
it('shares content by explicit click without creating public URL', async () => {
  const share = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'share', { configurable: true, value: share });
  render(<AnswerActions text="Private farm answer" messageId="a" scope="farmer-a" />);
  expect(share).not.toHaveBeenCalled();
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Share answer' })));
  expect(share).toHaveBeenCalledWith({ title: 'Kisan Mitra answer', text: 'Private farm answer' });
});
it('stores scoped ratings locally and states they are not sent', () => {
  render(<AnswerActions text="Answer" messageId="a" scope="farmer-a" />);
  fireEvent.click(screen.getByRole('button', { name: 'Helpful answer' }));
  expect(sessionStorage.getItem('mitra-answer-rating:farmer-a:a')).toBe('up');
  expect(screen.getByRole('status')).toHaveTextContent('not sent to Mitra');
  expect(sessionStorage.getItem('mitra-answer-rating:farmer-b:a')).toBeNull();
});
it('keeps rewrite separate and clearly unsaved without resending tasks', async () => {
  const rewrite = vi.fn().mockResolvedValue('A clearer answer');
  render(<AnswerActions text="Original answer" messageId="a" scope="farmer-a" onRetry={rewrite} />);
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Rewrite answer without repeating tasks' })));
  expect(rewrite).toHaveBeenCalledOnce();
  expect(screen.getByText('A clearer answer')).toBeInTheDocument();
  expect(screen.getByText('Not saved · original above')).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Original answer kept');
});
it('omits rewrite when answer is ineligible', () => {
  render(<AnswerActions text="Answer" messageId="a" scope="farmer-a" />);
  expect(screen.queryByRole('button', { name: /Rewrite answer/ })).not.toBeInTheDocument();
});
