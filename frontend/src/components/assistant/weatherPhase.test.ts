import { expect, test } from "vitest";
import { weatherPhase } from "./weatherPhase";

const solar = {
  time: ["2026-10-16"],
  sunrise: ["2026-10-16T06:03"],
  sunset: ["2026-10-16T17:48"],
};

test("changes colour at the selected place's sunrise and sunset", () => {
  expect(weatherPhase(new Date("2026-10-16T00:32:00Z"), "Asia/Kolkata", solar, 1)).toBe("night");
  expect(weatherPhase(new Date("2026-10-16T00:33:00Z"), "Asia/Kolkata", solar, 0)).toBe("day");
  expect(weatherPhase(new Date("2026-10-16T12:18:00Z"), "Asia/Kolkata", solar, 1)).toBe("night");
});

test("uses the selected city's timezone, then provider data when solar times are unavailable", () => {
  expect(weatherPhase(new Date("2026-10-16T01:00:00Z"), "Asia/Kolkata", solar)).toBe("day");
  const newYorkSolar = { time: ["2026-10-15"], sunrise: ["2026-10-15T06:03"], sunset: ["2026-10-15T17:48"] };
  expect(weatherPhase(new Date("2026-10-16T01:00:00Z"), "America/New_York", newYorkSolar)).toBe("night");
  expect(weatherPhase(new Date("2026-10-16T01:00:00Z"), "America/New_York", undefined, 0)).toBe("night");
});
