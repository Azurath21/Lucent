import argparse
import json
import sys

from .run_carousell_scraper import CarousellScraper


def main():
    parser = argparse.ArgumentParser(description="CLI wrapper for CarousellScraper that outputs JSON")
    # Required primary field
    parser.add_argument("--item", required=True, help="Main item name to search for (required)")
    # New subfields
    parser.add_argument("--brand", default="", help="Brand to include in search keywords")
    parser.add_argument("--model", default="", help="Model to include in search keywords")
    parser.add_argument("--notes", default="", help="Additional notes/keywords to include in search")
    parser.add_argument("--condition", default="3", help="Condition filter: layered_condition value or friendly text (e.g., 'brand new')")
    parser.add_argument("--min_price", default="0", help="Minimum price filter")
    # Keep these as optional operational controls
    parser.add_argument("--sort", default="3")
    parser.add_argument("--delay", type=int, default=15)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--no-fast", dest="fast", action="store_false", help="Disable per-run speed optimizations")
    parser.set_defaults(fast=True)
    args = parser.parse_args()

    # Build the search term by combining item + brand + notes
    search_term_parts = [args.item.strip()]
    if args.brand.strip():
        search_term_parts.append(args.brand.strip())
    if args.model.strip():
        search_term_parts.append(args.model.strip())
    if args.notes.strip():
        search_term_parts.append(args.notes.strip())
    search_term = " ".join(search_term_parts)

    scraper = None
    try:
        scraper = CarousellScraper(
            item=search_term,
            condition=args.condition,
            min_price=args.min_price,
            sort=args.sort,
            headless=args.headless,
            delay=args.delay,
            fast=args.fast,
        )
        result = scraper.run_and_save()
        out = {
            "ok": True,
            "query_url": scraper.url,
            "count": result.get("count", 0),
            "csv_path": result.get("csv_path", ""),
            "screenshot_path": result.get("screenshot_path", ""),
        }
        print(json.dumps(out))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
    finally:
        try:
            if scraper:
                scraper.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
