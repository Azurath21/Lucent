import argparse
import json
import sys
import os

from .facebook_scraper_manager import FacebookScraperManager


def main():
    parser = argparse.ArgumentParser(description="CLI wrapper for Facebook Marketplace scraper that outputs JSON")
    parser.add_argument("--item", required=True, help="Main item name to search for (required)")
    parser.add_argument("--brand", default="", help="Brand to include in search keywords")
    parser.add_argument("--model", default="", help="Model to include in search keywords")
    parser.add_argument("--notes", default="", help="Additional notes/keywords to include in search")
    parser.add_argument("--min_price", default="0", help="Minimum price filter")
    parser.add_argument("--max_price", default="", help="Maximum price filter")
    parser.add_argument("--condition", default="new", help="Condition filter: new, used, all")
    parser.add_argument("--location", default="singapore", help="Location for search")
    parser.add_argument("--days", type=int, default=30, help="Days since listed filter")
    args = parser.parse_args()

    search_term_parts = [args.item.strip()]
    if args.brand.strip():
        search_term_parts.append(args.brand.strip())
    if args.model.strip():
        search_term_parts.append(args.model.strip())
    if args.notes.strip():
        search_term_parts.append(args.notes.strip())
    search_term = " ".join(search_term_parts)

    os.makedirs("raw", exist_ok=True)
    os.makedirs("processed", exist_ok=True)

    try:
        manager = FacebookScraperManager(
            item=search_term,
            min_price=args.min_price,
            max_price=args.max_price,
            condition=args.condition,
            location=args.location,
            days_since_listed=args.days
        )
        
        result = manager.scrape_with_fallback()
        
        out = {
            "ok": result.get('count', 0) > 0,
            "query_url": f"https://www.facebook.com/marketplace/search/?query={search_term.replace(' ', '%20')}",
            "count": result.get('count', 0),
            "csv_path": result.get('csv_path', ''),
            "screenshot_path": "",
            "strategies_tried": result.get('status', 'completed')
        }
        print(json.dumps(out))
        
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
