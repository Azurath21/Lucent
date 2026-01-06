#!/usr/bin/env python3

import sys
import os
import google.generativeai as genai

def score_item(query: str, item_text: str) -> float:
    
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        return 0.0
    
    genai.configure(api_key=api_key)
    
    prompt = f"""Rate how relevant this item is to the search query on a scale of 0.01 to 1.0.
Never use 0.0 - minimum score is 0.01.

Query: {query}
Item: {item_text}

Return only a single number between 0.01 and 1.0"""
    
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        
        text = response.text.strip()
        
        try:
            score = float(text)
            return max(0.01, min(1.0, score))
        except ValueError:
            import re
            numbers = re.findall(r'\d+\.?\d*', text)
            if numbers:
                score = float(numbers[0])
                return max(0.01, min(1.0, score))
            
        print(f"Could not parse score from: {text}")
        return 0.01
        
    except Exception as e:
        return 0.01

def main():
    if len(sys.argv) != 3:
        print("Usage: python simple_score.py <query> <item_text>")
        sys.exit(1)
    
    query = sys.argv[1]
    item_text = sys.argv[2]
    
    score = score_item(query, item_text)
    print(f"{score:.4f}")

if __name__ == "__main__":
    main()
