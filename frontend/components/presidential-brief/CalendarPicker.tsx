"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { hapticSelection } from "@/lib/presidential-brief/haptics";
import { cn } from "@/lib/utils";

interface CalendarPickerProps {
  visible: boolean;
  currentDate: string;
  availableDates: string[];
  onSelectDate: (date: string) => void;
  onClose: () => void;
  /** `sheet`: no outer wrapper — parent dialog supplies padding/surface. `inline`: wrapped block for page flow. */
  placement?: "inline" | "sheet";
}

const DAYS_OF_WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function formatMonthYear(year: number, month: number): string {
  return new Date(year, month, 1).toLocaleString("en-US", {
    month: "long",
    year: "numeric",
  });
}

function toDateStr(year: number, month: number, day: number): string {
  const mm = String(month + 1).padStart(2, "0");
  const dd = String(day).padStart(2, "0");
  return `${year}-${mm}-${dd}`;
}

export default function CalendarPicker({
  visible,
  currentDate,
  availableDates,
  onSelectDate,
  onClose,
  placement = "inline",
}: CalendarPickerProps) {
  const parsedCurrent = currentDate ? new Date(currentDate + "T00:00:00") : new Date();

  const [viewYear, setViewYear] = useState(parsedCurrent.getFullYear());
  const [viewMonth, setViewMonth] = useState(parsedCurrent.getMonth());
  /** Drives slide-in direction when month changes (next = from right, prev = from left). */
  const [monthNav, setMonthNav] = useState<"next" | "prev" | null>(null);

  if (!visible) return null;

  const availableSet = new Set(availableDates);
  const todayStr = new Date().toISOString().slice(0, 10);

  // First day of view month
  const firstDay = new Date(viewYear, viewMonth, 1).getDay();
  // Days in view month
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

  const handlePrevMonth = () => {
    setMonthNav("prev");
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear((y) => y - 1);
    } else {
      setViewMonth((m) => m - 1);
    }
  };

  const handleNextMonth = () => {
    setMonthNav("next");
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear((y) => y + 1);
    } else {
      setViewMonth((m) => m + 1);
    }
  };

  const handleDayTap = async (dateStr: string) => {
    await hapticSelection();
    onSelectDate(dateStr);
    onClose();
  };

  // Build grid cells: leading blanks + days
  const cells: Array<{ day: number | null; dateStr: string | null }> = [];
  for (let i = 0; i < firstDay; i++) {
    cells.push({ day: null, dateStr: null });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({ day: d, dateStr: toDateStr(viewYear, viewMonth, d) });
  }
  // Pad to complete last row
  while (cells.length % 7 !== 0) {
    cells.push({ day: null, dateStr: null });
  }

  const monthKey = `${viewYear}-${viewMonth}`;
  const monthAnimClass =
    monthNav === "next"
      ? "calendar-month-enter-next"
      : monthNav === "prev"
        ? "calendar-month-enter-prev"
        : "";

  const content = (
    <>
      <div className="mb-3 flex items-center justify-center gap-1 sm:gap-2">
        <button
          type="button"
          onClick={handlePrevMonth}
          className="flex min-h-[40px] min-w-[40px] shrink-0 items-center justify-center rounded-[2px] text-text-primary transition-opacity hover:opacity-75"
          aria-label="Previous month"
        >
          <ChevronLeft className="h-5 w-5" strokeWidth={2} aria-hidden />
        </button>
        <span className="font-display min-w-0 max-w-[min(100%,16rem)] truncate text-center text-[17px] font-normal leading-tight tracking-[-0.01em] text-text-primary sm:text-[18px]">
          {formatMonthYear(viewYear, viewMonth)}
        </span>
        <button
          type="button"
          onClick={handleNextMonth}
          className="flex min-h-[40px] min-w-[40px] shrink-0 items-center justify-center rounded-[2px] text-text-primary transition-opacity hover:opacity-75"
          aria-label="Next month"
        >
          <ChevronRight className="h-5 w-5" strokeWidth={2} aria-hidden />
        </button>
      </div>

      <div
        key={`body-${monthKey}`}
        className={cn("overflow-hidden", monthAnimClass)}
      >
        <div className="mb-2 grid grid-cols-7 gap-0.5">
          {DAYS_OF_WEEK.map((d) => (
            <div
              key={d}
              className="font-ui flex items-center justify-center text-[12px] font-medium text-text-muted"
            >
              {d}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-y-2">
          {cells.map((cell, idx) => {
            if (!cell.day || !cell.dateStr) {
              return <div key={`blank-${idx}`} className="h-8" />;
            }

            const dateStr = cell.dateStr;
            const isAvailable = availableSet.has(dateStr);
            const isToday = dateStr === todayStr;
            const isSelected = dateStr === currentDate;
            const isFuture = dateStr > todayStr;
            const isDisabled = !isAvailable || isFuture;

            return (
              <button
                key={dateStr}
                disabled={isDisabled}
                onClick={() => !isDisabled && handleDayTap(dateStr)}
                className={[
                  "font-mono relative mx-auto flex h-8 w-8 flex-col items-center justify-center rounded-lg text-[13px] font-medium",
                  isSelected
                    ? "bg-accent text-white"
                    : isToday
                    ? "font-bold text-text-primary"
                    : isDisabled
                    ? "cursor-default text-gray-300"
                    : "text-text-primary",
                ]
                  .filter(Boolean)
                  .join(" ")}
                aria-label={dateStr}
                aria-pressed={isSelected}
              >
                {isToday && !isSelected && (
                  <span className="absolute inset-0 rounded-lg bg-black opacity-10" />
                )}
                <span className="relative z-10 leading-none">{cell.day}</span>
                {isAvailable && !isSelected && (
                  <span
                    className="relative z-10 mt-0.5 block h-1 w-1 rounded-full bg-accent"
                    aria-hidden="true"
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>

      <p className="font-ui mt-3 flex items-center justify-start pl-3 text-xs leading-snug text-text-muted">
        <span
          className="h-1 w-1 shrink-0 rounded-full bg-accent"
          aria-hidden="true"
        />
        <span className="ml-[4px]">Days with briefs available</span>
      </p>
    </>
  );

  if (placement === "sheet") {
    return content;
  }

  return <div className="mt-3 bg-bg-surface p-4">{content}</div>;
}
