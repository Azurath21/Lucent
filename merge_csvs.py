import sys
import os
import csv
from datetime import datetime

"""
Usage: python merge_csvs.py <output_dir> <item_slug> <csv1> <csv2> ...
- Merges all CSVs with header: Date, Item, Item_Link, Price, Seller, Seller_Link, Seller_Ratings
- Deduplicates by Item_Link.
- Writes output to <output_dir>/<timestamp>_Combined_<item_slug>.csv
- Prints JSON to stdout: {"ok": true, "csv_path": "...", "count": N}
"""

import json

def slugify(s: str) -> str:
    return ''.join(c if c.isalnum() else '_' for c in s).strip('_')

def main():
    try:
        if len(sys.argv) < 4:
            print(json.dumps({"ok": False, "error": "Usage: merge_csvs.py <output_dir> <item_slug> <csv1> <csv2> ..."}))
            sys.exit(1)
        out_dir = sys.argv[1]
        item_slug = slugify(sys.argv[2]) or 'items'
        csv_paths = sys.argv[3:]
        os.makedirs(out_dir, exist_ok=True)

        # Prepare output
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_path = os.path.join(out_dir, f"{ts}_Combined_{item_slug}.csv")

        seen = set()
        rows = []
        header = ['Date', 'Item', 'Item_Link', 'Price', 'Seller', 'Seller_Link', 'Seller_Ratings']
        for p in csv_paths:
            if not p or not os.path.exists(p):
                continue
            with open(p, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                try:
                    first = next(reader, None)
                except Exception:
                    first = None
                if first is None:
                    continue
                # If the first row matches header (case-insensitive by position), skip it
                if [c.strip().lower() for c in first] != [c.lower() for c in header]:
                    # not a header, treat as data row
                    row = first
                    if len(row) >= 3:
                        key = row[2].strip()
                        if key and key not in seen:
                            seen.add(key)
                            rows.append(row)
                # read rest
                for row in reader:
                    if not row:
                        continue
                    if len(row) < 3:
                        continue
                    key = row[2].strip()  # Item_Link
                    if key and key not in seen:
                        seen.add(key)
                        rows.append(row)

        # Write output
        with open(out_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for r in rows:
                writer.writerow(r)

        print(json.dumps({"ok": True, "csv_path": out_path, "count": len(rows)}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)

if __name__ == '__main__':
    main()
