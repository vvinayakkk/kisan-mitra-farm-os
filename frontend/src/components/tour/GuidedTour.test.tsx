import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { GuidedTour, tourPosition, visibleTarget } from './GuidedTour';
vi.mock('@/lib/assistantClient', () => ({ getAssistantSessionId: () => 'tour-owner' }));
const steps = [{ target: '#tour-target', title: 'Your first stop', body: 'Use this control.' }, { target: '#tour-second', title: 'Your next stop', body: 'Check the next control.' }];
const box = { x: 40, y: 80, left: 40, top: 80, width: 120, height: 44, right: 160, bottom: 124, toJSON: () => ({}) };
beforeEach(() => {
  localStorage.clear(); vi.useFakeTimers();
  vi.spyOn(performance, 'now').mockImplementation(() => Date.now());
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} });
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(box);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });
function mount() { return render(<><button id="tour-target">Target</button><button id="tour-second">Second</button><GuidedTour scope="test" steps={steps}/></>); }
async function tick(ms = 800) { await act(async () => { vi.advanceTimersByTime(ms); }); }
it('anchors to the real control, advances, traps focus, and restores focus after skip', async () => {
  mount(); screen.getByText('Target').focus(); await tick(); await tick(50);
  expect(screen.getByRole('dialog')).toHaveTextContent('Your first stop');
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Tab', shiftKey: true });
  expect(screen.getByRole('button', { name: 'Next' })).toHaveFocus();
  fireEvent.click(screen.getByRole('button', { name: 'Next' })); await tick(50);
  expect(screen.getByRole('dialog')).toHaveTextContent('Your next stop');
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' }); await tick(50);
  expect(screen.queryByRole('dialog')).toBeNull(); expect(screen.getByText('Target')).toHaveFocus();
  expect(localStorage.getItem('mitra-tour-v1:tour-owner:test')).toBe('done');
});
it('does not reopen completed tours, but replay always works', async () => {
  localStorage.setItem('mitra-tour-v1:tour-owner:test', 'done'); mount(); await tick();
  expect(screen.queryByRole('dialog')).toBeNull(); fireEvent.click(screen.getByRole('button', { name: 'Replay page tour' })); await tick(50);
  expect(screen.getByRole('dialog')).toHaveTextContent('Your first stop');
});
it('resumes an interrupted tour and keeps different account progress separate', async () => {
  localStorage.setItem('mitra-tour-v1:another-owner:test', 'done');
  localStorage.setItem('mitra-tour-v1:tour-owner:test', '1'); mount(); await tick(); await tick(50);
  expect(screen.getByRole('dialog')).toHaveTextContent('Your next stop');
});
it('waits for lazy targets and never draws a highlight on a missing control', async () => {
  render(<GuidedTour scope="missing" steps={[{...steps[0], target: '#missing'}, steps[1]]}/>); await tick();
  expect(screen.getByRole('dialog')).toHaveTextContent('Finding your next stop');
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  const el = document.createElement('button'); el.id = 'missing'; document.body.append(el); await tick(50);
  expect(screen.getByRole('dialog')).toHaveTextContent('Your first stop'); el.remove();
});
it('ignores controls inside hidden views even when multiple selectors match', () => {
  const { container } = render(<><div hidden><button className="same">Hidden</button></div><button className="same">Visible</button></>);
  expect(visibleTarget('.same')?.textContent).toBe('Visible'); container.remove();
});
it('keeps the coachmark within narrow screens and flips above bottom controls', () => {
  const narrow = tourPosition({x: 360,y: 80,width: 20,height: 30}, 340, 250, 390, 844);
  expect(narrow.left).toBe(38); expect(narrow.top).toBe(126);
  const bottom = tourPosition({x: 40,y: 750,width: 120,height: 40}, 340, 250, 390, 844);
  expect(bottom.top).toBe(484);
});

it('never activates the highlighted control and restores background access when unmounted', async () => {
  const click = vi.fn();
  const {container, unmount} = render(<><button id="tour-target" onClick={click}>Target</button><button id="tour-second">Second</button><GuidedTour scope="actions" steps={steps}/></>);
  await tick(); await tick(50);
  expect(container.inert).toBe(true);
  fireEvent.click(screen.getByRole('button', {name: 'Next'})); await tick(50);
  expect(click).not.toHaveBeenCalled();
  unmount(); expect(container.inert).toBeFalsy(); expect(document.documentElement.style.overflow).toBe('');
});
it('moves past an unavailable target instead of leaving the user stuck', async () => {
  render(<><button id="tour-second">Second</button><GuidedTour scope="missing-next" steps={steps}/></>);
  await tick(); await tick(5200); await tick(50);
  expect(screen.getByRole('dialog')).toHaveTextContent('Your next stop');
});

it('allows only one guide at a time and does not interrupt an open editor', async () => {
  const {unmount} = render(<><button id="tour-target">Target</button><GuidedTour scope="one" steps={steps}/><GuidedTour scope="two" steps={steps}/></>);
  await tick(); await tick(50); expect(screen.getAllByRole('dialog')).toHaveLength(1); unmount();
  render(<><div role="dialog">Profile editor</div><GuidedTour scope="editor" steps={steps}/></>);
  await tick(); expect(screen.getAllByRole('dialog')).toHaveLength(1); expect(screen.queryByText('Your first stop')).toBeNull();
});
