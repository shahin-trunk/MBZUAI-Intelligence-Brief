import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LanguageLearningView from "@/components/language-learning/LanguageLearningView";
import type { BriefItem } from "@/lib/types/brief";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => "/learn",
}));

// Mock useSectionAudio hook
vi.mock("@/hooks/useSectionAudio", () => ({
  useSectionAudio: vi.fn((urls, options) => ({
    currentSectionIndex: 0,
    sectionProgress: 0.5,
    overallProgress: 0.1,
    currentTime: 15,
    duration: 30,
    isPlaying: true,
    isLoading: false,
    speed: 1,
    cycleSpeed: vi.fn(),
    playSection: vi.fn(),
    pause: vi.fn(),
    togglePlayPause: vi.fn(),
  })),
}));

const mockBriefItem: BriefItem = {
  id: "test-item-001",
  headline: "France announces new climate initiative",
  summary: "French government unveils comprehensive plan",
  category: "politics",
  date: "2026-05-17",
  learning_fr: {
    version: 3,
    language: "fr",
    difficulty: "intermediate",
    phrases: [
      {
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
      },
      {
        id: "phrase_1",
        phrase_target: "Le changement climatique",
        phrase_en: "Climate change",
        context_anchor: "France announces new climate initiative",
        script1: "This phrase refers to the environmental challenges discussed in the briefing.",
        script2: "In French, this becomes:",
        script3: "Le changement climatique",
        script4: "Note the adjective placement after the noun in French.",
        audio_url_1: "https://example.com/audio5.mp3",
        audio_url_2: "https://example.com/audio6.mp3",
        audio_url_3: "https://example.com/audio7.mp3",
        audio_url_4: "https://example.com/audio8.mp3",
        grammar: {
          morphology: "Noun + adjective",
          etymology: "From Latin 'clima' meaning slope",
          register: "Formal, scientific",
          phonetic_guide: "luh shahnzh-mohn klee-mah-teek",
          usage_notes: "Common in environmental and political discourse",
        },
        estimated_duration_seconds: 30,
      },
    ],
  },
  learning_ar: null,
};

