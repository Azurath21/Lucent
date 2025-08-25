#!/usr/bin/env python3
"""
CSV scoring using batched Gemini approach.
Usage: python csv_score.py <input_csv> <output_dir> <query> [--batch-size=N]
Outputs: Date, Item, Price, Relevance_Weight
"""

import sys
import os
import csv
import json
import time
from datetime import datetime
import google.generativeai as genai

def score_batch(query: str, items: list, model, max_retries=3, batch_num=None, total_batches=None) -> list:
    """Score a batch of items against a query using Gemini."""
    
    if batch_num is not None and total_batches is not None:
        print(f"Processing batch {batch_num}/{total_batches}...", flush=True)
    
    # Build batch prompt
    items_text = "\n".join([f"{i}: {item}" for i, item in enumerate(items)])
    
    prompt = f"""Rate how relevant each item is to the search query on a scale of 0.01 to 1.0.
Never use 0.0 - minimum score is 0.01.

BE VERY HARSH: Only give high scores (0.7+) to items that are EXACTLY what the user is searching for.
Give 0.01 to accessories, covers, parts, decorations, or anything that is NOT the main item itself.

Examples for query "baby chair":
- "Baby High Chair" = 0.95 (exact match)
- "Baby chair cover" = 0.01 (accessory, not the chair)
- "Baby chair cushion" = 0.01 (accessory, not the chair)
- "Chair decoration" = 0.01 (decoration, not the chair)
- "Table and chair set" = 0.3 (includes chair but not primarily a baby chair)

Query: {query}

Items:
{items_text}

Return exactly {len(items)} scores as a JSON array, one score per item in order.
Example: [0.85, 0.01, 0.67, 0.01]"""
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            # Try to parse as JSON array
            try:
                import re
                # Extract JSON array from response
                json_match = re.search(r'\[[\d\.,\s]+\]', text)
                if json_match:
                    scores = json.loads(json_match.group())
                    if len(scores) == len(items):
                        return [max(0.01, min(1.0, float(s))) for s in scores]
            except:
                pass
            
            # Fallback: extract all numbers and take first N
            import re
            numbers = re.findall(r'\d+\.?\d*', text)
            if len(numbers) >= len(items):
                scores = [float(n) for n in numbers[:len(items)]]
                return [max(0.01, min(1.0, s)) for s in scores]
            
            # If we got some numbers but not enough, pad with 0.01
            if numbers:
                scores = [float(n) for n in numbers]
                while len(scores) < len(items):
                    scores.append(0.01)
                return [max(0.01, min(1.0, s)) for s in scores[:len(items)]]
                
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to score batch after {max_retries} attempts: {e}", file=sys.stderr)
            else:
                time.sleep(1)  # Brief delay before retry
    
    # Complete fallback: return 0.01 for all items
    return [0.01] * len(items)

def main():
    if len(sys.argv) < 4:
        print("Usage: python csv_score.py <input_csv> <output_dir> <query> [--batch-size=N]")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_dir = sys.argv[2]
    query = sys.argv[3]
    
    # Parse batch size
    batch_size = 20  # Default batch size
    for arg in sys.argv[4:]:
        if arg.startswith("--batch-size="):
            try:
                batch_size = int(arg.split("=")[1])
            except:
                pass
    
    # Setup Gemini
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print(json.dumps({"ok": False, "error": "Missing GOOGLE_API_KEY"}))
        sys.exit(1)
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    # Read CSV
    with open(input_csv, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)
    
    if not rows:
        print(json.dumps({"ok": False, "error": "Empty CSV"}))
        sys.exit(1)
    
    # Determine column indices
    lc = [c.strip().lower() for c in header]
    if lc[:3] == ['date', 'item', 'price']:
        date_idx, item_idx, price_idx = 0, 1, 2
    else:
        # Legacy format
        date_idx, item_idx, price_idx = 0, 1, 3
    
    # Extract items for batching
    items_data = []
    for row in rows:
        date = row[date_idx] if date_idx < len(row) else ""
        item = row[item_idx] if item_idx < len(row) else ""
        price = row[price_idx] if price_idx < len(row) else ""
        items_data.append((date, item, price))
    
    # Process in batches
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(output_dir, f"{ts}_Weighted.csv")
    
    all_scores = []
    total_batches = (len(items_data) + batch_size - 1) // batch_size
    
    for batch_idx in range(0, len(items_data), batch_size):
        batch_items = items_data[batch_idx:batch_idx + batch_size]
        item_texts = [item[1] for item in batch_items]  # Extract item text
        
        batch_num = batch_idx//batch_size + 1
        print(f"Processing batch {batch_num}/{total_batches} ({len(item_texts)} items)", file=sys.stderr)
        
        # Score this batch
        batch_scores = score_batch(query, item_texts, model, batch_num=batch_num, total_batches=total_batches)
        all_scores.extend(batch_scores)
        
        # Small delay between batches to be API-friendly
        if batch_idx + batch_size < len(items_data):
            time.sleep(0.5)
    
    # Write output
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Item", "Price", "Relevance_Weight"])
        
        for (date, item, price), score in zip(items_data, all_scores):
            writer.writerow([date, item, price, f"{score:.4f}"])
    
    print(json.dumps({"ok": True, "csv_path": output_path, "count": len(items_data)}))

if __name__ == "__main__":
    main()
