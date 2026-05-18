"use client";

import { Clock, Trophy, Target, Zap, BookOpen, Award } from "lucide-react";
import { useMemo } from "react";

interface LearningStatsProps {
  totalPhrases: number;
  completedPhrases: number;
  totalDuration?: number;
  language: "fr" | "ar";
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

    const estimatedWordsLearned = completedPhrases * 4;
    const xpEarned = completedPhrases * 15 + (masteryRate === 100 ? 50 : 0) + (grammarOpened ?? 0) * 5;

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
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col items-center rounded-xl bg-gray-900/50 border border-gray-800/30 px-4 py-3.5">
          <Target className="h-5 w-5 text-indigo-400/70 mb-2" strokeWidth={1.5} />
          <span className="font-display text-xl font-bold text-gray-100">{stats.masteryRate}%</span>
          <span className="font-ui text-[10px] text-gray-500 uppercase tracking-wider">Mastery</span>
        </div>
        <div className="flex flex-col items-center rounded-xl bg-gray-900/50 border border-gray-800/30 px-4 py-3.5">
          <BookOpen className="h-5 w-5 text-yellow-400/70 mb-2" strokeWidth={1.5} />
          <span className="font-display text-xl font-bold text-gray-100">{stats.estimatedWordsLearned}</span>
          <span className="font-ui text-[10px] text-gray-500 uppercase tracking-wider">Words</span>
        </div>
        <div className="flex flex-col items-center rounded-xl bg-gray-900/50 border border-gray-800/30 px-4 py-3.5">
          <Zap className="h-5 w-5 text-amber-400/70 mb-2" strokeWidth={1.5} />
          <span className="font-display text-xl font-bold text-gray-100">+{stats.xpEarned}</span>
          <span className="font-ui text-[10px] text-gray-500 uppercase tracking-wider">XP</span>
        </div>
        <div className="flex flex-col items-center rounded-xl bg-gray-900/50 border border-gray-800/30 px-4 py-3.5">
          <Clock className="h-5 w-5 text-blue-400/70 mb-2" strokeWidth={1.5} />
          <span className="font-display text-xl font-bold text-gray-100">{stats.timeSpentFormatted}</span>
          <span className="font-ui text-[10px] text-gray-500 uppercase tracking-wider">Time</span>
        </div>
      </div>

      {(stats.sentencesViewed > 0 || stats.grammarOpened > 0) && (
        <div className="rounded-xl bg-indigo-500/5 border border-indigo-500/15 px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <Award className="h-4 w-4 text-indigo-400" strokeWidth={1.5} />
            <span className="font-ui text-[10px] font-semibold text-indigo-300 uppercase tracking-wider">
              Learning Activity
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className="font-display text-lg font-bold text-gray-100">{stats.sentencesViewed}/{totalPhrases}</span>
              <span className="font-ui text-[10px] text-gray-500 block">{langLabel} Sentences</span>
            </div>
            <div>
              <span className="font-display text-lg font-bold text-gray-100">{stats.grammarOpened}</span>
              <span className="font-ui text-[10px] text-gray-500 block">Deep Dives</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