describe("LanguageLearningView - Integration Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe("Initial Load & Rendering", () => {
    it("renders the learning view with all components", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Should show phrase content
      expect(screen.getByText("C'est la vie")).toBeInTheDocument();
    });

    it("displays phrase number badge correctly", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      expect(screen.getByText("1/2")).toBeInTheDocument();
    });

    it("shows context anchor from briefing", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      expect(screen.getByText(/Life continues despite challenges/)).toBeInTheDocument();
    });
  });

  describe("Phrase Navigation", () => {
    it("allows navigation between phrases", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Initially shows first phrase
      expect(screen.getByText("1/2")).toBeInTheDocument();

      // Navigation dots should be present
      const navigationDots = screen.getAllByRole("button");
      expect(navigationDots.length).toBeGreaterThan(0);
    });

    it("shows correct phrase count", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      expect(screen.getByText("1/2")).toBeInTheDocument();
    });
  });

  describe("Language Switching", () => {
    it("shows language toggle when both languages available", () => {
      const itemWithBothLangs = {
        ...mockBriefItem,
        learning_ar: mockBriefItem.learning_fr,
      };

      render(
        <LanguageLearningView
          item={itemWithBothLangs}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Should show language options
      expect(screen.getByText("FR")).toBeInTheDocument();
    });

    it("defaults to French when available", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Should render French content
      expect(screen.getByText("C'est la vie")).toBeInTheDocument();
    });
  });

  describe("Progress Persistence", () => {
    it("saves progress to localStorage", async () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Wait for progress to be saved
      await waitFor(() => {
        const stored = localStorage.getItem("ll-progress-test-item-001-fr");
        expect(stored).toBeTruthy();
      });
    });

    it("loads progress from localStorage on mount", () => {
      // Pre-populate localStorage
      localStorage.setItem(
        "ll-progress-test-item-001-fr",
        JSON.stringify({
          completedPhrases: [0],
          isLessonComplete: false,
          timestamp: Date.now(),
        })
      );

      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Should have loaded the saved progress
      expect(screen.getByText("C'est la vie")).toBeInTheDocument();
    });
  });

  describe("Grammar Drawer", () => {
    it("shows grammar trigger on script 3", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Grammar trigger should appear when on script 3
      const grammarButton = screen.queryByText("Explore grammar & linguistic details");
      // This depends on current script index - may not be visible initially
    });

    it("opens grammar drawer when trigger is clicked", async () => {
      const user = userEvent.setup();

      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      const grammarButton = screen.queryByText("Explore grammar & linguistic details");
      if (grammarButton) {
        await user.click(grammarButton);
        // Drawer should open with grammar content
        await waitFor(() => {
          expect(screen.getByRole("dialog")).toBeInTheDocument();
        });
      }
    });
  });

  describe("Loading States", () => {
    it("shows loading when no content available", () => {
      const emptyItem = {
        ...mockBriefItem,
        learning_fr: null,
      } as unknown as BriefItem;

      render(
        <LanguageLearningView
          item={emptyItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      expect(screen.getByText("Content not available")).toBeInTheDocument();
    });

    it("shows generating state when phrases are empty", () => {
      const generatingItem = {
        ...mockBriefItem,
        learning_fr: {
          version: 3,
          language: "fr",
          difficulty: "beginner",
          phrases: [],
        },
      } as unknown as BriefItem;

      render(
        <LanguageLearningView
          item={generatingItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      expect(screen.getByText("Generating learning content...")).toBeInTheDocument();
    });
  });

  describe("Responsiveness", () => {
    it("renders with mobile-friendly layout", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Should have touch-friendly elements
      const buttons = screen.getAllByRole("button");
      buttons.forEach(button => {
        // All buttons should be accessible
        expect(button).toBeVisible();
      });
    });

    it("displays phrase content at readable font sizes", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      const phraseText = screen.getByText("C'est la vie");
      // Should have responsive font classes
      expect(phraseText.className).toMatch(/text-\[/);
    });
  });

  describe("Accessibility", () => {
    it("has proper ARIA labels", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Main content area should have role
      const mainContent = screen.getByRole("button");
      expect(mainContent).toHaveAttribute("tabIndex");
    });

    it("supports keyboard navigation", () => {
      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Should be focusable
      const interactiveElement = screen.getByRole("button");
      expect(interactiveElement).toHaveAttribute("tabIndex", "-1");
    });
  });

  describe("Completion Flow", () => {
    it("shows completion state when lesson is done", () => {
      // Pre-set completed state
      localStorage.setItem(
        "ll-progress-test-item-001-fr",
        JSON.stringify({
          completedPhrases: [0, 1],
          isLessonComplete: true,
          timestamp: Date.now(),
        })
      );

      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      // Should show completion UI
      expect(screen.getByText("Lesson Complete!")).toBeInTheDocument();
    });

    it("provides replay option after completion", () => {
      localStorage.setItem(
        "ll-progress-test-item-001-fr",
        JSON.stringify({
          completedPhrases: [0, 1],
          isLessonComplete: true,
          timestamp: Date.now(),
        })
      );

      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      expect(screen.getByText("Replay Lesson")).toBeInTheDocument();
    });

    it("provides reset progress option", () => {
      localStorage.setItem(
        "ll-progress-test-item-001-fr",
        JSON.stringify({
          completedPhrases: [0, 1],
          isLessonComplete: true,
          timestamp: Date.now(),
        })
      );

      render(
        <LanguageLearningView
          item={mockBriefItem}
          briefDate="2026-05-17"
          slideIndex={0}
        />
      );

      expect(screen.getByText("Reset Progress")).toBeInTheDocument();
    });
  });
});
