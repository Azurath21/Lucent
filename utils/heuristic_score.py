#!/usr/bin/env python3
"""
Heuristic-based CSV scoring system as an alternative to AI weighting.
Uses keyword matching and price outlier detection to score items.
"""

import pandas as pd
import numpy as np
import re
import argparse
import json
import sys
from pathlib import Path

# Common words to ignore in scoring
IGNORE_WORDS = {
    # Quality indicators
    'new', 'good', 'brand', 'well', 'used', 'condition', 'excellent', 'perfect',
    'great', 'nice', 'quality', 'original', 'authentic', 'genuine', 'official',
    'like', 'mint', 'pristine', 'flawless', 'immaculate', 'spotless',
    
    # Service terms (buyer protection, warranty, delivery)
    'buyer', 'protection', 'warranty', 'guarantee', 'applecare', 'care',
    'free', 'delivery', 'shipping', 'postage', 'courier', 'express',
    'fast', 'same', 'day', 'next', 'overnight', 'rush',
    
    # Colors
    'black', 'white', 'silver', 'gold', 'rose', 'space', 'gray', 'grey',
    'blue', 'red', 'green', 'yellow', 'orange', 'purple', 'pink',
    'midnight', 'starlight', 'product', 'coral', 'navy', 'teal',
    
    # Common words
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
    'with', 'by', 'from', 'up', 'about', 'into', 'over', 'after', 'is', 'are',
    'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
    'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
    'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
    
    # Additional marketplace terms
    'still', 'available', 'selling', 'sale', 'price', 'nego', 'negotiable',
    'firm', 'fixed', 'urgent', 'moving', 'house', 'clearance'
}

def clean_text(text):
    """Clean and normalize text for comparison."""
    if pd.isna(text):
        return ""
    
    # Convert to lowercase
    text = str(text).lower()
    
    # Remove emojis (Unicode emoji ranges)
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002500-\U00002BEF"  # chinese char
        u"\U00002702-\U000027B0"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u2640-\u2642" 
        u"\u2600-\u2B55"
        u"\u200d"
        u"\u23cf"
        u"\u23e9"
        u"\u231a"
        u"\ufe0f"  # dingbats
        u"\u3030"
                      "]+", flags=re.UNICODE)
    text = emoji_pattern.sub(r'', text)
    
    # Remove price patterns (dollar signs and associated numbers)
    # Matches patterns like: S$500, $500, SGD 500, 500$, etc.
    price_pattern = re.compile(r'\b(?:s\$|sgd|usd|\$)\s*\d+(?:[,\.]\d+)*|\d+(?:[,\.]\d+)*\s*(?:\$|sgd|usd)\b', flags=re.IGNORECASE)
    text = price_pattern.sub(r'', text)
    
    # Remove punctuation and extra spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Split into words and remove common words
    words = text.split()
    words = [word for word in words if word not in IGNORE_WORDS and len(word) > 2]
    
    return set(words)  # Return as set to handle duplicates

def calculate_keyword_score(item_text, query_keywords):
    """
    Calculate keyword matching score.
    Gives points for matching words, penalizes heavily for extra words.
    """
    item_words = clean_text(item_text)
    query_words = clean_text(query_keywords)
    
    if not query_words:
        return 0.5  # Neutral score if no query words
    
    # Count matching words
    matching_words = item_words.intersection(query_words)
    match_score = len(matching_words) / len(query_words)
    
    # Penalize for extra words (words in item but not in query)
    extra_words = item_words - query_words
    extra_penalty = len(extra_words) * 0.5  # Maximum penalty for irrelevant extra words
    
    # Final score: reward matches, penalize extras
    score = match_score - extra_penalty
    
    # Ensure score is between 0 and 1
    return max(0, min(1, score))

def detect_price_outliers(prices, z_threshold=2.0):
    """
    Detect price outliers using standard deviation.
    Returns boolean array where True indicates outlier.
    """
    prices = pd.to_numeric(prices, errors='coerce')
    prices = prices.dropna()
    
    if len(prices) < 3:
        return np.zeros(len(prices), dtype=bool)
    
    mean_price = prices.mean()
    std_price = prices.std()
    
    if std_price == 0:
        return np.zeros(len(prices), dtype=bool)
    
    z_scores = np.abs((prices - mean_price) / std_price)
    return z_scores > z_threshold

