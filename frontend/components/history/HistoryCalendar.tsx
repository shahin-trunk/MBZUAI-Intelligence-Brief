"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface BriefDateEntry {
  brief_date: string;
  item_count: number;
  generated_at: string;
  top_headlines: string[];
}

interface HistoryCalendarProps {
  entries: BriefDateEntry[];
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatTime(isoStr: string): string {
  if (!isoStr) return "";
  const date = new Date(isoStr);
  return date.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Dubai",
  }) + " GST";
}

function getMonthLabel(date: Date): string {
  return date.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

function isSameMonth(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth();
}

function toDateKey(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

/* ------------------------------------------------------------------ */
/*  Component                                                         */
/* ------------------------------------------------------------------ */

export function HistoryCalendar({ entries }: HistoryCalendarProps) {
  const today = new Date();
  const [currentMonth, setCurrentMonth] = useState(
    new Date(today.getFullYear(), today.getMonth(), 1)
  );

  // Set of date strings that have briefs
  const availableDates = new Set(entries.map((e) => e.brief_date));

  /* ---- Calendar grid ---- */
  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();
  const firstDay = new Date(year, month, 1);
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Monday = 0, Sunday = 6
  const startWeekday = (firstDay.getDay() + 6) % 7;

  const calendarCells: (number | null)[] = [];
  for (let i = 0; i < startWeekday; i++) {
    calendarCells.push(null);
  }
  for (let d = 1; d <= daysInMonth; d++) {
    calendarCells.push(d);
  }

  // Pad the end to fill the last row
  while (calendarCells.length % 7 !== 0) {
    calendarCells.push(null);
  }

  const todayKey = toDateKey(today.getFullYear(), today.getMonth(), today.getDate());

  /* ---- Month navigation ---- */
  function prevMonth() {
    setCurrentMonth(new Date(year, month - 1, 1));
  }

  function nextMonth() {
    setCurrentMonth(new Date(year, month + 1, 1));
  }

  function goToToday() {
    setCurrentMonth(new Date(today.getFullYear(), today.getMonth(), 1));
  }

  /* ---- Entries for current month ---- */
  const monthEntries = entries.filter((e) => {
    const d = new Date(e.brief_date + "T00:00:00");
    return isSameMonth(d, currentMonth);
  });

  return (
    <div className="space-y-8">
      {/* Calendar */}
      <div className="rounded-sm border border-border-primary bg-bg-secondary p-4">
        {/* Month header */}
        <div className="flex items-center justify-between">
          <button
            onClick={prevMonth}
            className="rounded p-1 text-text-muted transition-colors hover:bg-bg-tertiary hover:text-text-primary"
            aria-label="Previous month"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          <div className="flex items-center gap-3">
            <span className="font-serif text-lg text-text-bright">
              {getMonthLabel(currentMonth)}
            </span>
            {!isSameMonth(currentMonth, today) && (
              <button
                onClick={goToToday}
                className="font-mono text-[12px] text-accent-primary hover:underline"
              >
                Today
              </button>
            )}
          </div>

          <button
            onClick={nextMonth}
            className="rounded p-1 text-text-muted transition-colors hover:bg-bg-tertiary hover:text-text-primary"
            aria-label="Next month"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        {/* Weekday headers */}
        <div className="mt-4 grid grid-cols-7 gap-px">
          {WEEKDAYS.map((day) => (
            <div
              key={day}
              className="py-1 text-center font-mono text-[12px] text-text-muted"
            >
              {day}
            </div>
          ))}
        </div>

        {/* Day cells */}
        <div className="mt-1 grid grid-cols-7 gap-px">
          {calendarCells.map((day, idx) => {
            if (day === null) {
              return <div key={`empty-${idx}`} className="h-12" />;
            }

            const dateKey = toDateKey(year, month, day);
            const hasBrief = availableDates.has(dateKey);
            const isToday = dateKey === todayKey;

            const cellContent = (
              <div
                className={cn(
                  "relative flex h-12 w-full flex-col items-center justify-center rounded-sm transition-colors",
                  hasBrief
                    ? "cursor-pointer text-text-primary hover:bg-bg-tertiary"
                    : "text-text-muted/30",
                  isToday && "ring-1 ring-accent-primary"
                )}
              >
                <span className="font-mono text-xs">{day}</span>
                {hasBrief && (
                  <span className="absolute bottom-1.5 h-1.5 w-1.5 rounded-full bg-sig-high" />
                )}
              </div>
            );

            if (hasBrief) {
              return (
                <Link key={dateKey} href={`/brief/${dateKey}`}>
                  {cellContent}
                </Link>
              );
            }

            return (
              <div key={dateKey}>
                {cellContent}
              </div>
            );
          })}
        </div>
      </div>

      {/* Brief preview list for current month */}
      <div>
        <h2 className="font-serif text-lg text-text-bright">
          {isSameMonth(currentMonth, today)
            ? "Recent Briefs"
            : getMonthLabel(currentMonth)}
        </h2>

        {monthEntries.length === 0 ? (
          <p className="mt-3 font-mono text-xs text-text-muted">
            No briefs available for this month.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {monthEntries.map((entry) => (
              <Link
                key={entry.brief_date}
                href={`/brief/${entry.brief_date}`}
                className="block rounded-sm border border-border-primary bg-bg-secondary p-4 transition-colors hover:bg-bg-tertiary"
              >
                <div className="flex items-baseline justify-between">
                  <span className="font-serif text-sm text-text-bright">
                    {formatDate(entry.brief_date)}
                  </span>
                  <span className="font-mono text-[12px] text-text-muted">
                    {entry.item_count} items
                    {entry.generated_at ? ` \u00B7 ${formatTime(entry.generated_at)}` : ""}
                  </span>
                </div>

                {entry.top_headlines.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {entry.top_headlines.map((headline, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 font-serif text-xs text-text-secondary"
                      >
                        <span className="mt-1.5 h-1 w-1 flex-shrink-0 rounded-full bg-text-muted/40" />
                        <span className="line-clamp-1">{headline}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
