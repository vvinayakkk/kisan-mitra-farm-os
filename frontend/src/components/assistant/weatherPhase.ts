type SolarSeries = Record<string, Array<string | number | null>>;

function localParts(now: Date, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(now);
  const value = (type: string) => parts.find(part => part.type === type)?.value || "00";
  return {
    date: `${value("year")}-${value("month")}-${value("day")}`,
    minute: Number(value("hour")) * 60 + Number(value("minute")),
  };
}

function solarMinute(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const match = /T(\d{2}):(\d{2})/.exec(value);
  return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}

export function weatherPhase(now: Date, timezone: string, daily?: SolarSeries, providerIsDay?: unknown): "day" | "night" {
  try {
    const local = localParts(now, timezone);
    const index = daily?.time?.findIndex(value => value === local.date) ?? -1;
    if (index >= 0) {
      const sunrise = solarMinute(daily?.sunrise?.[index]);
      const sunset = solarMinute(daily?.sunset?.[index]);
      if (sunrise !== null && sunset !== null) {
        return local.minute >= sunrise && local.minute < sunset ? "day" : "night";
      }
    }
  } catch {                                                                      }
  return providerIsDay === 0 ? "night" : "day";
}
