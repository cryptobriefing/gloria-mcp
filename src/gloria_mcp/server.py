"""Gloria AI MCP Server — curated crypto news for AI agents."""

import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from gloria_mcp.client import GloriaClient
from gloria_mcp.models import (
    enriched_news_payment_info,
    format_recap,
    ticker_summary_payment_info,
    truncate_news,
)

load_dotenv()

mcp = FastMCP(
    "Gloria AI",
    instructions=(
        "Real-time curated crypto news from Gloria AI. "
        "Covers 18 categories including Bitcoin, Ethereum, DeFi, AI, Solana, and more. "
        "News is sourced from crypto Twitter, filtered by AI for relevance, "
        "and enriched with sentiment analysis and entity extraction. "
        "Use get_categories to discover available topics, then get_latest_news "
        "or get_news_recap for data. Paid tools return x402 payment instructions."
    ),
)

_client: GloriaClient | None = None


def _get_client() -> GloriaClient:
    global _client
    if _client is None:
        token = os.environ.get("GLORIA_API_TOKEN", "")
        base_url = os.environ.get("AI_HUB_BASE_URL", "https://ai-hub.cryptobriefing.com")
        if not token:
            raise RuntimeError("GLORIA_API_TOKEN environment variable is required")
        _client = GloriaClient(base_url, token)
    return _client


# ---------------------------------------------------------------------------
# Free tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_latest_news(category: str | None = None, limit: int = 5) -> list[dict]:
    """Get the latest curated crypto news headlines.

    Returns real-time news items with headline, sentiment, categories, and sources.
    Use the category parameter to filter by topic (e.g. 'bitcoin', 'defi', 'ai').
    Call get_categories first to see all available category codes.

    Args:
        category: Filter by category code (e.g. 'bitcoin', 'ethereum', 'defi', 'ai').
                  Omit to get news across all categories.
        limit: Number of items to return (1-10, default 5).
    """
    limit = max(1, min(10, limit))
    items = await _get_client().get_news(category=category, limit=limit)
    return [truncate_news(item) for item in items]


@mcp.tool()
async def get_news_recap(category: str, timeframe: str = "12h") -> dict:
    """Get an AI-generated news recap/summary for a specific category.

    Returns a concise narrative summarizing the most important recent news
    for the given category. Great for getting up to speed quickly.

    Args:
        category: Category code (required). Use get_categories to see options.
                  Popular choices: 'crypto', 'bitcoin', 'ethereum', 'defi', 'ai', 'macro'.
        timeframe: Time window for the recap. Use '1h' for crypto/macro (updated hourly),
                   '8h' or '24h' for other categories. Default '12h'.
    """
    result = await _get_client().get_recap(category=category, timeframe=timeframe)
    if result is None:
        return {"error": f"No recap found for category '{category}' with timeframe '{timeframe}'."}
    return format_recap(result)


@mcp.tool()
async def search_news(query: str, limit: int = 5) -> list[dict]:
    """Search curated crypto news by keyword.

    Searches across all news items for matching content. Returns headlines,
    sentiment, categories, and sources.

    Args:
        query: Search keyword or phrase (e.g. 'ETF', 'SEC', 'Uniswap').
        limit: Number of results to return (1-5, default 5).
    """
    limit = max(1, min(5, limit))
    items = await _get_client().get_news(keyword=query, limit=limit)
    return [truncate_news(item) for item in items]


@mcp.tool()
async def get_categories() -> list[dict]:
    """List all available news categories with their recap timeframes.

    Returns category codes that can be used with get_latest_news, get_news_recap,
    and other tools. Each category includes its code, display name, and how
    frequently recaps are generated.
    """
    return await _get_client().get_categories()


@mcp.tool()
async def get_news_item(id: str) -> dict:
    """Get a specific news item by its ID.

    Returns the full free-tier details for a single news item including
    headline, sentiment, categories, sources, and tweet URL.

    Args:
        id: The news item ID (returned in results from get_latest_news or search_news).
    """
    item = await _get_client().get_news_by_id(id)
    if item is None:
        return {"error": f"News item '{id}' not found."}
    return truncate_news(item)


# ---------------------------------------------------------------------------
# Paid tools (return x402 payment instructions)
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_enriched_news() -> dict:
    """Get enriched news with full AI-generated context and analysis (paid via x402).

    This premium endpoint returns the complete news data including:
    - long_context: Detailed AI-generated context about the news event
    - short_context: Brief contextual summary
    - Full entity analysis and token mentions

    Payment is handled via the x402 protocol using USDC on Base network.
    This tool returns the payment endpoint and instructions.
    """
    return enriched_news_payment_info()


@mcp.tool()
async def get_ticker_summary() -> dict:
    """Get a 24-hour AI-generated summary for any crypto ticker or topic (paid via x402).

    Returns decision-grade bullet points combining Gloria's curated news
    with real-time web search. Designed for fund managers and trading agents.

    Payment is handled via the x402 protocol using USDC on Base network.
    This tool returns the payment endpoint and instructions.
    """
    return ticker_summary_payment_info()


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("gloria://about")
async def about() -> str:
    """About Gloria AI and its data coverage."""
    return (
        "Gloria AI is a real-time crypto intelligence platform that curates news "
        "from crypto Twitter. Every item passes through a multi-stage AI pipeline:\n\n"
        "1. Ingestion from 100+ curated Twitter accounts\n"
        "2. Multi-topic filtering (single-event focus)\n"
        "3. Duplicate detection via embeddings + keyword matching\n"
        "4. Newsworthiness scoring by AI curator\n"
        "5. Category classification across 18 topics\n"
        "6. Sentiment analysis and entity extraction\n"
        "7. AI-generated headlines and context\n\n"
        "Coverage: Bitcoin, Ethereum, DeFi, AI/ML, Solana, Base, Macro, "
        "Ripple, RWA, Perps, Hyperliquid, and more.\n\n"
        "Update frequency: News items appear within ~2-3 minutes of the original tweet. "
        "Recaps are generated hourly for crypto/macro, every 8-24h for other categories.\n\n"
        "Free tier: Headlines, sentiment, categories, sources.\n"
        "Paid tier (x402): Full context, entity analysis, ticker summaries.\n\n"
        "Website: https://itsgloria.ai\n"
        "API docs: https://cryptobriefing.com/llms.txt"
    )


@mcp.resource("gloria://categories")
async def categories_resource() -> str:
    """Current feed categories with descriptions."""
    try:
        cats = await _get_client().get_categories()
        lines = ["Available Gloria AI news categories:\n"]
        for cat in cats:
            recap = cat.get("recap_timeframe")
            recap_info = f" (recaps every {recap})" if recap else " (no recaps)"
            lines.append(f"- {cat['code']}: {cat['name']}{recap_info}")
        return "\n".join(lines)
    except Exception:
        return "Categories temporarily unavailable. Use the get_categories tool instead."


def main():
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "streamable-http":
        port = int(os.environ.get("MCP_PORT", "8005"))
        mcp.settings.port = port
        mcp.settings.host = "0.0.0.0"
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
