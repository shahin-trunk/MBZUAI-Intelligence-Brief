"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type {
  Engagement,
  EngagementFormat,
} from "@/lib/types/executive-engagement";

const FORMAT_OPTIONS: EngagementFormat[] = ["In person", "Virtual", "Hybrid"];

interface Props {
  engagement: Engagement;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditEngagementDialog({
  engagement,
  open,
  onOpenChange,
}: Props) {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");

  const [visitorName, setVisitorName] = useState(engagement.visitor_name);
  const [visitorTitle, setVisitorTitle] = useState(engagement.visitor_title);
  const [visitorOrg, setVisitorOrg] = useState(
    engagement.visitor_organization
  );
  const [date, setDate] = useState(engagement.date);
  const [time, setTime] = useState(engagement.time);
  const [location, setLocation] = useState(engagement.location);
  const [format, setFormat] = useState<EngagementFormat>(engagement.format);
  // Use concise narrative if available (new shape), fall back to bio (old shape)
  const [bio, setBio] = useState(
    engagement.bio_concise_narrative || engagement.bio || ""
  );

  async function handleSave() {
    setIsLoading(true);
    setError("");
    try {
      const updateFields: Record<string, unknown> = {
        visitor_name: visitorName,
        visitor_title: visitorTitle,
        visitor_organization: visitorOrg,
        date,
        time,
        location,
        format,
        bio, // backward compat column
      };

      // If this engagement has the new dual-bio columns, also update concise narrative
      if (engagement.bio_concise_narrative !== undefined) {
        updateFields.bio_concise_narrative = bio;
      }

      const res = await fetch(
        `/api/internal/engagements/${engagement.id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updateFields),
        }
      );
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to update");
      }
      onOpenChange(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleRegenerate() {
    setIsRegenerating(true);
    setError("");
    try {
      const res = await fetch(
        `/api/internal/engagements/${engagement.id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            regenerate: true,
            visitor_name: visitorName,
            visitor_title: visitorTitle,
            visitor_organization: visitorOrg,
          }),
        }
      );
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Failed to regenerate");
      }
      onOpenChange(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to regenerate");
    } finally {
      setIsRegenerating(false);
    }
  }

  async function handleUpload(file: File) {
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(
        `/api/internal/engagements/${engagement.id}/materials`,
        { method: "POST", body: formData }
      );
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Upload failed");
      }
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  }

  async function handleDeleteMaterial(materialId: string) {
    try {
      const res = await fetch(
        `/api/internal/engagements/${engagement.id}/materials`,
        {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ materialId }),
        }
      );
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Delete failed");
      }
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function handleDelete() {
    if (!confirm("Delete this engagement? This cannot be undone.")) return;
    try {
      const res = await fetch(
        `/api/internal/engagements/${engagement.id}`,
        { method: "DELETE" }
      );
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || "Delete failed");
      }
      onOpenChange(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  const busy = isLoading || isRegenerating;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px] max-h-[85vh] overflow-y-auto bg-bg-secondary border-border-primary">
        <DialogHeader>
          <DialogTitle className="text-text-bright">
            Edit Engagement
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-2">
          <FieldGroup label="Visitor name">
            <input
              type="text"
              value={visitorName}
              onChange={(e) => setVisitorName(e.target.value)}
              disabled={busy}
              className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary outline-none focus:border-[rgba(212,168,67,0.4)]"
            />
          </FieldGroup>

          <FieldGroup label="Title">
            <input
              type="text"
              value={visitorTitle}
              onChange={(e) => setVisitorTitle(e.target.value)}
              disabled={busy}
              className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary outline-none focus:border-[rgba(212,168,67,0.4)]"
            />
          </FieldGroup>

          <FieldGroup label="Organization">
            <input
              type="text"
              value={visitorOrg}
              onChange={(e) => setVisitorOrg(e.target.value)}
              disabled={busy}
              className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary outline-none focus:border-[rgba(212,168,67,0.4)]"
            />
          </FieldGroup>

          <div className="grid grid-cols-2 gap-3">
            <FieldGroup label="Date">
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                disabled={busy}
                className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary outline-none focus:border-[rgba(212,168,67,0.4)] [color-scheme:dark]"
              />
            </FieldGroup>
            <FieldGroup label="Time">
              <input
                type="text"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                disabled={busy}
                className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary outline-none focus:border-[rgba(212,168,67,0.4)]"
              />
            </FieldGroup>
          </div>

          <FieldGroup label="Location">
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              disabled={busy}
              className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary outline-none focus:border-[rgba(212,168,67,0.4)]"
            />
          </FieldGroup>

          <FieldGroup label="Format">
            <div className="flex gap-1">
              {FORMAT_OPTIONS.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setFormat(opt)}
                  disabled={busy}
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

          <FieldGroup label="Bio narrative">
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              disabled={busy}
              rows={6}
              className="w-full rounded-[6px] bg-bg-tertiary border border-border-primary px-3 py-2 text-[13px] text-text-primary outline-none focus:border-[rgba(212,168,67,0.4)] resize-none"
            />
            <p className="text-[11px] text-text-dim mt-1">
              Structured facts (roles, recognition) are auto-generated. Use Regenerate to update them.
            </p>
          </FieldGroup>

          {/* Materials */}
          <FieldGroup label="Materials">
            <div className="space-y-2">
              {engagement.materials.map((mat) => (
                <div
                  key={mat.id}
                  className="flex items-center justify-between rounded-[6px] px-3 py-2"
                  style={{
                    background: "rgba(148,163,184,0.06)",
                    border: "1px solid var(--border-primary)",
                  }}
                >
                  <span className="text-[12px] text-text-secondary truncate">
                    {mat.name}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDeleteMaterial(mat.id)}
                    className="text-[11px] text-red-400 hover:text-red-300 shrink-0 ml-2"
                  >
                    Remove
                  </button>
                </div>
              ))}

              <input
                ref={fileRef}
                type="file"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleUpload(f);
                }}
              />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={isUploading}
                className="text-[12px] text-sig-high hover:text-[#E5BE6A] transition-colors"
              >
                {isUploading ? "Uploading..." : "+ Upload material"}
              </button>
            </div>
          </FieldGroup>

          {error && (
            <p className="text-[12px] text-red-400">{error}</p>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between pt-2">
            <button
              type="button"
              onClick={handleDelete}
              className="text-[12px] text-red-400 hover:text-red-300 transition-colors"
            >
              Delete engagement
            </button>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleRegenerate}
                disabled={busy}
                className="rounded-[6px] px-3 py-1.5 text-[12px] text-text-secondary transition-colors disabled:opacity-40"
                style={{ border: "1px solid var(--border-primary)" }}
              >
                {isRegenerating
                  ? `Researching ${visitorName}...`
                  : "Regenerate"}
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={busy}
                className="rounded-[6px] px-3.5 py-1.5 text-[12px] font-semibold transition-colors disabled:opacity-40"
                style={{ background: "var(--sig-high)", color: "var(--surface-primary)" }}
              >
                {isLoading ? "Saving..." : "Save changes"}
              </button>
            </div>
          </div>
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
