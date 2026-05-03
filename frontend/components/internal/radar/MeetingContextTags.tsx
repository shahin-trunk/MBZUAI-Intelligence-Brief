import type { MeetingContextTag } from "@/lib/types/internal-intelligence";

interface MeetingContextTagsProps {
  tags: MeetingContextTag[];
}

const TAG_STYLES: Record<MeetingContextTag, string> = {
  "board-ready": "bg-text-dim/20 text-text-secondary border-text-dim/40",
  government: "bg-sig-high/10 text-sig-high border-sig-high/30",
  "donor-ready": "bg-[#06B6D4]/10 text-[#06B6D4] border-[#06B6D4]/30",
};

const TAG_LABELS: Record<MeetingContextTag, string> = {
  "board-ready": "Board",
  government: "Government",
  "donor-ready": "Donor",
};

export function MeetingContextTags({ tags }: MeetingContextTagsProps) {
  if (tags.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((tag) => (
        <span
          key={tag}
          className={`inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[11px] font-medium ${TAG_STYLES[tag]}`}
        >
          {TAG_LABELS[tag]}
        </span>
      ))}
    </div>
  );
}
