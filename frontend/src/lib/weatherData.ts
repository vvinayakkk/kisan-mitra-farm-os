import { apiFetch } from "@/lib/apiClient";
// Weather data integration with FastAPI backend
// Connects to the configured backend API at /api/sensors/

const HOST_URL = import.meta.env.VITE_API_URL || '';
// Ensure API_BASE always includes the path correctly
const API_BASE = HOST_URL.endsWith('/') 
  ? `${HOST_URL}api/sensors` 
  : `${HOST_URL}/api/sensors`;
const STATION_ID = import.meta.env.VITE_STATION_ID || 'WS01';

export interface WeatherData {
  timestamp: Date;
  temperature: number;
  humidity: number;
  pressure: number;
  windSpeed: number;
  windDirection: string;
  rainfall: number;
  uvIndex: number;
  lightIntensity: number;
  airQualityPM25: number;
  airQualityPM10: number;
  soilTemperature: number;
  soilMoisture: number;
}

export interface SystemHealth {
  batteryVoltage: number;
  batteryStatus: 'healthy' | 'low' | 'critical' | 'unknown';
  solarCharging: boolean;
  loraLinkActive: boolean;
  edgeSystemRunning: boolean;
  sensorNodeOnline: boolean;
  lastUpdateSeconds: number;
}

export interface Alert {
  id: string;
  type: 'warning' | 'critical' | 'info';
  message: string;
  messageKey: string;
  timestamp: Date;
}

export type ParameterStatus = 'normal' | 'elevated' | 'critical' | 'unknown';

export function getParameterStatus(param: string, value: number): ParameterStatus {
  if (!Number.isFinite(value)) return 'unknown';
  switch (param) {
    case 'temperature':
      if (value > 40 || value < 5) return 'critical';
      if (value > 35 || value < 10) return 'elevated';
      return 'normal';
    case 'humidity':
      if (value > 95 || value < 20) return 'critical';
      if (value > 85 || value < 30) return 'elevated';
      return 'normal';
    case 'windSpeed':
      if (value > 50) return 'critical';
      if (value > 30) return 'elevated';
      return 'normal';
    case 'uvIndex':
      if (value >= 11) return 'critical';
      if (value >= 8) return 'elevated';
      return 'normal';
    case 'airQualityPM25':
      if (value > 150) return 'critical';
      if (value > 50) return 'elevated';
      return 'normal';
    case 'soilMoisture':
      if (value < 20 || value > 90) return 'critical';
      if (value < 30 || value > 80) return 'elevated';
      return 'normal';
    default:
      return 'normal';
  }
}

// Fetch current data from FastAPI backend
export async function getCurrentWeatherData(): Promise<WeatherData> {
  try {
    const response = await apiFetch(`${API_BASE}/latest/${STATION_ID}`);
    if (!response.ok) throw new Error('Failed to fetch weather data');
    const data = await response.json();
    if (data.available === false || !data.timestamp) throw new Error("Station has no valid readings.");

    // Accept both camelCase and snake_case keys (backend returns camelCase)
    const result = {
      timestamp: new Date(data.timestamp),
      temperature: data.temperature ?? NaN,
      humidity: data.humidity ?? NaN,
      pressure: data.pressure ?? NaN,
      windSpeed: data.windSpeed ?? data.wind_speed ?? NaN,
      windDirection: typeof (data.windDirection ?? data.wind_direction) === 'string' ? data.windDirection ?? data.wind_direction : '—',
      rainfall: data.rainfall ?? NaN,
      uvIndex: data.uvIndex ?? data.uv_index ?? NaN,
      lightIntensity: data.lightIntensity ?? data.lux ?? NaN,
      airQualityPM25: data.airQualityPM25 ?? data.pm25 ?? NaN,
      airQualityPM10: data.airQualityPM10 ?? data.pm10 ?? NaN,
      soilTemperature: data.soilTemperature ?? data.soil_temperature ?? NaN,
      soilMoisture: data.soilMoisture ?? data.soil_moisture ?? NaN,
    };
    return result;
  } catch (error) {
    console.error(' Error fetching weather data:', error);
    throw new Error('Station data is unavailable. No readings were substituted.');
  }
}

