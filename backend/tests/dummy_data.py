"""Dummy data fixtures for exhibit/model-release tests."""

# ---------------------------------------------------------------------------
# Model release detection: clear launches (should return True)
# ---------------------------------------------------------------------------

CLEAR_LAUNCH_OPENAI = {
    "headline": "OpenAI launches GPT-6 with API access and developer tooling",
    "raw_content": (
        "OpenAI released GPT-6, its most capable model to date, with full API access, "
        "a 512K context window, and pricing at $2.50 per million input tokens. The model "
        "is available today via the API and ChatGPT. Benchmarks show GPT-6 scoring 96% "
        "on GPQA Diamond and 62% on SWE-bench Pro."
    ),
    "summary": "OpenAI released GPT-6 with API access.",
    "brief_section": "Model Releases & Technical Developments",
    "entities": ["OpenAI", "GPT-6"],
    "source_url": "https://openai.com/blog/gpt-6",
    "category": "model_release",
}

CLEAR_LAUNCH_GOOGLE = {
    "headline": "Google releases Gemini 3 Pro and Flash via Vertex AI and Google AI Studio",
    "raw_content": (
        "Google DeepMind launched Gemini 3 Pro and Flash, available via Vertex AI, "
        "Google AI Studio, and the Gemini API. Flash is optimized for low-latency tasks "
        "with pricing at $0.15 per million input tokens."
    ),
    "summary": "Google released Gemini 3 Pro and Flash.",
    "brief_section": "Model Releases & Technical Developments",
    "entities": ["Google", "Gemini 3 Pro", "Gemini 3 Flash"],
    "source_url": "https://ai.google.dev/gemini-3",
    "category": "model_release",
}

# ---------------------------------------------------------------------------
# Model release detection: non-launches (should return False)
# ---------------------------------------------------------------------------

NON_LAUNCH_FUNDING = {
    "headline": "Mistral raises $2B in Series C to expand foundation model capabilities",
    "raw_content": (
        "Mistral AI has secured $2 billion in Series C funding led by Andreessen Horowitz. "
        "The company plans to use the funds to scale its pre-training infrastructure."
    ),
    "summary": "Mistral raised $2B in funding.",
    "brief_section": "International Business & Technology",
    "entities": ["Mistral"],
    "source_url": "https://techcrunch.com/mistral-series-c",
    "category": "funding",
}

NON_LAUNCH_RESEARCH = {
    "headline": "New benchmark study reveals LLM reasoning limits on complex tasks",
    "raw_content": (
        "Researchers from MIT published a paper on arxiv evaluating LLM reasoning "
        "capabilities across 15 tasks. The study found significant gaps in multi-step "
        "logical deduction."
    ),
    "summary": "Research paper on LLM reasoning limits.",
    "brief_section": "Model Releases & Technical Developments",
    "entities": ["MIT"],
    "source_url": "https://arxiv.org/abs/2026.12345",
    "category": "research",
}

NON_LAUNCH_MARKET = {
    "headline": "AI companies see record weekly token consumption across major platforms",
    "raw_content": (
        "Weekly usage data shows record token consumption volume across major "
        "AI platforms, with total API calls reaching 5 trillion tokens this week."
    ),
    "summary": "Record weekly token usage across platforms.",
    "brief_section": "International Business & Technology",
    "entities": ["AI platforms"],
    "source_url": "https://analytics.example/weekly-rankings",
    "category": "market",
}

# ---------------------------------------------------------------------------
# Model release detection: ambiguous (should return None)
# ---------------------------------------------------------------------------

AMBIGUOUS_OPEN_WEIGHT = {
    "headline": "Startup open-sources new Llama-derived model on HuggingFace",
    "raw_content": (
        "A startup has released an open-source model derived from Llama on HuggingFace. "
        "The model shows promising results on common benchmarks."
    ),
    "summary": "Startup open-sourced a Llama-derived model.",
    "brief_section": "Model Releases & Technical Developments",
    "entities": ["StartupAI"],
    "source_url": "https://example.com/blog/open-source-model",
    "category": "model_release",
}

