import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { LanguageProvider, useLanguage } from './LanguageContext';
import { beginLanguageTransition, reloadForLanguage } from '@/lib/googlePageTranslation';

vi.mock('@/lib/googlePageTranslation', () => ({ beginLanguageTransition: vi.fn(), reloadForLanguage: vi.fn() }));

function Switcher() {
  const { language, setLanguage, t } = useLanguage();
  return <>
    <span data-testid="language">{language}</span>
    <span data-testid="label">{t('dashboard')}</span>
    <button onClick={() => setLanguage('hi')}>हिन्दी</button>
  </>;
}

beforeEach(() => { localStorage.clear(); vi.clearAllMocks(); });
afterEach(() => { vi.restoreAllMocks(); });

it('uses Google page translation after covering the language reload, without a Sarvam UI request', async () => {
  const fetchSpy = vi.spyOn(globalThis, 'fetch');
  render(<LanguageProvider><Switcher /></LanguageProvider>);
  fireEvent.click(screen.getByRole('button', { name: 'हिन्दी' }));
  expect(beginLanguageTransition).toHaveBeenCalledWith('hi');
  await waitFor(() => expect(reloadForLanguage).toHaveBeenCalledOnce());
  expect(screen.getByTestId('language')).toHaveTextContent('hi');
  expect(screen.getByTestId('label')).toHaveTextContent('Dashboard');
  expect(document.cookie).toContain('googtrans=/en/hi');
  expect(fetchSpy).not.toHaveBeenCalled();
});
