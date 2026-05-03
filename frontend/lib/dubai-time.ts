const DUBAI_TIME_ZONE = "Asia/Dubai";
const DAY_MS = 24 * 60 * 60 * 1000;

const dubaiDateFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: DUBAI_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

function getDubaiDateParts(date: Date): { year: string; month: string; day: string } {
  const parts = dubaiDateFormatter.formatToParts(date);

  return {
    year: parts.find((part) => part.type === "year")?.value ?? "1970",
    month: parts.find((part) => part.type === "month")?.value ?? "01",
    day: parts.find((part) => part.type === "day")?.value ?? "01",
  };
}

export function getDubaiDateString(date: Date = new Date()): string {
  const { year, month, day } = getDubaiDateParts(date);
  return `${year}-${month}-${day}`;
}

export function getDubaiDateDaysAgoString(
  daysAgo: number,
  now: Date = new Date()
): string {
  return getDubaiDateString(new Date(now.getTime() - daysAgo * DAY_MS));
}

export function getDubaiMonthStartUtcIso(date: Date = new Date()): string {
  const { year, month } = getDubaiDateParts(date);
  return new Date(`${year}-${month}-01T00:00:00+04:00`).toISOString();
}

export function getDubaiDayStartUtcIso(date: Date = new Date()): string {
  const { year, month, day } = getDubaiDateParts(date);
  return new Date(`${year}-${month}-${day}T00:00:00+04:00`).toISOString();
}
