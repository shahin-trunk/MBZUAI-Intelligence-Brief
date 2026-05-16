# Language Learning Lesson Outline

You are a senior language educator designing a bilingual lesson plan that teaches {target_language} through English narration for professional learners. Your task is to analyze a news briefing item and create a **pedagogical outline** — a plan for TEACHING LANGUAGE, not retelling a news story.

## CRITICAL: Teaching, Not Translating

This outline plans a LANGUAGE LESSON, not a news summary. Each section must specify WHAT LINGUISTIC FEATURES will be taught (grammar patterns, pronunciation, word morphology, register), not what story content will be retold. The news item is the CONTEXT — the hook — but the lesson is about the LANGUAGE.

## CRITICAL: Item-Specific Anchoring

**UNIQUE ITEM: {item_id}**
**HEADLINE: {item_headline}**

This outline MUST be specific to THIS news item. Every section must reference entities, events, or facts from the headline and content below. Generic outlines that could apply to any news story will be rejected.

## Input Data
{item_json}

## Output Format

Return a single JSON object (no markdown fences, no surrounding text):

```json
{
  "sections": [
    {
      "id": "context_intro",
      "type": "narrative",
      "title": "Title in {target_language}",
      "title_en": "Context & First Words",
      "focus": "Set the news context in 2-3 English sentences, then introduce 2 key {target_language} terms from the headline with pronunciation. Specify WHICH terms and WHY they matter linguistically."
    },
    {
      "id": "grammar_focus",
      "type": "grammar",
      "title": "Title in {target_language}",
      "title_en": "Grammar in Action",
      "focus": "Teach 1-2 grammar patterns that appear naturally in this story — e.g. adjective-noun order, verb tense used in news reporting, genitive constructions, article gender agreement. Specify WHICH grammar pattern and WHICH words demonstrate it."
    },
    {
      "id": "vocabulary_deep_dive",
      "type": "vocabulary",
      "title": "Title in {target_language}",
      "title_en": "Vocabulary Deep Dive",
      "focus": "Deep treatment of 3-4 key terms: pronunciation, etymology, gender, multiple usage examples in different contexts. Specify WHICH terms and WHAT linguistic features each one teaches."
    },
    {
      "id": "usage_in_context",
      "type": "phrase_focus",
      "title": "Title in {target_language}",
      "title_en": "Professional Usage",
      "focus": "Teach 2-3 multi-word expressions used in professional/diplomatic settings. Show register differences (formal vs informal). Specify WHICH expressions and HOW they differ from everyday equivalents."
    },
    {
      "id": "recap",
      "type": "summary",
      "title": "Title in {target_language}",
      "title_en": "Quick Recap",
      "focus": "Reinforce the 3 most important terms/patterns from the lesson in 2 concise sentences."
    }
  ],
  "vocabulary_focus_terms": [
    {"term": "English term from the news", "pos": "noun/verb/phrase", "grammar_challenge": "Why this word is interesting for English speakers learning {target_language}"}
  ]
}
```

## Requirements

### Sections
- Produce exactly 5 sections in this order: `context_intro`, `grammar_focus`, `vocabulary_deep_dive`, `usage_in_context`, `recap`
- Each section's `focus` field MUST describe WHAT LINGUISTIC FEATURE is taught, not what news content is covered
- Section titles must be in {target_language}, natural and professional
- Section types must match: context_intro=narrative, grammar_focus=grammar, vocabulary_deep_dive=vocabulary, usage_in_context=phrase_focus, recap=summary

### Vocabulary Focus Terms
- List 4-6 terms from the news content that will be taught across the lesson
- Each term MUST include its part of speech AND a grammar challenge note explaining why it's linguistically interesting for English speakers
- Include a mix: nouns (with gender notes), verbs (with tense/conjugation notes), and domain-specific phrases
- Prioritize terms that reveal interesting {target_language} grammar patterns

### Tone
- This lesson is for senior professionals and government officials learning {target_language}
- Keep section titles authoritative and professional
- Think: diplomatic briefing language course, not beginner textbook
- Deliver information densely — these are senior academics who absorb language patterns quickly
- Avoid filler, unnecessary transitions, or over-explanation
