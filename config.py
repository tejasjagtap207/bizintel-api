"""
config.py — All settings in one place
Tu hyala change kar nahi, fakt .env file madhe values change kar
"""

import os
from dotenv import load_dotenv

load_dotenv()

# === APP ===
APP_NAME = "BizIntel API"
APP_VERSION = "1.0.0"
PORT = int(os.getenv("PORT", 8000))

# === DATABASE ===
# SQLite for local, PostgreSQL for Render production
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bizintel.db")

# === OPENAI (for LLM wrapper) ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", 2000))

# === PRICING TIERS ===
TIERS = {
    "free": {
        "price": 0,
        "requests_per_month": 50,
        "features": ["basic_lookup", "quick_scan"],
        "data_depth": "basic",
        "description": "50 free requests/month. Basic data only."
    },
    "pro": {
        "price": 49,
        "requests_per_month": 2000,
        "features": ["basic_lookup", "quick_scan", "full_enrichment",
                      "seo_analysis", "tech_detection", "email_finder"],
        "data_depth": "full",
        "description": "2000 requests. Full intelligence + SEO + Tech stack."
    },
    "business": {
        "price": 199,
        "requests_per_month": 10000,
        "features": ["basic_lookup", "quick_scan", "full_enrichment",
                      "seo_analysis", "tech_detection", "email_finder",
                      "competitor_analysis", "content_analysis", "business_signals"],
        "data_depth": "deep",
        "description": "10K requests. Deep analysis + Everything included."
    },
    "enterprise": {
        "price": 999,
        "requests_per_month": -1,  # Unlimited
        "features": ["basic_lookup", "quick_scan", "full_enrichment",
                      "seo_analysis", "tech_detection", "email_finder",
                      "competitor_analysis", "content_analysis", "business_signals",
                      "custom_endpoints", "white_label", "priority_support"],
        "data_depth": "maximum",
        "description": "Unlimited. Custom everything. White label option."
    }
}

# === RATE LIMITS ===
RATE_LIMIT_FREE = 10  # requests per minute
RATE_LIMIT_PRO = 60
RATE_LIMIT_BUSINESS = 120
RATE_LIMIT_ENTERPRISE = 300