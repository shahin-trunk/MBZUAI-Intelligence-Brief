"use client";

import { useCallback, useRef, useState } from "react";
import type { ExhibitData } from "@/lib/types/brief";
import { ExhibitRenderer } from "@/components/card-reader/ExhibitRenderer";
import { ExhibitEditor } from "./ExhibitEditor";

type UploaderState = "empty" | "uploading" | "extracting" | "review" | "error";

interface ExhibitUploaderProps {
  itemId: string;
  onExhibitAdded: (exhibit: ExhibitData) => void;
  onCancel: () => void;
}

export function ExhibitUploader({ itemId, onExhibitAdded, onCancel }: ExhibitUploaderProps) {
  const [editing, setEditing] = useState(false);
  const [state, setState] = useState<UploaderState>("empty");
  const [exhibit, setExhibit] = useState<ExhibitData | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [caption, setCaption] = useState("");
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const processFile = useCallback(
    async (file: File) => {
      setState("uploading");
      setError("");

      const formData = new FormData();
      formData.append("image", file);
      formData.append("item_id", itemId);

      setState("extracting");

      try {
        const res = await fetch("/api/curation/extract-exhibit", {
          method: "POST",
          body: formData,
        });
        const data = await res.json();

        setImageUrl(data.image_url ?? null);

        if (data.exhibit) {
          setExhibit(data.exhibit as ExhibitData);
          setState("review");
          if (data.extraction_failed) {
            setError(data.reason ?? "Could not extract structured data");
          }
        } else {
          setError(data.error ?? "Extraction failed");
          setState("error");
        }
      } catch {
        setError("Network error during upload");
        setState("error");
      }
    },
    [itemId],
  );

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  }

  function handleConfirm() {
    if (!exhibit) return;
    // If it's a raw_image, add the caption
    if (exhibit.type === "raw_image" && caption) {
      exhibit.data.caption = caption;
    }
    onExhibitAdded(exhibit);
  }

  function handleSaveAsImage() {
    if (!imageUrl) return;
    onExhibitAdded({
      type: "raw_image",
      data: { image_url: imageUrl, caption },
      source_image_url: imageUrl,
    });
  }

  // Empty state — drop zone
  if (state === "empty") {
    return (
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`rounded-lg border-2 border-dashed p-6 text-center transition-colors cursor-pointer ${
          dragging
            ? "border-accent-primary bg-accent-primary/5"
            : "border-border-secondary hover:border-accent-primary/30"
        }`}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".png,.jpg,.jpeg,.webp"
          onChange={handleFileChange}
          className="hidden"
        />
        <svg className="w-8 h-8 mx-auto mb-2 text-text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242M12 12v9m0 0l-3-3m3 3l3-3" />
        </svg>
        <p className="text-xs text-text-muted">
          Drop an image here or click to upload
        </p>
        <p className="text-[10px] text-text-muted/50 mt-1">
          PNG, JPG, WebP (max 10MB)
        </p>
      </div>
    );
  }

  // Uploading / Extracting
  if (state === "uploading" || state === "extracting") {
    return (
      <div className="rounded-lg border border-border-secondary p-6 text-center">
        <div className="animate-spin w-6 h-6 border-2 border-accent-primary border-t-transparent rounded-full mx-auto mb-3" />
        <p className="text-xs text-text-muted">
          {state === "uploading" ? "Uploading image..." : "Extracting data from image..."}
        </p>
      </div>
    );
  }

  // Review state
  if (state === "review" && exhibit) {
    if (editing) {
      return (
        <div className="rounded-lg border border-border-secondary p-4">
          <ExhibitEditor
            exhibit={exhibit}
            onSave={(updated) => {
              setExhibit(updated);
              setEditing(false);
            }}
            onCancel={() => setEditing(false)}
          />
        </div>
      );
    }

    return (
      <div className="rounded-lg border border-border-secondary p-4 space-y-3">
        {error && (
          <p className="text-xs text-amber-400 bg-amber-400/10 px-3 py-1.5 rounded">
            {error} — showing as image fallback
          </p>
        )}

        <ExhibitRenderer exhibit={exhibit} />

        {exhibit.type === "raw_image" && (
          <div>
            <label className="text-[10px] uppercase tracking-wider text-text-muted">Caption</label>
            <input
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              placeholder="Optional caption..."
              className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary"
            />
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={handleConfirm}
            className="text-xs px-3 py-1.5 rounded bg-green-600 text-white hover:bg-green-500"
          >
            Attach Exhibit
          </button>
          {exhibit.type !== "raw_image" && (
            <button
              onClick={() => setEditing(true)}
              className="text-xs px-3 py-1.5 rounded border border-border-secondary text-text-muted hover:text-text-primary"
            >
              Edit Data
            </button>
          )}
          <button
            onClick={onCancel}
            className="text-xs px-3 py-1.5 rounded bg-surface-primary text-text-muted hover:text-text-primary"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  // Error state
  return (
    <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-4 space-y-3">
      <p className="text-xs text-red-400">{error}</p>
      {imageUrl && (
        <>
          <img src={imageUrl} alt="Uploaded" className="w-full rounded max-h-48 object-contain" />
          <div>
            <label className="text-[10px] uppercase tracking-wider text-text-muted">Caption</label>
            <input
              value={caption}
              onChange={(e) => setCaption(e.target.value)}
              placeholder="Optional caption..."
              className="mt-1 w-full rounded bg-surface-primary border border-border-secondary px-3 py-1.5 text-sm text-text-primary"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleSaveAsImage}
              className="text-xs px-3 py-1.5 rounded bg-amber-600 text-white hover:bg-amber-500"
            >
              Save as Image
            </button>
            <button
              onClick={onCancel}
              className="text-xs px-3 py-1.5 rounded bg-surface-primary text-text-muted hover:text-text-primary"
            >
              Cancel
            </button>
          </div>
        </>
      )}
      {!imageUrl && (
        <button
          onClick={onCancel}
          className="text-xs px-3 py-1.5 rounded bg-surface-primary text-text-muted hover:text-text-primary"
        >
          Cancel
        </button>
      )}
    </div>
  );
}
