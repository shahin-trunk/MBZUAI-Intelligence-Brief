#!/usr/bin/env python3
"""Seed the entity_logos table with core entities.

Usage:
    python3.11 seed_entity_logos.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from supabase import create_client

# Add parent dir for env_loader
sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_loader import load_project_env

CORE_ENTITIES = [
    # UAE / Gulf
    {"entity_name": "MBZUAI", "aliases": ["Mohamed bin Zayed University of Artificial Intelligence"], "category": "university", "logo_path": "mbzuai.png"},
    {"entity_name": "ADNOC", "aliases": ["Abu Dhabi National Oil Company"], "category": "energy", "logo_path": "adnoc.png"},
    {"entity_name": "G42", "aliases": ["Group 42"], "category": "company", "logo_path": "g42.png"},
    {"entity_name": "TII", "aliases": ["Technology Innovation Institute"], "category": "org", "logo_path": "tii.png"},
    {"entity_name": "Mubadala", "aliases": ["Mubadala Investment Company"], "category": "finance", "logo_path": "mubadala.png"},
    {"entity_name": "KAUST", "aliases": ["King Abdullah University of Science and Technology"], "category": "university", "logo_path": "kaust.png"},
    {"entity_name": "Khalifa University", "aliases": [], "category": "university", "logo_path": "khalifa.png"},
    {"entity_name": "Presight", "aliases": ["Presight AI"], "category": "company", "logo_path": "presight.png"},
    {"entity_name": "Core42", "aliases": [], "category": "company", "logo_path": "core42.png"},
    {"entity_name": "ADIA", "aliases": ["Abu Dhabi Investment Authority"], "category": "finance", "logo_path": "adia.png"},
    {"entity_name": "ADQ", "aliases": [], "category": "finance", "logo_path": "adq.png"},
    {"entity_name": "Masdar", "aliases": [], "category": "energy", "logo_path": "masdar.png"},
    {"entity_name": "SDAIA", "aliases": ["Saudi Data and Artificial Intelligence Authority"], "category": "government", "logo_path": "sdaia.png"},

    # Big tech / AI labs
    {"entity_name": "NVIDIA", "aliases": ["Nvidia"], "category": "company", "logo_path": "nvidia.png"},
    {"entity_name": "OpenAI", "aliases": [], "category": "company", "logo_path": "openai.png"},
    {"entity_name": "Anthropic", "aliases": [], "category": "company", "logo_path": "anthropic.png"},
    {"entity_name": "Google", "aliases": ["Alphabet"], "category": "company", "logo_path": "google.png"},
    {"entity_name": "Google DeepMind", "aliases": ["DeepMind"], "category": "company", "logo_path": "deepmind.png"},
    {"entity_name": "Meta", "aliases": ["Meta AI", "Facebook"], "category": "company", "logo_path": "meta.png"},
    {"entity_name": "Microsoft", "aliases": [], "category": "company", "logo_path": "microsoft.png"},
    {"entity_name": "Apple", "aliases": [], "category": "company", "logo_path": "apple.png"},
    {"entity_name": "Amazon", "aliases": ["AWS", "Amazon Web Services"], "category": "company", "logo_path": "amazon.png"},
    {"entity_name": "xAI", "aliases": ["Grok"], "category": "company", "logo_path": "xai.png"},
    {"entity_name": "Mistral", "aliases": ["Mistral AI"], "category": "company", "logo_path": "mistral.png"},
    {"entity_name": "Cohere", "aliases": [], "category": "company", "logo_path": "cohere.png"},
    {"entity_name": "Hugging Face", "aliases": ["HuggingFace"], "category": "company", "logo_path": "huggingface.png"},

    # Chip / hardware
    {"entity_name": "TSMC", "aliases": ["Taiwan Semiconductor"], "category": "company", "logo_path": "tsmc.png"},
    {"entity_name": "Samsung", "aliases": ["Samsung Electronics"], "category": "company", "logo_path": "samsung.png"},
    {"entity_name": "Intel", "aliases": [], "category": "company", "logo_path": "intel.png"},
    {"entity_name": "AMD", "aliases": ["Advanced Micro Devices"], "category": "company", "logo_path": "amd.png"},
    {"entity_name": "Broadcom", "aliases": [], "category": "company", "logo_path": "broadcom.png"},
    {"entity_name": "Cerebras", "aliases": ["Cerebras Systems"], "category": "company", "logo_path": "cerebras.png"},
    {"entity_name": "Groq", "aliases": [], "category": "company", "logo_path": "groq.png"},

    # AI infra / startups
    {"entity_name": "Together AI", "aliases": ["Together"], "category": "company", "logo_path": "together.png"},
    {"entity_name": "Scale AI", "aliases": ["Scale"], "category": "company", "logo_path": "scaleai.png"},
    {"entity_name": "Firmus", "aliases": [], "category": "company", "logo_path": "firmus.png"},

    # Chinese AI
    {"entity_name": "Tencent", "aliases": [], "category": "company", "logo_path": "tencent.png"},
    {"entity_name": "Baidu", "aliases": [], "category": "company", "logo_path": "baidu.png"},
    {"entity_name": "ByteDance", "aliases": ["TikTok"], "category": "company", "logo_path": "bytedance.png"},
    {"entity_name": "DeepSeek", "aliases": [], "category": "company", "logo_path": "deepseek.png"},
    {"entity_name": "Zhipu AI", "aliases": ["GLM"], "category": "company", "logo_path": "zhipu.png"},

    # Government
    {"entity_name": "UAE Government", "aliases": ["United Arab Emirates"], "category": "government", "logo_path": "uae.png"},
    {"entity_name": "Saudi Arabia", "aliases": ["Saudi Arabia Government", "Kingdom of Saudi Arabia"], "category": "government", "logo_path": "saudi.png"},
    {"entity_name": "Abu Dhabi Government", "aliases": ["Abu Dhabi"], "category": "government", "logo_path": "abudhabi.png"},

    # Other
    {"entity_name": "ASPIRE", "aliases": [], "category": "org", "logo_path": "aspire.png"},
    {"entity_name": "ATRC", "aliases": ["Advanced Technology Research Council"], "category": "org", "logo_path": "atrc.png"},
    {"entity_name": "DEWA", "aliases": ["Dubai Electricity and Water Authority"], "category": "energy", "logo_path": "dewa.png"},
]


def main() -> None:
    for env_path in load_project_env():
        print(f"Loaded env from {env_path}")

    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing Supabase credentials")
        sys.exit(1)

    sb = create_client(url, key)

    for entity in CORE_ENTITIES:
        sb.table("entity_logos").upsert(entity, on_conflict="entity_name").execute()
        print(f"  Seeded: {entity['entity_name']}")

    print(f"\nDone: {len(CORE_ENTITIES)} entities seeded.")


if __name__ == "__main__":
    main()