AMBIGUOUS_FUNDING_PLUS_LAUNCH = {
    "headline": "AI startup raises $500M and launches new reasoning model via API",
    "raw_content": (
        "The company raised $500 million in Series B and simultaneously released "
        "Model X via API with benchmark results showing 72% on SWE-bench Verified."
    ),
    "summary": "Company raised funding and released a model.",
    "brief_section": "International Business & Technology",
    "entities": ["Model X"],
    "source_url": "https://techcrunch.com/startup-model-x",
    "category": "business",
}

# ---------------------------------------------------------------------------
# Benchmark table extraction: standard markdown table
# ---------------------------------------------------------------------------

ITEM_WITH_STANDARD_TABLE = {
    "headline": "OpenAI releases GPT-5.4 mini and nano for agentic workloads",
    "entities": ["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "raw_content": "OpenAI released GPT-5.4 mini and nano.",
    "enriched_sources": [
        {
            "url": "https://openai.com/index/gpt-5-4-mini-nano/",
            "title": "Introducing GPT-5.4 mini and nano - OpenAI",
            "extract": (
                "Today we're releasing GPT-5.4 mini and nano.\n"
                "| | GPT-5.4 (flagship) | GPT-5.4 mini | GPT-5.4 nano |\n"
                "|---|---|---|---|\n"
                "| SWE-Bench Pro | 57.7% | 54.4% | 52.4% |\n"
                "| GPQA Diamond | 93.0% | 88.0% | 82.8% |\n"
            ),
        }
    ],
}

# ---------------------------------------------------------------------------
# Benchmark table extraction: inline table (single-line)
# ---------------------------------------------------------------------------

ITEM_WITH_INLINE_TABLE = {
    "headline": "OpenAI releases GPT-5.4 mini and nano for agentic workloads",
    "entities": ["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "raw_content": "OpenAI released GPT-5.4 mini and nano.",
    "enriched_sources": [
        {
            "url": "https://openai.com/index/gpt-5-4-mini-nano/",
            "title": "Introducing GPT-5.4 mini and nano - OpenAI",
            "extract": (
                "Today we're releasing GPT-5.4 mini and nano. "
                "| GPT-5.4 (flagship) | GPT-5.4 mini | GPT-5.4 nano | GPT-5 mini | | "
                "|---|---|---|---|---| "
                "| SWE-Bench Pro | 57.7% | 54.4% | 52.4% | 45.7% | "
                "| Terminal-Bench 2.0 | 75.1% | 60.0% | 46.3% | 38.2% | "
                "| Toolathlon | 54.6% | 42.9% | 35.5% | 26.9% | "
                "| GPQA Diamond | 93.0% | 88.0% | 82.8% | 81.6% | "
                "| OSWorld-Verified | 75.0% | 72.1% | 39.0% | 42.0% | "
                "GPT-5.4 mini costs $0.75 per 1M input tokens and $4.50 per 1M output tokens. "
                "GPT-5.4 nano costs $0.20 per 1M input tokens and $1.25 per 1M output tokens. "
                "GPT-5.4 mini has a 400K context window."
            ),
        }
    ],
}

# ---------------------------------------------------------------------------
# No table present
# ---------------------------------------------------------------------------

ITEM_NO_TABLE = {
    "headline": "Claude 5 achieves strong performance on coding tasks",
    "entities": ["Anthropic", "Claude 5"],
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "raw_content": (
        "Anthropic's Claude 5 reportedly scores well on SWE-bench Pro and GPQA Diamond, "
        "though exact figures were not released in table format."
    ),
    "enriched_sources": [],
}

# ---------------------------------------------------------------------------
# Noisy model labels
# ---------------------------------------------------------------------------

ITEM_NOISY_LABELS = {
    "headline": "OpenAI releases GPT-5.4 mini and nano for agentic workloads",
    "entities": ["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "raw_content": "OpenAI released GPT-5.4 mini and nano for fast, low-cost agentic workloads.",
    "enriched_sources": [
        {
            "url": "https://www.zdnet.com/article/gpt-5-4-mini-and-nano/",
            "title": "OpenAI's GPT-5.4 mini and nano launch",
            "extract": (
                "GPQA Diamond results show GPT-5.4 mini score 88.01%, approaching GPT-5.4 "
                "at 93.00%. Terminal-Bench: GPT-5.4 mini reaches 60.00% versus 38.20% for "
                "GPT-5 mini."
            ),
        },
    ],
}

# ---------------------------------------------------------------------------
# Key number extraction fixtures
# ---------------------------------------------------------------------------

ITEM_DIRECT_PRICING = {
    "headline": "Model X released",
    "entities": ["Model X mini"],
    "is_model_release": True,
    "raw_content": "",
    "enriched_sources": [
        {"url": "https://example.com", "extract": "Model X mini costs $0.75/$4.50 per million tokens."}
    ],
}

ITEM_COMPACT_PRICING = {
    "headline": "Model X released",
    "entities": ["Model X mini"],
    "is_model_release": True,
    "raw_content": "",
    "enriched_sources": [
        {"url": "https://example.com", "extract": "Price $0.75\u2022$4.5 Input\u2022Output."}
    ],
}

ITEM_LONG_FORM_PRICING = {
    "headline": "Model X released",
    "entities": ["Model X mini"],
    "is_model_release": True,
    "raw_content": "",
    "enriched_sources": [
        {
            "url": "https://example.com",
            "extract": "Model X mini costs $0.75 per 1M input tokens and $4.50 per 1M output tokens.",
        }
    ],
}

ITEM_CONTEXT_WINDOW = {
    "headline": "Model X released",
    "entities": ["Model X mini"],
    "is_model_release": True,
    "raw_content": "",
    "enriched_sources": [
        {"url": "https://example.com", "extract": "Model X mini has a 400,000-token context window."},
        {"url": "https://example2.com", "extract": "Context window 400K tokens."},
    ],
}

ITEM_SPEED = {
    "headline": "Model X released",
    "entities": ["Model X mini"],
    "is_model_release": True,
    "raw_content": "",
    "enriched_sources": [
        {"url": "https://example.com", "extract": "Model X mini runs about 2X faster than its predecessor."}
    ],
}

# ---------------------------------------------------------------------------
# Coverage notes
# ---------------------------------------------------------------------------

ITEM_COVERAGE_NOT_DISCLOSED = {
    "headline": "Model Y released",
    "entities": [],
    "is_model_release": True,
    "raw_content": "Pricing not disclosed. The model's training data was not disclosed.",
    "enriched_sources": [],
}

ITEM_COVERAGE_API_ONLY = {
    "headline": "Model Y released",
    "entities": [],
    "is_model_release": True,
    "raw_content": "The nano variant is API-only, with availability not yet announced.",
    "enriched_sources": [],
}

# ---------------------------------------------------------------------------
# Validation test data
# ---------------------------------------------------------------------------

VALIDATION_SOURCE_ITEM = {
    "is_model_release": True,
    "benchmark_facts": [
        {"benchmark": "SWE-bench Pro", "model": "GPT-5.4 mini", "score": "54.38%"},
        {"benchmark": "SWE-bench Pro", "model": "GPT-5.4 nano", "score": "52.39%"},
        {"benchmark": "SWE-bench Pro", "model": "GPT-5 mini", "score": "45.69%"},
        {"benchmark": "OSWorld-Verified", "model": "GPT-5.4 mini", "score": "72.13%"},
        {"benchmark": "OSWorld-Verified", "model": "GPT-5.4 nano", "score": "39.0%"},
        {"benchmark": "MMLU", "model": "GPT-5.4 mini", "score": "86.2%"},
    ],
    "key_number_facts": [
        {"label": "Pricing (mini)", "kind": "pricing"},
        {"label": "Context (mini)", "kind": "context"},
        {"label": "Speed (mini)", "kind": "speed"},
    ],
}

VALIDATION_INCOMPLETE_OUTPUT = {
    "model_release_data": {
        "key_numbers": [
            {"label": "Pricing (mini)", "value": "$0.75/$4.50"},
            {"label": "Context (mini)", "value": "400K"},
        ],
        "benchmarks": {
            "rows": [
                {"benchmark": "SWE-bench Pro", "scores": ["54.38%", "—", "—"]},
                {"benchmark": "OSWorld-Verified", "scores": ["72.13%", "—", "42.0%"]},
            ]
        },
    }
}

VALIDATION_COMPLETE_OUTPUT = {
    "model_release_data": {
        "key_numbers": [
            {"label": "Pricing (mini)", "value": "$0.75/$4.50"},
            {"label": "Context (mini)", "value": "400K"},
            {"label": "Speed (mini)", "value": "~2x"},
        ],
        "benchmarks": {
            "rows": [
                {"benchmark": "SWE-bench Pro", "scores": ["54.38%", "52.39%", "45.69%"]},
                {"benchmark": "OSWorld-Verified", "scores": ["72.13%", "39.0%", "—"]},
                {"benchmark": "MMLU", "scores": ["86.2%"]},
            ]
        },
    }
}

# ---------------------------------------------------------------------------
# Full enriched item for packet assembly
# ---------------------------------------------------------------------------

ENRICHED_MINI_NANO_ITEM = {
    "headline": "OpenAI releases GPT-5.4 mini and nano for agentic workloads",
    "entities": ["OpenAI", "GPT-5.4 mini", "GPT-5.4 nano"],
    "brief_section": "Model Releases & Technical Developments",
    "is_model_release": True,
    "raw_content": (
        "OpenAI released GPT-5.4 mini and nano, smaller models designed for "
        "high-volume workloads with faster speeds and lower cost. GPT-5.4 mini "
        "improves substantially over GPT-5 mini and approaches larger GPT-5.4 "
        "performance on benchmarks, while GPT-5.4 nano targets lightweight tasks "
        "like classification and extraction."
    ),
    "enriched_sources": [
        {
            "url": "https://thenewstack.io/gpt-54-nano-mini/",
            "title": "OpenAI's GPT-5.4 mini and nano",
            "extract": (
                "GPT-5.4 mini is available in the API, Codex, and ChatGPT. It has a "
                "400,000-token context window and costs $0.75 per million input tokens "
                "and $4.50 per million output tokens. GPT-5.4 nano is API-only at "
                "$0.20 per million input tokens and $1.25 per million output tokens. "
                "On SWE-bench Pro, mini scores 54.38%, only 3 percentage points behind "
                "the full GPT-5.4. On OSWorld-Verified, mini scores 72.13%, almost "
                "matching the flagship model's 75.03%. Nano scores lower on "
                "OSWorld-Verified (39.01% vs. 42%). GPT-5.4 mini runs about 2X faster "
                "than GPT-5 mini."
            ),
        },
    ],
    "_enrichment": {},
}

# ---------------------------------------------------------------------------
# Format mismatch: backend vs frontend benchmark table shapes
# ---------------------------------------------------------------------------

BACKEND_BENCHMARK_TABLE = {
    "type": "benchmark_table",
    "data": {
        "models": ["GPT-5.4", "Claude 4"],
        "highlighted_model_index": 0,
        "highlighted_model_indexes": [0],
        "rows": [
            {"benchmark": "MMLU", "scores": ["90%", "89%"]},
            {"benchmark": "GPQA Diamond", "scores": ["93%", "91%"]},
        ],
        "summary": "GPT-5.4 leads on both benchmarks.",
    },
}

FRONTEND_BENCHMARK_TABLE = {
    "type": "benchmark_table",
    "data": {
        "columns": ["GPT-5.4", "Claude 4"],
        "rows": [
            {"benchmark": "MMLU", "scores": {"GPT-5.4": "90%", "Claude 4": "89%"}},
            {"benchmark": "GPQA Diamond", "scores": {"GPT-5.4": "93%", "Claude 4": "91%"}},
        ],
    },
}

# ---------------------------------------------------------------------------
# Truncated editor JSON
# ---------------------------------------------------------------------------

TRUNCATED_JSON_MID_ITEMS = (
    '{"final_brief": {"brief_metadata": {"date": "2026-04-09", "generated_at": "2026-04-09T08:00:00Z", '
    '"total_items": 2, "section_counts": {"UAE": 1}, "lead_story_id": "001"}, '
    '"items": [{"id": "001", "rank": 1, "section": "UAE", "headline": "Test Item One", '
    '"source_domain": "example.com", "source_name": "Example", "source_url": "https://example.com", '
    '"key_bullets": ["bullet 1"], "analysis": "analysis text", "exhibits": [{"type": "benchmark_table", '
    '"data": {"models": ["A"], "rows": [{"benchmark": "MMLU", "scores": ["90%"]}]}}], '
    '"main_bullet": "", "context": "", "implication": "", "entities": [], "category": "tech", '
    '"composite_score": 0.9, "is_model_release": true, "depth": "full"}, '
    '{"id": "002", "rank": 2, "section": "UAE", "headline": "Test Item Two'
)

TRUNCATED_JSON_MID_EXHIBIT = (
    '{"final_brief": {"brief_metadata": {"date": "2026-04-09", "generated_at": "2026-04-09T08:00:00Z", '
    '"total_items": 1, "section_counts": {"UAE": 1}, "lead_story_id": "001"}, '
    '"items": [{"id": "001", "rank": 1, "section": "UAE", "headline": "Test", '
    '"source_domain": "example.com", "source_name": "Example", "source_url": "https://example.com", '
    '"key_bullets": ["bullet"], "analysis": "text", "exhibits": [{"type": "benchmark_table", '
    '"data": {"models": ["A"'
)

# ---------------------------------------------------------------------------
# Search slot reservation candidates
# ---------------------------------------------------------------------------

SEARCH_CANDIDATES = [
    {
        "link": "https://random.example/news",
        "title": "General roundup",
        "snippet": "Overview of the launch",
        "classified_intents": [],
    },
    {
        "link": "https://openai.com/index/gpt-5-4-mini-nano",
        "title": "OpenAI announcement",
        "snippet": "Official announcement and model card",
        "classified_intents": ["official", "pricing"],
    },
    {
        "link": "https://benchmarks.example/gpt-5-4-mini",
        "title": "Benchmark analysis",
        "snippet": "SWE-bench and OSWorld evaluation",
        "classified_intents": ["benchmark"],
    },
    {
        "link": "https://pricing.example/gpt-5-4-mini",
        "title": "API pricing",
        "snippet": "Pricing and availability details",
        "classified_intents": ["pricing"],
    },
    {
        "link": "https://review1.example/gpt-5-4",
        "title": "Review one",
        "snippet": "A review",
        "classified_intents": [],
    },
    {
        "link": "https://review2.example/gpt-5-4",
        "title": "Review two",
        "snippet": "Another review",
        "classified_intents": [],
    },
]

# ---------------------------------------------------------------------------
# GhostwriterOutput-shaped dict for Pydantic roundtrip
# ---------------------------------------------------------------------------

GHOSTWRITER_OUTPUT_WITH_EXHIBITS = {
    "date": "2026-04-09",
    "items": [
        {
            "id": "001",
            "rank": 1,
            "section": "Model Releases & Technical Developments",
            "headline": "OpenAI launches GPT-6",
            "source_domain": "openai.com",
            "source_name": "OpenAI",
            "source_url": "https://openai.com/gpt-6",
            "key_bullets": ["Scores 96% on GPQA Diamond", "API access available"],
            "analysis": "GPT-6 represents a significant leap.",
            "primary_entity": "OpenAI",
            "exhibits": [
                {
                    "type": "benchmark_table",
                    "data": {
                        "models": ["GPT-6", "GPT-5.4"],
                        "highlighted_model_index": 0,
                        "highlighted_model_indexes": [0],
                        "rows": [
                            {"benchmark": "GPQA Diamond", "scores": ["96%", "93%"]},
                            {"benchmark": "SWE-bench Pro", "scores": ["62%", "57%"]},
                        ],
                    },
                }
            ],
            "entities": ["OpenAI", "GPT-6"],
            "category": "model_release",
            "composite_score": 0.95,
            "is_model_release": True,
            "model_release_data": {
                "developer": "OpenAI",
                "model_name": "GPT-6",
                "summary_pitch": "Most capable model to date.",
                "key_numbers": [
                    {"label": "Pricing", "value": "$2.50/$10.00"},
                    {"label": "Context", "value": "512K"},
                ],
                "benchmarks": {
                    "models": ["GPT-6", "GPT-5.4"],
                    "highlighted_model_index": 0,
                    "highlighted_model_indexes": [0],
                    "rows": [
                        {"benchmark": "GPQA Diamond", "scores": ["96%", "93%"]},
                        {"benchmark": "SWE-bench Pro", "scores": ["62%", "57%"]},
                    ],
                },
            },
            "depth": "full",
        }
    ],
}
