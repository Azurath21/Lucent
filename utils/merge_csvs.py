import sys
import os
import csv
from datetime import datetime

"""
Usage: python merge_csvs.py <output_dir> <item_slug> <csv1> <csv2> ...
- Merges CSVs with header: Date, Item, Price
- Deduplicates by the (Date, Item, Price) tuple.
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
        header = ['Date', 'Item', 'Price']
        legacy_header = ['Date', 'Item', 'Item_Link', 'Price', 'Seller', 'Seller_Link', 'Seller_Ratings']

        def normalize_row(row):
            # Return (Date, Item, Price) from either 3-col or legacy 7-col rows
            if len(row) >= 7:
                return [row[0], row[1], row[3]]
            # fallback to first 3 columns
            return [row[0] if len(row) > 0 else '', row[1] if len(row) > 1 else '', row[2] if len(row) > 2 else '']
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
                # If the first row matches known headers (case-insensitive), skip it
                first_lc = [c.strip().lower() for c in first]
                if first_lc != [c.lower() for c in header] and first_lc != [c.lower() for c in legacy_header]:
                    # not a header, treat as data row
                    row = normalize_row(first)
                    if len(row) >= 3:
                        key = (row[0].strip(), row[1].strip(), row[2].strip())
                        if key not in seen:
                            seen.add(key)
                            rows.append([row[0], row[1], row[2]])
                # read rest
                for row in reader:
                    if not row:
                        continue
                    row = normalize_row(row)
                    if len(row) < 3:
                        continue
                    key = (row[0].strip(), row[1].strip(), row[2].strip())
                    if key not in seen:
                        seen.add(key)
                        rows.append([row[0], row[1], row[2]])

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
