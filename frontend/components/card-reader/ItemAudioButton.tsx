"use client";

import { useRef, useState } from "react";

interface ItemAudioButtonProps {
  audioUrl?: string;
}

export function ItemAudioButton({ audioUrl }: ItemAudioButtonProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);

  if (!audioUrl) return null;

  function toggle() {
    const el = audioRef.current;
    if (!el) return;
    if (playing) {
      el.pause();
    } else {
      el.play();
    }
    setPlaying(!playing);
  }

  return (
    <>
      <audio
        ref={audioRef}
        src={audioUrl}
        onEnded={() => setPlaying(false)}
        preload="none"
      />
      <button
        onClick={toggle}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-accent-primary/10 text-accent-primary text-xs hover:bg-accent-primary/20 transition-colors"
      >
        {playing ? (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
            <rect x="2" y="2" width="3" height="8" rx="0.5" />
            <rect x="7" y="2" width="3" height="8" rx="0.5" />
          </svg>
        ) : (
          <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
            <path d="M3 1.5v9l7.5-4.5z" />
          </svg>
        )}
        {playing ? "Pause" : "Listen"}
      </button>
    </>
  );
}
