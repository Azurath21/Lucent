import argparse
import json
import sys

from run_carousell_scraper import CarousellScraper


def main():
    parser = argparse.ArgumentParser(description="CLI wrapper for CarousellScraper that outputs JSON")
    parser.add_argument("--item", default="baby chair")
    parser.add_argument("--condition", default="3", help="layered_condition value or friendly text (e.g., 'brand new')")
    parser.add_argument("--min_price", default="0")
    parser.add_argument("--max_price", default="150")
    parser.add_argument("--sort", default="3")
    parser.add_argument("--delay", type=int, default=15)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--no-fast", dest="fast", action="store_false", help="Disable per-run speed optimizations")
    parser.set_defaults(fast=True)
    args = parser.parse_args()

    scraper = CarousellScraper(
        item=args.item,
        condition=args.condition,
        min_price=args.min_price,
        max_price=args.max_price,
        sort=args.sort,
        headless=args.headless,
        delay=args.delay,
        fast=args.fast,
    )
    try:
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
            scraper.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
