"use client";

import { cn } from "@/lib/utils";

interface TabOption {
  key: string;
  label: string;
}

interface IntelTabsProps {
  tabs: TabOption[];
  activeKey: string;
  onChange: (key: string) => void;
  className?: string;
}

export function IntelTabs({
  tabs,
  activeKey,
  onChange,
  className,
}: IntelTabsProps) {
  return (
    <div
      className={cn(
        "inline-flex border-b border-border-primary mb-6",
        className
      )}
    >
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          onClick={() => onChange(tab.key)}
          className={cn("intel-tab", activeKey === tab.key && "active")}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
