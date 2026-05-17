"use client";

import { Clock, Trophy, Target, Zap } from "lucide-react";
import { useMemo } from "react";

interface LearningStatsProps {
  totalPhrases: number;
  completedPhrases: number;
  totalDuration?: number;
  language: "fr" | "ar";
}

export default function LearningStats({
  totalPhrases,
  completedPhrases,
  totalDuration,
  language,
}: LearningStatsProps) {
  const stats = useMemo(() => {
    const masteryRate = totalPhrases > 0
      ? Math.round((completedPhrases / totalPhrases) * 100)
      : 0;

    const estimatedWordsLearned = completedPhrases * 3; // Average 3 key phrases per card

    const xpEarned = completedPhrases * 10 + (masteryRate === 100 ? 50 : 0);

    return {
      masteryRate,
      estimatedWordsLearned,
      xpEarned,
      durationFormatted: totalDuration
        ? `${Math.floor(totalDuration / 60)}m ${Math.floor(totalDuration % 60)}s`
        : "~3m",
    };
  }, [totalPhrases, completedPhrases, totalDuration]);

  return (
    <div className="grid grid-cols-2 gap-3 sm:gap-4 mb-6 sm:mb-8">
      {/* Mastery Rate */}
      <div className="flex flex-col items-center rounded-xl bg-bg-surface/50 border border-rule/30 px-4 py-3">
        <Target className="h-5 w-5 sm:h-6 sm:w-6 text-accent-primary/70 mb-2" />
        <span className="font-display text-xl sm:text-2xl font-bold text-text-primary">
          {stats.masteryRate}%
        </span>
        <span className="font-ui text-[10px] sm:text-[11px] text-text-muted uppercase tracking-wide">
          Mastery
        </span>
      </div>

      {/* Words Learned */}
      <div className="flex flex-col items-center rounded-xl bg-bg-surface/50 border border-rule/30 px-4 py-3">
        <Trophy className="h-5 w-5 sm:h-6 sm:w-6 text-yellow-500/70 mb-2" />
        <span className="font-display text-xl sm:text-2xl font-bold text-text-primary">
          {stats.estimatedWordsLearned}
        </span>
        <span className="font-ui text-[10px] sm:text-[11px] text-text-muted uppercase tracking-wide">
          Phrases
        </span>
      </div>

      {/* XP Earned */}
      <div className="flex flex-col items-center rounded-xl bg-bg-surface/50 border border-rule/30 px-4 py-3">
        <Zap className="h-5 w-5 sm:h-6 sm:w-6 text-amber-500/70 mb-2" />
        <span className="font-display text-xl sm:text-2xl font-bold text-text-primary">
          +{stats.xpEarned}
        </span>
        <span className="font-ui text-[10px] sm:text-[11px] text-text-muted uppercase tracking-wide">
          XP Earned
        </span>
      </div>

      {/* Time Spent */}
      <div className="flex flex-col items-center rounded-xl bg-bg-surface/50 border border-rule/30 px-4 py-3">
        <Clock className="h-5 w-5 sm:h-6 sm:w-6 text-blue-500/70 mb-2" />
        <span className="font-display text-xl sm:text-2xl font-bold text-text-primary">
          {stats.durationFormatted}
        </span>
        <span className="font-ui text-[10px] sm:text-[11px] text-text-muted uppercase tracking-wide">
          Duration
        </span>
      </div>
    </div>
  );
}
