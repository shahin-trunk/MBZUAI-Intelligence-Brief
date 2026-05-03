"use client";

interface KeyboardHelpOverlayProps {
  open: boolean;
  onClose: () => void;
}

const shortcuts: { key: string; description: string }[] = [
  { key: "j / k", description: "Next / Previous item" },
  { key: "\u2190 / \u2192", description: "Previous / Next brief" },
  { key: "1-5", description: "Jump to section" },
  { key: "Esc", description: "Close panels" },
  { key: "?", description: "Toggle this help" },
];

export function KeyboardHelpOverlay({ open, onClose }: KeyboardHelpOverlayProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-bg-secondary border border-border-primary rounded-md p-6 max-w-sm w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="font-serif text-lg text-text-primary mb-4">Keyboard Shortcuts</h2>

        <ul className="space-y-3">
          {shortcuts.map(({ key, description }) => (
            <li key={key} className="flex items-center justify-between gap-4">
              <kbd className="font-mono text-[14px] bg-bg-tertiary border border-border-primary rounded px-2 py-0.5 text-text-primary min-w-[2rem] text-center">
                {key}
              </kbd>
              <span className="text-sm text-text-secondary">{description}</span>
            </li>
          ))}
        </ul>

        <p className="mt-5 text-xs text-text-muted text-center">
          Press <kbd className="font-mono text-[14px] bg-bg-tertiary border border-border-primary rounded px-1 py-0.5">?</kbd> or{" "}
          <kbd className="font-mono text-[14px] bg-bg-tertiary border border-border-primary rounded px-1 py-0.5">Esc</kbd> to close
        </p>
      </div>
    </div>
  );
}
