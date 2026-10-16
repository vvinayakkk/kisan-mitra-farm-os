import { expect, it } from 'vitest';
import { parseSpokenDate, parseSpokenNumber } from './voiceNumbers';
it('parses reviewed digits, Indian grouping, decimals and supported English phrases', () => {
  for (const [input, value] of [['2500', 2500], ['2,500.50', 2500.5], ['2,50,000', 250000], ['two thousand five hundred', 2500], ['two thousand five hundred and fifty', 2550], ['one lakh twenty five thousand', 125000], ['two point five', 2.5], ['२५००.५०', 2500.5], ['forty-two', 42], ['two thousand five hundred.', 2500], ['2,500.50।',2500.5]] as const) expect(parseSpokenNumber(input)).toBe(value);
  expect(parseSpokenNumber('₹2,500.50', { unit: 'rupees' })).toBe(2500.5);
  expect(parseSpokenNumber('two thousand five hundred rupees', { unit: 'rupees' })).toBe(2500);
  expect(parseSpokenNumber('two thousand five hundred rupees.', {unit:'rupees'})).toBe(2500);
  expect(parseSpokenNumber('2.5 ha', { unit: 'hectares' })).toBe(2.5);
});
it('refuses ambiguous words, corrupted numbers, unit changes, ranges and unsupported speech', () => {
  for (const input of ['one two', 'five or six', '2,50.5', 'two thousand thousand', 'twenty hundred', 'ढाई', 'about two', 'two point twenty', '-5', '1e4', '', 'five to ten']) expect(() => parseSpokenNumber(input)).toThrow();
  expect(() => parseSpokenNumber('5 acres', { unit: 'hectares' })).toThrow('no conversion');
  expect(() => parseSpokenNumber('5', { max: 4 })).toThrow('Nothing was changed');
});
it('accepts exact valid dates and refuses guessing', () => {
  expect(parseSpokenDate('2026-10-14')).toBe('2026-10-14');
  expect(parseSpokenDate('२०२६-१०-१४')).toBe('2026-10-14');
  for (const date of ['tomorrow', '14/10/26', '2026-02-30', '2026-13-01']) expect(() => parseSpokenDate(date)).toThrow();
});
