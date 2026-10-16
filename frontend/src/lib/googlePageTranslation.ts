import { preferredLanguage, type Language } from './languagePreference';

const marker = 'mitra-language-transition';

export function beginLanguageTransition(language: Language) {
  try { sessionStorage.setItem(marker, language); } catch { /* The cover still works for this page. */ }
  document.documentElement.classList.add('language-transitioning');
}

export function reloadForLanguage() { window.location.reload(); }

/** The widget must start after React has rendered actual page text. */
export function bootGooglePageTranslation() {
  const root = document.getElementById('root');
  if (!root) return;
  const language = preferredLanguage();
  let pending = false;
  try { pending = sessionStorage.getItem(marker) === language; } catch { /* No stored transition. */ }
  if (!pending) document.documentElement.classList.remove('language-transitioning');

  const finish = () => {
    try { sessionStorage.removeItem(marker); } catch { /* Ignore storage restrictions. */ }
    document.documentElement.classList.remove('language-transitioning');
  };
  let ready = false;
  const injectWidget = (attempt = 0) => {
    if (document.querySelector('.goog-te-gadget-simple')) return;
    const prior = document.getElementById('google-translate-script');
    if (prior) prior.remove();
    const script = document.createElement('script');
    script.id = 'google-translate-script';
    script.src = `https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit${attempt ? `&retry=${attempt}` : ''}`;
    script.async = true;
    script.onerror = () => {
      document.documentElement.dataset.googleTranslateStatus = 'retrying';
      if (attempt < 2) window.setTimeout(() => injectWidget(attempt + 1), 600 * (attempt + 1));
    };
    script.onload = () => {
      document.documentElement.dataset.googleTranslateStatus = 'loaded';
      if (attempt < 2) window.setTimeout(() => {
        if (!document.querySelector('.goog-te-gadget-simple')) injectWidget(attempt + 1);
      }, 1500);
    };
    document.body.appendChild(script);
  };
  const loadWidget = () => {
    if (ready || !root.textContent || root.textContent.trim().length < 80) return;
    ready = true;
    contentObserver.disconnect();
    if (language === 'en') {
      if (pending) requestAnimationFrame(() => requestAnimationFrame(finish));
      return;
    }
    injectWidget();
  };
  const contentObserver = new MutationObserver(loadWidget);
  contentObserver.observe(root, { childList: true, subtree: true, characterData: true });
  loadWidget();

  if (pending && language !== 'en') {
    let settleTimer = 0;
    const translationObserver = new MutationObserver(() => {
      if (!document.documentElement.classList.contains('translated-ltr') && !document.body.classList.contains('translated-ltr')) return;
      window.clearTimeout(settleTimer);
      settleTimer = window.setTimeout(() => {
        translationObserver.disconnect();
        finish();
      }, 350);
    });
    translationObserver.observe(document.documentElement, { attributes: true, childList: true, characterData: true, subtree: true });
    window.setTimeout(() => { translationObserver.disconnect(); finish(); }, 20000);
  }
}
