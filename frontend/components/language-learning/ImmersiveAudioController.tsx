"use client";

interface ImmersiveAudioControllerProps {
  overallProgress: number; // 0-1, across all sections
  isLessonComplete: boolean;
}

export default function ImmersiveAudioController({
  overallProgress,
  isLessonComplete,
}: ImmersiveAudioControllerProps) {
  const pct = isLessonComplete ? 100 : Math.min(overallProgress * 100, 100);

  return (
    <div className="fixed top-0 left-0 right-0 z-50 h-[3px] bg-rule/20">
      <div
        className="h-full bg-accent-primary transition-[width] duration-200 ease-linear"
        style={{
          width: `${pct}%`,
          ...(pct > 0
            ? { boxShadow: "0 0 6px 1px var(--color-accent-primary, #6366f1)" }
            : {}),
        }}
      />
    </div>
  );
}
