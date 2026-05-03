"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type {
  EngagementFormat,
  GenerateDossierInput,
} from "@/lib/types/executive-engagement";

const FORMAT_OPTIONS: EngagementFormat[] = ["In person", "Virtual", "Hybrid"];

interface NewEngagementDialogProps {
  externalOpen?: boolean;
  onExternalOpenChange?: (open: boolean) => void;
  onGenerate?: (input: GenerateDossierInput) => void;
}

export function NewEngagementDialog({
  externalOpen,
  onExternalOpenChange,
  onGenerate,
}: NewEngagementDialogProps = {}) {
  const [internalOpen, setInternalOpen] = useState(false);
  const open = externalOpen !== undefined ? externalOpen : internalOpen;
  const setOpen = onExternalOpenChange ?? setInternalOpen;
  const [error, setError] = useState("");

  const [visitorName, setVisitorName] = useState("");
  const [visitorTitle, setVisitorTitle] = useState("");
  const [visitorOrganization, setVisitorOrganization] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("10:00");
  const [location, setLocation] = useState("");
  const [format, setFormat] = useState<EngagementFormat>("In person");

  function resetForm() {
    setVisitorName("");
    setVisitorTitle("");
    setVisitorOrganization("");
    setDate("");
    setTime("10:00");
    setLocation("");
    setFormat("In person");
    setError("");
  }

  function handleGenerate() {
    if (!visitorName.trim() || !date || !time.trim()) {
      setError("Name, date, and time are required");
      return;
    }

    const input: GenerateDossierInput = {
      visitorName: visitorName.trim(),
      visitorTitle: visitorTitle.trim(),
      visitorOrganization: visitorOrganization.trim(),
      date,
      time: time.trim() + " GST",
      location: location.trim(),
      format,
    };

    // Fire generation in parent and close dialog immediately
    onGenerate?.(input);
    setOpen(false);
    resetForm();
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) resetForm();
      }}
    >
      {externalOpen === undefined && (
        <DialogTrigger asChild>
          <button
            type="button"
            className="rounded-[6px] px-3.5 py-1.5 text-[12px] font-semibold transition-colors"
            style={{ background: "var(--sig-high)", color: "var(--surface-primary)" }}
          >
            + New Engagement
          </button>
        </DialogTrigger>
      )}

      <DialogContent className="sm:max-w-[520px] bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="text-text-bright">
            New Engagement
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-2">
          {/* Visitor name */}
          <FieldGroup label="Visitor name *">
            <input
              type="text"
              value={visitorName}
              onChange={(e) => setVisitorName(e.target.value)}
              placeholder="Prof. Fei-Fei Li"
              className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary placeholder:text-text-dim outline-none focus:border-[rgba(212,168,67,0.4)]"
            />
          </FieldGroup>

          {/* Title */}
          <FieldGroup label="Title">
            <input
              type="text"
              value={visitorTitle}
              onChange={(e) => setVisitorTitle(e.target.value)}
              placeholder="Co-Founder & CEO"
              className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary placeholder:text-text-dim outline-none focus:border-[rgba(212,168,67,0.4)]"
            />
          </FieldGroup>

          {/* Organization */}
          <FieldGroup label="Organization">
            <input
              type="text"
              value={visitorOrganization}
              onChange={(e) => setVisitorOrganization(e.target.value)}
              placeholder="World Labs"
              className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary placeholder:text-text-dim outline-none focus:border-[rgba(212,168,67,0.4)]"
            />
          </FieldGroup>

          {/* Date + Time row */}
          <div className="grid grid-cols-2 gap-3">
            <FieldGroup label="Date *">
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary outline-none focus:border-[rgba(212,168,67,0.4)] [color-scheme:dark]"
              />
            </FieldGroup>
            <FieldGroup label="Time *">
              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary outline-none focus:border-[rgba(212,168,67,0.4)] [color-scheme:dark]"
              />
            </FieldGroup>
          </div>

          {/* Location */}
          <FieldGroup label="Location">
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Executive Boardroom"
              className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary placeholder:text-text-dim outline-none focus:border-[rgba(212,168,67,0.4)]"
            />
          </FieldGroup>

          {/* Format */}
          <FieldGroup label="Format">
            <div className="flex gap-1">
              {FORMAT_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setFormat(opt)}
                  className="rounded-[6px] px-3 py-1.5 text-[12px] transition-colors"
                  style={{
                    background:
                      format === opt
                        ? "rgba(212,168,67,0.15)"
                        : "transparent",
                    color: format === opt ? "var(--sig-high)" : "var(--text-dim)",
                    border: `1px solid ${format === opt ? "rgba(212,168,67,0.3)" : "var(--border-primary)"}`,
                  }}
                >
                  {opt}
                </button>
              ))}
            </div>
          </FieldGroup>

          {/* Error */}
          {error && (
            <p className="text-[12px] text-red-400">{error}</p>
          )}

          {/* Generate button */}
          <button
            type="button"
            onClick={handleGenerate}
            className="w-full rounded-[6px] py-2.5 text-[13px] font-semibold transition-colors"
            style={{ background: "var(--sig-high)", color: "var(--surface-primary)" }}
          >
            Generate Dossier
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FieldGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-[11px] text-text-secondary mb-1.5 font-medium">
        {label}
      </label>
      {children}
    </div>
  );
}