def calculate_heuristic_scores(csv_path, query_text):
    """
    Calculate heuristic scores for all items in the CSV.
    """
    try:
        # Read CSV
        df = pd.read_csv(csv_path)
        
        if df.empty:
            raise ValueError("CSV file is empty")
        
        # Check available columns and map to standard names
        columns = df.columns.tolist()
        print(f"DEBUG: Available CSV columns: {columns}", file=sys.stderr)
        
        # Map common column names to our expected format
        title_col = None
        price_col = None
        
        for col in columns:
            col_lower = col.lower()
            if 'title' in col_lower or 'item' in col_lower or 'name' in col_lower:
                title_col = col
            elif 'price' in col_lower:
                price_col = col
        
        if not title_col or not price_col:
            raise ValueError(f"Could not find title/price columns in: {columns}")
        
        print(f"DEBUG: Using title_col='{title_col}', price_col='{price_col}'", file=sys.stderr)
        
        # Calculate keyword scores
        keyword_scores = []
        for _, row in df.iterrows():
            # Combine title and description for scoring
            item_text = str(row.get(title_col, ''))
            if 'description' in df.columns:
                item_text += ' ' + str(row.get('description', ''))
            
            score = calculate_keyword_score(item_text, query_text)
            keyword_scores.append(score)
        
        df['keyword_score'] = keyword_scores
        
        # Detect price outliers
        prices = pd.to_numeric(df[price_col], errors='coerce')
        outliers = detect_price_outliers(prices)
        
        # Calculate final heuristic scores
        final_scores = []
        for i, (_, row) in enumerate(df.iterrows()):
            score = row['keyword_score']
            
            # Heavily penalize price outliers
            if i < len(outliers) and outliers[i]:
                score *= 0.1  # Reduce score by 90% for outliers
            
            final_scores.append(score)
        
        # Add the final relevance weight column (this is what the price predictor needs)
        df['Relevance_Weight'] = final_scores
        
        # Remove intermediate scoring columns to keep CSV clean
        df = df.drop(columns=['keyword_score'], errors='ignore')
        
        # Sort by relevance weight (descending)
        df = df.sort_values('Relevance_Weight', ascending=False)
        output_path = csv_path.replace('.csv', '_heuristic_scored.csv')
        df.to_csv(output_path, index=False)
        
        print(f"DEBUG: Saved heuristic scored CSV to: {output_path}", file=sys.stderr)
        print(f"DEBUG: CSV columns after scoring: {df.columns.tolist()}", file=sys.stderr)
        
        # Calculate statistics
        stats = {
            'total_items': len(df),
            'avg_keyword_score': float(np.mean(keyword_scores)),
            'outliers_detected': int(np.sum(outliers)),
            'outlier_percentage': float(np.sum(outliers) / len(df) * 100) if len(df) > 0 else 0,
            'top_score': float(df['Relevance_Weight'].max()) if not df.empty else 0,
            'avg_score': float(df['Relevance_Weight'].mean()) if not df.empty else 0
        }
        
        return {
            'success': True,
            'csv_path': output_path,
            'stats': stats
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def main():
    parser = argparse.ArgumentParser(description='Heuristic-based CSV scoring')
    parser.add_argument('csv_path', help='Path to the CSV file to score')
    parser.add_argument('query_text', help='Query text for keyword matching')
    parser.add_argument('--z-threshold', type=float, default=2.0, 
                       help='Z-score threshold for outlier detection (default: 2.0)')
    
    args = parser.parse_args()
    
    if not Path(args.csv_path).exists():
        print(json.dumps({'success': False, 'error': 'CSV file not found'}))
        sys.exit(1)
    
    result = calculate_heuristic_scores(args.csv_path, args.query_text)
    print(json.dumps(result))
    
    if not result['success']:
        sys.exit(1)

if __name__ == '__main__':
    main()
