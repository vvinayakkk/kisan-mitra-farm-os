/** App/profile codes use ISO 'or'; the speech provider uses 'od-IN'. */
export const APP_LANGUAGES = [
  ['en', 'English'], ['hi', 'हिन्दी'], ['te', 'తెలుగు'], ['ta', 'தமிழ்'],
  ['mr', 'मराठी'], ['gu', 'ગુજરાતી'], ['bn', 'বাংলা'], ['kn', 'ಕನ್ನಡ'],
  ['ml', 'മലയാളം'], ['pa', 'ਪੰਜਾਬੀ'], ['or', 'ଓଡ଼ିଆ'],
  ['as', 'অসমীয়া'], ['ur', 'اردو'],
] as const;
export type Language = typeof APP_LANGUAGES[number][0] | 'ne' | 'sa' | 'ks' | 'kok' | 'mai' | 'doi' | 'mni' | 'sat' | 'sd' | 'bo' | 'brx';
const codes = new Set<string>([...APP_LANGUAGES.map(([code]) => code), 'ne', 'sa', 'ks', 'kok', 'mai', 'doi', 'mni', 'sat', 'sd', 'bo', 'brx']);
export function normalizeLanguage(value?: string | null): Language | undefined {
  const prefix = value?.toLowerCase().replace('_', '-').split('-')[0];
  const code = prefix === 'od' ? 'or' : prefix;
  return code && codes.has(code) ? code as Language : undefined;
}
let memory: Language | undefined;
export function preferredLanguage(): Language {
  try { return normalizeLanguage(localStorage.getItem('app_language')) || memory || 'en'; }
  catch { return memory || 'en'; }
}
export function applyLanguagePreference(value: string, reload = false) {
  const language = normalizeLanguage(value);
  if (!language) return;
  const changed = preferredLanguage() !== language;
  memory = language;
  try { localStorage.setItem('app_language', language); } catch { /* In-memory preference remains available. */ }
  document.cookie = `googtrans=${language === 'en' ? '' : `/en/${language}`}; path=/;`;
  document.documentElement.lang = language;
  window.dispatchEvent(new CustomEvent('mitra-language-change', { detail: { language, reload: reload && changed } }));
}
