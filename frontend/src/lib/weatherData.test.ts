import { beforeEach, expect, it, vi } from 'vitest';
import { apiFetch } from './apiClient';
import { formatWindDirection, getCurrentWeatherData, getHistoricalData, getSystemHealth } from './weatherData';
vi.mock('./apiClient', () => ({apiFetch: vi.fn()}));
beforeEach(() => vi.mocked(apiFetch).mockReset());
it('accepts canonical wind degrees including north at zero', async () => {
  vi.mocked(apiFetch).mockResolvedValue(Response.json({available:true,timestamp:new Date().toISOString(),windDirection:0,temperature:0,humidity:0}));
  const result=await getCurrentWeatherData();
  expect(result.windDirection).toBe('N'); expect(result.temperature).toBe(0);
  expect(formatWindDirection(225)).toBe('SW');
});
it('does not mark a station online when no packet exists', async () => {
  vi.mocked(apiFetch).mockResolvedValue(Response.json({available:false}));
  expect(await getSystemHealth()).toMatchObject({sensorNodeOnline:false,lastUpdateSeconds:0,batteryStatus:'unknown'});
});
it('honors the history contract limit and preserves missing measurements', async () => {
  vi.mocked(apiFetch).mockResolvedValue(Response.json({data:[{timestamp:'2026-10-18T00:00:00Z',temperature:null,humidity:0,rainfall:null}]}));
  const result=await getHistoricalData(720);
  expect(String(vi.mocked(apiFetch).mock.calls[0][0])).toContain('limit=2000&hours=720');
  expect(result[0].temperature).toBeNaN(); expect(result[0].humidity).toBe(0); expect(result[0].rainfall).toBeNaN();
});
it('surfaces history outages rather than treating them as an empty farm', async () => {
  vi.mocked(apiFetch).mockResolvedValue(Response.json({detail:'Unavailable'},{status:503}));
  await expect(getHistoricalData()).rejects.toThrow('HTTP 503');
});
