#!/usr/bin/env python3
"""
Opportunity Scanner v1.1 — Kevin Intelligence System
Multi-source market intelligence aggregator with resilient data fetching.
100% self-serviceable (no API keys, no human dependencies).

Usage:
    python3 scripts/intel/opportunity-scanner.py             # Full report
    python3 scripts/intel/opportunity-scanner.py --quick     # Quick overview
    python3 scripts/intel/opportunity-scanner.py --polymarket  # Prediction markets
    python3 scripts/intel/opportunity-scanner.py --output report.md
"""

import urllib.request
import json
import sys
import os
import time
from datetime import datetime, timezone
from typing import Any

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)
TIMEOUT = 15

def log(msg: str):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}")

def fetch_json(url: str) -> dict | list | None:
    """Fetch JSON with timeout and error handling."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; KevinIntel/1.0)"
        })
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log(f"  ⚠️  {url.split('/')[2][:30]}... {e.__class__.__name__}: {str(e)[:80]}")
        return None

def get_crypto_prices() -> dict:
    """Fetch BTC, ETH, SOL prices with 24h change."""
    data = fetch_json(
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum,solana&vs_currencies=usd"
        "&include_24hr_change=true"
    )
    if not data:
        return {}
    result = {}
    for coin, info in data.items():
        result[coin] = {
            "price": info.get("usd", 0),
            "change_24h": info.get("usd_24h_change", 0)
        }
    return result

def get_fear_greed() -> dict | None:
    """Fetch Fear & Greed Index."""
    data = fetch_json("https://api.alternative.me/fng/?limit=1")
    if data and data.get("data"):
        return data["data"][0]
    return None

def get_trending_coins() -> list:
    """Fetch trending coins from CoinGecko."""
    data = fetch_json(
        "https://api.coingecko.com/api/v3/search/trending"
    )
    if data and "coins" in data:
        coins = []
        for c in data["coins"][:10]:
            item = c.get("item", {})
            coins.append({
                "name": item.get("name", "?"),
                "symbol": item.get("symbol", "?"),
                "rank": item.get("market_cap_rank", "?"),
                "price_btc": item.get("price_btc", "?")
            })
        return coins
    return []

def get_polymarket_markets(query: str = None, tag: str = None, limit: int = 5) -> list:
    """Fetch Polymarket markets with fallback strategies."""
    results = []
    
    # NOTE: CLOB /markets endpoint is broken — returns 1000+ closed/stale markets
    # with no prices or volume. Skipping to Gamma API directly.
    
    # Strategy 1: Gamma Markets API (most reliable for active markets)
    try:
        url = "https://gamma-api.polymarket.com/events?limit=5&closed=false"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            events = json.loads(r.read().decode())
            if isinstance(events, list):
                for ev in events[:3]:
                    title = ev.get("title", "?")
                    mkts = ev.get("markets", ev.get("childMarkets", []))
                    for m in mkts[:2]:
                        results.append({
                            "question": m.get("question", title),
                            "prices": m.get("outcomePrices", "?"),
                            "volume": m.get("volume", "?") or ev.get("volume", "?"),
                            "source": "gamma"
                        })
                if results:
                    return results
    except Exception as e:
        log(f"  ⚠️  Gamma API: {e}")
    
    # Strategy 3: Use a public stats aggregator
    try:
        url = "https://polymarket-stats.vercel.app/api/markets?limit=5"
        req = urllib.request.Request(url, headers={"User-Agent": "KevinIntel/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            stats = json.loads(r.read().decode())
            if stats:
                mkts = stats if isinstance(stats, list) else stats.get("markets", [stats])
                for m in mkts[:limit]:
                    results.append({
                        "question": m.get("question", m.get("title", "?")),
                        "prices": str(m.get("outcomePrices", m.get("prices", "?"))),
                        "volume": m.get("volume24h", m.get("volume", "?")),
                        "source": "stats"
                    })
                return results
    except Exception as e:
        log(f"  ⚠️  Stats API: {e}")
    
    return results

def get_news_headlines() -> list:
    """Fetch crypto news headlines from public RSS-to-JSON."""
    try:
        url = "https://api.rss2json.com/v1/api.json?rss_url=https://cointelegraph.com/rss"
        req = urllib.request.Request(url, headers={"User-Agent": "KevinIntel/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode())
            if data.get("status") == "ok":
                items = data.get("items", [])
                headlines = []
                for item in items[:8]:
                    headlines.append({
                        "title": item.get("title", "?"),
                        "pub_date": item.get("pubDate", "?")[:19] if item.get("pubDate") else "?",
                        "link": item.get("link", "?")
                    })
                return headlines
    except Exception as e:
        log(f"  ⚠️  News: {e}")
    return []

def generate_report(prices: dict, fng: dict | None, trending: list, 
                    polymarkets: list, headlines: list) -> str:
    """Generate a formatted markdown report."""
    now = datetime.now(timezone.utc)
    
    lines = []
    lines.append(f"# Kevin Intelligence Report — {now.strftime('%B %d, %Y @ %H:%M UTC')}")
    lines.append(f"")
    
    # Market overview
    lines.append("## 📊 Market Overview")
    lines.append("| Asset | Price | 24h Change |")
    lines.append("|-------|-------|------------|")
    for coin in ["bitcoin", "ethereum", "solana"]:
        if coin in prices:
            p = prices[coin]
            symbol = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL"}[coin]
            ch = p.get("change_24h", 0)
            arrow = "🟢" if ch > 0 else "🔴"
            lines.append(f"| {symbol} | ${p['price']:,.0f} | {arrow} {ch:+.2f}% |")
    
    if fng:
        lines.append(f"\n**Fear & Greed**: {fng.get('value', '?')}/100 ({fng.get('value_classification', '?')})")
    
    # Trending
    if trending:
        lines.append("\n## 🔥 Trending Coins")
        for c in trending:
            rank = c.get("rank", "?")
            lines.append(f"- **{c['name']} ({c['symbol']})** — rank #{rank}")
    
    # Polymarket
    if polymarkets:
        lines.append("\n## 🎯 Prediction Markets")
        for m in polymarkets:
            q = m.get("question", "?")[:65]
            p_raw = m.get("prices", "?")
            # Parse outcomePrices as JSON array to show readable prices
            if isinstance(p_raw, str) and p_raw.startswith("["):
                try:
                    prices_list = json.loads(p_raw)
                    p_yes = float(prices_list[1]) * 100 if len(prices_list) > 1 else 0
                    p_no = float(prices_list[0]) * 100 if len(prices_list) > 0 else 0
                    p_str = f"Yes {p_yes:.1f}% / No {p_no:.1f}%"
                except:
                    p_str = str(p_raw)
            elif isinstance(p_raw, list):
                p_yes = float(p_raw[1]) * 100 if len(p_raw) > 1 else 0
                p_no = float(p_raw[0]) * 100 if len(p_raw) > 0 else 0
                p_str = f"Yes {p_yes:.1f}% / No {p_no:.1f}%"
            else:
                p_str = str(p_raw)
            vol = m.get('volume', '?')
            try:
                vol_str = f"${float(vol):,.0f}" if vol else "?"
            except:
                vol_str = str(vol)
            lines.append(f"- {q}")
            lines.append(f"  {p_str} | Vol: {vol_str}")
    
    if not polymarkets:
        lines.append("\n## 🎯 Prediction Markets")
        lines.append("*No markets found. API may be rate-limited.*")
    
    # News
    if headlines:
        lines.append("\n## 📰 Top Headlines")
        for h in headlines:
            lines.append(f"- [{h['title']}]({h['link']}) ({h['pub_date']})")
    
    # Market signals
    lines.append("\n## 💡 Signals")
    if fng:
        fng_val = int(fng.get("value", 50))
        if fng_val < 25:
            lines.append("- **🟢 Extreme Fear ({}/100)** — Historical contrarian buy signal".format(fng_val))
            lines.append("  Previous instances of <25: BTC 20-50% higher 3mo later")
        elif fng_val > 75:
            lines.append("- **🔴 Extreme Greed ({}/100)** — Caution, potential top".format(fng_val))
        else:
            lines.append("- Fear & Greed: {} — neutral zone".format(fng_val))
    
    lines.append(f"\n---")
    lines.append(f"*Generated by Kevin Intel System v1.1 | {now.strftime('%Y-%m-%dT%H:%M:%SZ')}*")
    
    return "\n".join(lines)

def main():
    quick = "--quick" in sys.argv
    output = None
    for i, arg in enumerate(sys.argv):
        if arg == "--output" and i + 1 < len(sys.argv):
            output = sys.argv[i + 1]
    
    log("🔍 Kevin Intelligence Scan Starting...")
    
    prices = get_crypto_prices()
    log(f"✓ Prices: {len(prices)} coins")
    
    fng = get_fear_greed()
    log(f"✓ Fear & Greed: {'got' if fng else 'failed'}")
    
    trending = get_trending_coins() if not quick else []
    log(f"✓ Trending: {len(trending)} coins")
    
    polymarkets = get_polymarket_markets()
    log(f"✓ Polymarket: {len(polymarkets)} markets")
    
    headlines = get_news_headlines() if not quick else []
    log(f"✓ News: {len(headlines)} headlines")
    
    report = generate_report(prices, fng, trending, polymarkets, headlines)
    
    if output:
        out_path = output if output.startswith("/") else os.path.join(os.getcwd(), output)
        with open(out_path, "w") as f:
            f.write(report)
        log(f"📄 Report saved: {out_path}")
    else:
        print("\n" + "=" * 60)
        print(report)
    
    # Also save with timestamp
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    auto_path = os.path.join(OUTPUT_DIR, f"intel_report_{ts}.md")
    with open(auto_path, "w") as f:
        f.write(report)
    log(f"📄 Auto-saved: {auto_path}")
    
    return report

if __name__ == "__main__":
    report = main()
