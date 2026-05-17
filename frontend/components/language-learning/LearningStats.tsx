"use client";

import { Clock, Trophy, Target, Zap, BookOpen, Award } from "lucide-react";
import { useMemo } from "react";

interface LearningStatsProps {
  totalPhrases: number;
  completedPhrases: number;
  totalDuration?: number;
  language: "fr" | "ar";
  // ITER 18: Enhanced tracking
  sentencesViewed?: number;
  grammarOpened?: number;
  startTime?: number;
}

export default function LearningStats({
  totalPhrases,
  completedPhrases,
  totalDuration,
  language,
  sentencesViewed,
  grammarOpened,
  startTime,
}: LearningStatsProps) {
  const stats = useMemo(() => {
    const masteryRate = totalPhrases > 0
      ? Math.round((completedPhrases / totalPhrases) * 100)
      : 0;

    // ITER 18: Count key words learned from grammar.key_words
    const estimatedWordsLearned = completedPhrases * 4; // Average 4 key words per sentence

    const xpEarned = completedPhrases * 15 + (masteryRate === 100 ? 50 : 0) + (grammarOpened ?? 0) * 5;

    // ITER 18: Calculate actual time spent if startTime is provided
    const timeSpentMs = startTime ? Date.now() - startTime : 0;
    const timeSpentFormatted = timeSpentMs > 0
      ? `${Math.floor(timeSpentMs / 60000)}m ${Math.floor((timeSpentMs % 60000) / 1000)}s`
      : totalDuration
        ? `${Math.floor(totalDuration / 60)}m ${Math.floor(totalDuration % 60)}s`
        : "~3m";

    return {
      masteryRate,
      estimatedWordsLearned,
      xpEarned,
      timeSpentFormatted,
      sentencesViewed: sentencesViewed ?? completedPhrases,
      grammarOpened: grammarOpened ?? 0,
    };
  }, [totalPhrases, completedPhrases, totalDuration, sentencesViewed, grammarOpened, startTime]);

  const langLabel = language === "fr" ? "French" : "Arabic";

  return (
    <div className="space-y-4">
      {/* Primary stats grid */}
      <div className="grid grid-cols-2 gap-3 sm:gap-4">
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
          <BookOpen className="h-5 w-5 sm:h-6 sm:w-6 text-yellow-500/70 mb-2" />
          <span className="font-display text-xl sm:text-2xl font-bold text-text-primary">
            {stats.estimatedWordsLearned}
          </span>
          <span className="font-ui text-[10px] sm:text-[11px] text-text-muted uppercase tracking-wide">
            Words
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
            {stats.timeSpentFormatted}
          </span>
          <span className="font-ui text-[10px] sm:text-[11px] text-text-muted uppercase tracking-wide">
            Time
          </span>
        </div>
      </div>

      {/* ITER 18: Learning activity summary */}
      {(stats.sentencesViewed > 0 || stats.grammarOpened > 0) && (
        <div className="rounded-xl bg-accent-primary/5 border border-accent-primary/20 px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <Award className="h-4 w-4 text-accent-primary" />
            <span className="font-ui text-xs font-semibold text-accent-primary uppercase tracking-wide">
              Learning Activity
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="font-display text-lg font-bold text-text-primary">
                {stats.sentencesViewed}/{totalPhrases}
              </span>
              <span className="font-ui text-[10px] text-text-muted block">
                {langLabel} Sentences
              </span>
            </div>
            <div>
              <span className="font-display text-lg font-bold text-text-primary">
                {stats.grammarOpened}
              </span>
              <span className="font-ui text-[10px] text-text-muted block">
                Deep Dives
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
