import argparse
import json
import sys
import os
import csv
import time
from .ebay_scraper import EbayScraper

def main():
    parser = argparse.ArgumentParser(description="CLI wrapper for EbayScraper that outputs JSON")
    # Required primary field
    parser.add_argument("--item", required=True, help="Main item name to search for (required)")
    # New subfields
    parser.add_argument("--brand", default="", help="Brand to include in search keywords")
    parser.add_argument("--model", default="", help="Model to include in search keywords")
    parser.add_argument("--notes", default="", help="Additional notes/keywords to include in search")
    parser.add_argument("--condition", default="3", help="Condition filter: 1000=New, 3=Used, 7=For parts")
    parser.add_argument("--min_price", default="0", help="Minimum price filter")
    parser.add_argument("--max_price", default="", help="Maximum price filter")
    parser.add_argument("--location", default="1", help="Location preference: 1=Singapore")
    # Keep these as optional operational controls
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests")
    args = parser.parse_args()

    # Ensure raw directory exists
    os.makedirs("raw", exist_ok=True)

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
            delay=args.delay
        )
        
        result = scraper.run_and_save()
        print(json.dumps(result))
        
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
