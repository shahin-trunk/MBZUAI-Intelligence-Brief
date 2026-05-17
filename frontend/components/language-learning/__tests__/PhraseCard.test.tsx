import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PhraseCard from "@/components/language-learning/PhraseCard";
import type { LearningPhrase } from "@/lib/types/brief";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => "/learn",
}));

const mockPhrase: LearningPhrase = {
  id: "phrase_0",
  phrase_target: "C'est la vie",
  phrase_en: "That's life",
  context_anchor: "Life continues despite challenges",
  script1: "This phrase captures the essence of accepting life's unpredictability.",
  script2: "In French, this becomes:",
  script3: "C'est la vie",
  script4: "The phrase uses the demonstrative 'c'est' (this is) with the definite article 'la' before 'vie' (life).",
  audio_url_1: "https://example.com/audio1.mp3",
  audio_url_2: "https://example.com/audio2.mp3",
  audio_url_3: "https://example.com/audio3.mp3",
  audio_url_4: "https://example.com/audio4.mp3",
  grammar: {
    morphology: "Demonstrative pronoun + definite article + noun",
    etymology: "From Latin 'sic est vita'",
    register: "Standard, conversational",
    phonetic_guide: "seh lah VEE",
    usage_notes: "Used to express acceptance of unavoidable situations",
  },
  estimated_duration_seconds: 30,
};

describe("PhraseCard", () => {
  const defaultProps = {
    phrase: mockPhrase,
    phraseNumber: 1,
    totalPhrases: 3,
    language: "fr" as const,
    scriptIndex: 1 as const,
    currentTime: 0,
    duration: 30,
    isPlaying: false,
    onExpandGrammar: vi.fn(),
    showGrammarTrigger: true,
  };

  describe("Script 1 - Bilingual Explanation", () => {
    it("renders phrase number badge", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={1} />);

      expect(screen.getByText("1/3")).toBeInTheDocument();
    });

    it("renders target phrase with correct text", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={1} />);

      expect(screen.getByText("C'est la vie")).toBeInTheDocument();
    });

    it("renders English translation", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={1} />);

      expect(screen.getByText("That's life")).toBeInTheDocument();
    });

    it("renders grammar expand trigger when showGrammarTrigger is true", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={1} showGrammarTrigger={true} />);

      expect(screen.getByText("Explore grammar & linguistic details")).toBeInTheDocument();
    });

    it("does not render grammar trigger when showGrammarTrigger is false", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={1} showGrammarTrigger={false} />);

      expect(screen.queryByText("Explore grammar & linguistic details")).not.toBeInTheDocument();
    });
  });

  describe("Script 2 - Transition", () => {
    it("renders transition text", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={2} />);

      expect(screen.getByText("In French, this becomes:")).toBeInTheDocument();
    });

    it("applies italic styling", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={2} />);

      const transitionText = screen.getByText("In French, this becomes:");
      expect(transitionText).toHaveClass("italic");
    });
  });

  describe("Script 3 - Target Language", () => {
    it("renders context bridge badge", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={3} />);

      expect(screen.getByText("From your briefing")).toBeInTheDocument();
    });

    it("renders context anchor text", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={3} />);

      expect(screen.getByText(/Life continues despite challenges/)).toBeInTheDocument();
    });

    it("renders English translation with decorative dividers", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={3} />);

      expect(screen.getByText("That's life")).toBeInTheDocument();
    });

    it("renders pronunciation guide when available", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={3} />);

      expect(screen.getByText("seh lah VEE")).toBeInTheDocument();
    });

    it("does not render pronunciation guide when not available", () => {
      const phraseWithoutPhonetic = {
        ...mockPhrase,
        grammar: { ...mockPhrase.grammar, phonetic_guide: undefined },
      };

      render(
        <PhraseCard
          {...defaultProps}
          phrase={phraseWithoutPhonetic}
          scriptIndex={3}
        />
      );

      expect(screen.queryByText("seh lah VEE")).not.toBeInTheDocument();
    });
  });

  describe("Language Direction", () => {
    it("applies ltr direction for French", () => {
      render(<PhraseCard {...defaultProps} language="fr" scriptIndex={1} />);

      const phraseElement = screen.getByText("C'est la vie");
      expect(phraseElement).toHaveAttribute("dir", "ltr");
    });

    it("applies rtl direction for Arabic", () => {
      const arabicPhrase = {
        ...mockPhrase,
        phrase_target: "هذه الحياة",
      };

      render(<PhraseCard {...defaultProps} phrase={arabicPhrase} language="ar" scriptIndex={1} />);

      const phraseElement = screen.getByText("هذه الحياة");
      expect(phraseElement).toHaveAttribute("dir", "rtl");
    });
  });

  describe("Responsiveness", () => {
    it("renders with responsive font sizes", () => {
      render(<PhraseCard {...defaultProps} scriptIndex={1} />);

      const phraseElement = screen.getByText("C'est la vie");
      // Check for responsive classes
      expect(phraseElement.className).toMatch(/text-\[24px\]/);
      expect(phraseElement.className).toMatch(/sm:text-\[28px\]/);
      expect(phraseElement.className).toMatch(/lg:text-\[32px\]/);
    });
  });
});
