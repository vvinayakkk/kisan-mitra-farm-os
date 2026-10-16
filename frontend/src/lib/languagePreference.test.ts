import { beforeEach, expect, it } from 'vitest';
import { applyLanguagePreference, normalizeLanguage, preferredLanguage } from './languagePreference';
import { voiceLanguageCode } from '@/hooks/useVoiceInput';
import { voiceStatus } from './voiceStatus';
beforeEach(()=>localStorage.clear());
it('normalizes profile and provider locale aliases without silently switching language',()=>{
  expect(normalizeLanguage('te-IN')).toBe('te'); expect(normalizeLanguage('od-IN')).toBe('or');
  applyLanguagePreference('od-IN'); expect(preferredLanguage()).toBe('or'); expect(voiceLanguageCode()).toBe('od-IN');
  applyLanguagePreference('ur'); expect(voiceLanguageCode()).toBe('ur-IN');
});
it('profile updates inform the interface, chat and voice through one event',()=>{
  let detail:unknown; window.addEventListener('mitra-language-change',(event)=>{detail=(event as CustomEvent).detail;},{once:true});
  applyLanguagePreference('te'); expect(detail).toEqual({language:'te',reload:false}); expect(preferredLanguage()).toBe('te'); expect(voiceLanguageCode()).toBe('te-IN');
  expect(voiceStatus('speaking')).toBe('మిత్ర మాట్లాడుతోంది');
});
