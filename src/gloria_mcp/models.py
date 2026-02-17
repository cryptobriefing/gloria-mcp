"""Response formatting helpers — strip paid fields, build payment instructions."""

from datetime import datetime, timezone

X402_BASE = "https://api.itsgloria.ai"

FREE_NEWS_FIELDS = [
    "id",
    "signal",
    "sentiment",
    "sentiment_value",
    "timestamp",
    "feed_categories",
    "sources",
    "author",
    "tokens",
    "tweet_url",
]


def truncate_news(item: dict) -> dict:
    """Return only free-tier fields from a news item."""
    return {k: item[k] for k in FREE_NEWS_FIELDS if k in item}


def format_recap(item: dict) -> dict:
    """Pass through recap — all fields are free tier."""
    return {
        "feed_category": item.get("feed_category"),
        "timeframe": item.get("timeframe"),
        "recap": item.get("recap"),
        "created_at": item.get("created_at"),
    }


def enriched_news_payment_info() -> dict:
    return {
        "payment_required": True,
        "protocol": "x402",
        "description": (
            "Get enriched news with full AI-generated context, entity analysis, "
            "and token mentions. Includes long_context and short_context fields "
            "omitted from the free tier."
        ),
        "endpoint": f"{X402_BASE}/news",
        "method": "GET",
        "required_params": {
            "feed_categories": "Category code (e.g. 'bitcoin', 'defi', 'ai')"
        },
        "optional_params": {
            "from_date": "YYYY-MM-DD",
            "to_date": "YYYY-MM-DD",
            "limit": "1-10, default 10",
            "page": "Page number, default 1",
        },
        "price": "USDC on Base — exact amount returned in HTTP 402 response",
        "how_to_pay": (
            "Send a GET request to the endpoint. You'll receive an HTTP 402 "
            "response with payment details. Complete the USDC payment on Base "
            "network, then retry with the payment proof header."
        ),
    }


def ticker_summary_payment_info() -> dict:
    return {
        "payment_required": True,
        "protocol": "x402",
        "description": (
            "Get a comprehensive 24-hour AI-generated summary for any crypto "
            "ticker or topic. Combines Gloria's curated news with web search "
            "for decision-grade bullet points."
        ),
        "endpoint": f"{X402_BASE}/news-ticker-summary",
        "method": "GET",
        "required_params": {
            "ticker": "Ticker symbol or topic name (e.g. 'SOL', 'LayerZero', 'ETH')"
        },
        "price": "USDC on Base — exact amount returned in HTTP 402 response",
        "how_to_pay": (
            "Send a GET request to the endpoint. You'll receive an HTTP 402 "
            "response with payment details. Complete the USDC payment on Base "
            "network, then retry with the payment proof header."
        ),
    }
