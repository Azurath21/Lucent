import argparse
import json
import sys
import os
from .ebay_scraper import EbayScraper

def main():
    parser = argparse.ArgumentParser(description="CLI wrapper for EbayScraper that outputs JSON")
    parser.add_argument("--item", required=True, help="Main item name to search for (required)")
    parser.add_argument("--brand", default="", help="Brand to include in search keywords")
    parser.add_argument("--model", default="", help="Model to include in search keywords")
    parser.add_argument("--notes", default="", help="Additional notes/keywords to include in search")
    parser.add_argument("--condition", default="3", help="Condition filter: 1000=New, 3=Used, 7=For parts")
    parser.add_argument("--min_price", default="0", help="Minimum price filter")
    parser.add_argument("--max_price", default="", help="Maximum price filter")
    parser.add_argument("--location", default="1", help="Location preference: 1=Singapore")
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests")
    parser.add_argument("--mode", default="ultra_fast", choices=['ultra_fast', 'fast', 'normal'],
                        help="Speed mode: ultra_fast (5 pages), fast (10 pages), normal (15 pages)")
    args = parser.parse_args()

    os.makedirs("raw", exist_ok=True)
    os.makedirs("processed", exist_ok=True)

    scraper = None
    try:
        scraper = EbayScraper(
            item=args.item,
            brand=args.brand,
            model=args.model,
            notes=args.notes,
            condition=args.condition,
            min_price=args.min_price,
            max_price=args.max_price,
            location=args.location,
            delay=args.delay,
            mode=args.mode
        )
        
        result = scraper.run_and_save()
        print(json.dumps(result))
        
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
    finally:
        if scraper:
            scraper.close()

if __name__ == "__main__":
    main()