// Fetch system health from backend
export async function getSystemHealth(): Promise<SystemHealth> {
  try {
    const response = await apiFetch(`${API_BASE}/latest/${STATION_ID}`);
    if (!response.ok) throw new Error('Failed to fetch system health');
    
    const data = await response.json();
    const battery = data.batteryVoltage ?? data.battery_voltage ?? NaN;
    const solar = data.solarVoltage ?? data.solar_voltage ?? 0;
    
    // Calculate battery status based on voltage
    let batteryStatus: SystemHealth['batteryStatus'] = Number.isFinite(battery) ? 'healthy' : 'unknown';
    if (battery < 3.0) batteryStatus = 'critical';
    else if (battery < 3.5) batteryStatus = 'low';
    
    // Calculate last update time
    const lastUpdate = new Date(data.timestamp);
    const now = new Date();
    const lastUpdateSeconds = Math.floor((now.getTime() - lastUpdate.getTime()) / 1000);
    
    return {
      batteryVoltage: battery,
      batteryStatus,
      solarCharging: solar > 0,
      loraLinkActive: data.loraLinkActive === true || data.lora_link_active === true,
      edgeSystemRunning: data.edgeSystemRunning === true || data.edge_system_running === true,
      sensorNodeOnline: lastUpdateSeconds <= 300,
      lastUpdateSeconds: Math.max(0, lastUpdateSeconds), // Keep the display update time low/reasonable
    };
  } catch (error) {
    console.error('Error fetching system health:', error);
    throw new Error('Station health is unavailable.');
  }
}

// Fetch recent alerts (mock for now, can integrate with backend)
export async function getRecentAlerts(): Promise<Alert[]> {
  try {
    const response = await apiFetch(`${HOST_URL}/api/recent-alerts`);
    if (!response.ok) throw new Error('Alerts unavailable');
    const data = await response.json();
    return (data.alerts ?? []).map((row: { id: string; severity?: string; message: string; timestamp: string }) => ({
      id: row.id, type: row.severity === 'critical' ? 'critical' : row.severity === 'warning' ? 'warning' : 'info',
      message: row.message, messageKey: '', timestamp: new Date(row.timestamp),
    }));
  } catch (error) {
    console.error('Error fetching alerts:', error);
    return [];
  }
}

// Fetch historical data from backend
export async function getHistoricalData(hours: number = 24): Promise<{ time: string; temperature: number; humidity: number; rainfall: number }[]> {
  try {
    const limit = Math.ceil(hours * 30); // ~720 records for 24 hours (every 2 minutes)
    const url = `${API_BASE}/history/${STATION_ID}?limit=${limit}&hours=${hours}`;
    
    const response = await apiFetch(url);
    
    if (!response.ok) {
      const text = await response.text();
      console.error(' Response not OK:', text);
      throw new Error(`HTTP ${response.status}: ${text}`);
    }
    
    const result = await response.json();
    
    const data = result.data || [];
    
    if (!data || data.length === 0) {
      console.warn('️ No data returned from API');
      return [];
    }
    
    // Transform backend data to chart format
    const transformed = data.map((record: any) => {
      try {
        // Handle timestamp like "2026-02-28 15:03:36" (with space instead of T)
        let formattedTimestamp = record.timestamp;
        if (formattedTimestamp && formattedTimestamp.includes(' ')) {
          // Replace space with T for ISO format: "2026-02-28 15:03:36" -> "2026-02-28T15:03:36"
          formattedTimestamp = formattedTimestamp.replace(' ', 'T');
        }
        
        const time = new Date(formattedTimestamp);
        if (isNaN(time.getTime())) {
          console.warn('Invalid timestamp:', record.timestamp);
          return null;
        }
        
        return {
          time: `${time.getHours().toString().padStart(2, '0')}:${time.getMinutes().toString().padStart(2, '0')}`,
          temperature: Math.round((record.temperature || 0) * 10) / 10,
          humidity: Math.round(record.humidity || 0),
          rainfall: Math.round((record.rainfall || 0) * 10) / 10,
        };
      } catch (e) {
        console.error('Error transforming record:', record, e);
        return null;
      }
    }).filter(Boolean).reverse(); // Remove null entries and show chronological order
    
    if (transformed.length > 0) {
    }
    
    return transformed;
  } catch (error) {
    console.error(' Error fetching historical data:', error);
    
    return [];
  }
}
