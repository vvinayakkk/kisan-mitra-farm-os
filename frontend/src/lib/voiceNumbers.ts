export type DictationUnit = "number" | "rupees" | "hectares" | "acres";
interface NumberOptions {
  unit?: DictationUnit;
  min?: number;
  max?: number;
}
const ONES: Record<string, number> = {
  zero: 0,
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
  eleven: 11,
  twelve: 12,
  thirteen: 13,
  fourteen: 14,
  fifteen: 15,
  sixteen: 16,
  seventeen: 17,
  eighteen: 18,
  nineteen: 19,
};
const TENS: Record<string, number> = {
  twenty: 20,
  thirty: 30,
  forty: 40,
  fifty: 50,
  sixty: 60,
  seventy: 70,
  eighty: 80,
  ninety: 90,
};
const SCALES: Record<string, number> = {
  thousand: 1000,
  lakh: 100000,
  lakhs: 100000,
  crore: 10000000,
  crores: 10000000,
  million: 1000000,
};
function fail(): never {
  throw new Error(
    "Please say one clear number, or type it. Check the number and unit before saving.",
  );
}
function belowHundred(words: string[]): number {
  if (words.length === 1 && words[0] in ONES) return ONES[words[0]];
  if (words.length === 1 && words[0] in TENS) return TENS[words[0]];
  if (
    words.length === 2 &&
    words[0] in TENS &&
    (ONES[words[1]] ?? 0) > 0 &&
    ONES[words[1]] < 10
  )
    return TENS[words[0]] + ONES[words[1]];
  return fail();
}
function small(words: string[]): number {
  const at = words.indexOf("hundred");
  if (at < 0) return belowHundred(words);
  if (
    at !== 1 ||
    !(words[0] in ONES) ||
    ONES[words[0]] < 1 ||
    ONES[words[0]] > 9 ||
    words.lastIndexOf("hundred") !== at
  )
    return fail();
  let tail = words.slice(2);
  if (tail[0] === "and") tail = tail.slice(1);
  return ONES[words[0]] * 100 + (tail.length ? belowHundred(tail) : 0);
}
function whole(words: string[]): number {
  if (!words.length) return fail();
  let result = 0,
    previousScale = Infinity,
    group: string[] = [];
  for (const word of words) {
    if (word in SCALES) {
      const scale = SCALES[word];
      if (!group.length || scale >= previousScale) return fail();
      result += small(group) * scale;
      group = [];
      previousScale = scale;
    } else group.push(word);
  }
  if (group.length) {
    if (group[0] === "and" && result) group.shift();
    if (!group.length) return fail();
    result += small(group);
  }
  return result;
}
/** Strict English number phrases and Latin/Devanagari numerals; never infers or converts units. */
export function parseSpokenNumber(
  input: string,
  {
    unit = "number",
    min = 0,
    max = Number.MAX_SAFE_INTEGER,
  }: NumberOptions = {},
): number {
  let text = input
    .trim()
    .toLowerCase()
    .replace(/[,.!?।]+$/, "")
    .trim()
    .replace(/[०-९]/g, (digit) => String("०१२३४५६७८९".indexOf(digit)))
    .replace(/-/g, " ")
    .replace(/\s+/g, " ");
  const suffix = text.match(/\s*(rupees?|rs\.?|inr|₹|hectares?|ha|acres?)\s*$/);
  let spokenUnit: DictationUnit = "number";
  if (suffix) {
    spokenUnit = /^(rupee|rs|inr|₹)/.test(suffix[1])
      ? "rupees"
      : /^(hectare|ha)/.test(suffix[1])
        ? "hectares"
        : "acres";
    text = text.slice(0, suffix.index).trim();
  }
  if (/^(?:₹|inr|rs\.?)\s*/.test(text)) {
    if (spokenUnit !== "number" && spokenUnit !== "rupees") return fail();
    spokenUnit = "rupees";
    text = text.replace(/^(?:₹|inr|rs\.?)\s*/, "");
  }
  if (spokenUnit !== "number" && spokenUnit !== unit)
    throw new Error(
      `This field uses ${unit}. Please check the spoken unit; no conversion was applied.`,
    );
  let value: number;
  if (
    /^(?:\d+(?:\.\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{1,2}(?:,\d{2})*,\d{3}(?:\.\d+)?)$/.test(
      text,
    )
  )
    value = Number(text.replace(/,/g, ""));
  else {
    const parts = text.split(" point ");
    if (parts.length > 2 || !parts[0]) return fail();
    value = whole(parts[0].split(" "));
    if (parts.length === 2) {
      const digits = parts[1].split(" ");
      if (
        !digits.length ||
        digits.length > 8 ||
        digits.some((word) => !(word in ONES) || ONES[word] > 9)
      )
        return fail();
      value += Number("0." + digits.map((word) => ONES[word]).join(""));
    }
  }
  if (!Number.isFinite(value) || value < min || value > max)
    throw new Error(
      `Enter a number between ${min} and ${max}. Nothing was changed.`,
    );
  return value;
}
/** ISO dates only: relative or ambiguous spoken dates must use the date picker. */
export function parseSpokenDate(text: string): string {
  const clean = text
    .trim()
    .replace(/[०-९]/g, (digit) => String("०१२३४५६७८९".indexOf(digit)));
  if (!/^\d{4}-\d{2}-\d{2}$/.test(clean))
    throw new Error(
      "Use the date picker, or say an exact date in year-month-day format.",
    );
  const date = new Date(clean + "T00:00:00Z");
  if (
    !Number.isFinite(date.valueOf()) ||
    date.toISOString().slice(0, 10) !== clean
  )
    throw new Error("That date is not valid. Please use the date picker.");
  return clean;
}
