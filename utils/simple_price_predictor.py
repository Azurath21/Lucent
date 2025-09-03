#!/usr/bin/env python3
"""
Simple price prediction without pandas dependency.
Usage: python simple_price_predictor.py <input_csv> <target_days>
"""

import sys
import os
import csv
import json
import re
from datetime import datetime

# Add debug output to stderr
def debug_print(msg):
    print(f"DEBUG: {msg}", file=sys.stderr)

def parse_price(price_str):
    """Extract numeric price from price string like 'SGD 450' or 'S$488'."""
    if not price_str:
        return 0
    # Remove currency symbols and extract number
    numbers = re.findall(r'\d+\.?\d*', str(price_str).replace(',', ''))
    return float(numbers[0]) if numbers else 0

def simple_predict_price(csv_path: str, target_days: int):
    """
    Simple price prediction using basic CSV parsing and statistics.
    """
    try:
        debug_print(f"Reading CSV file: {csv_path}")
        
        # Read CSV file
        prices = []
        items = []
        weights_found = False
        
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            debug_print(f"CSV columns: {reader.fieldnames}")
            
            for row in reader:
                price_str = row.get('Price', '')
                item_name = row.get('Item', '')
                weight_str = row.get('Relevance_Weight', '1.0')  # Default weight if missing
                
                debug_print(f"Processing row - Price: {price_str}, Weight: {weight_str}")
                
                if price_str and item_name:
                    price = parse_price(price_str)
                    weight = float(weight_str) if weight_str else 1.0
                    
                    if price > 0:
                        # Store price and weight for weighted calculation
                        prices.append((price, weight))
                        items.append(f"{item_name} (weight: {weight:.2f})")
                        debug_print(f"Added price: {price}, weight: {weight}")
        
        debug_print(f"Total prices found: {len(prices)}")
        
        if not prices:
            # Return a valid JSON structure even with no data
            result = {
                'predicted_price': 0,
                'price_range': {
                    'min': 0,
                    'max': 0,
                    'avg': 0
                },
                'confidence': 0,
                'target_days': target_days,
                'sample_size': 0,
                'recommendation': 'No market data available - consider manual pricing',
                'market_analysis': {
                    'lowest_price': 0,
                    'highest_price': 0,
                    'average_market_price': 0,
                    'suggested_discount': '0%'
                },
                'status': 'no_data'
            }
            return result
        
        # Calculate weighted statistics
        total_weighted_price = sum(price * weight for price, weight in prices)
        total_weight = sum(weight for price, weight in prices)
        
        # Weighted average price
        avg_price = total_weighted_price / total_weight if total_weight > 0 else 0
        
        # Min/max from actual prices (not weighted)
        raw_prices = [price for price, weight in prices]
        min_price = min(raw_prices)
        max_price = max(raw_prices)
        
        # Simple prediction logic
        # For faster sales (≤30 days), apply discount
        # For longer sales (>30 days), price closer to average
        if target_days <= 15:
            discount_factor = 0.90  # 10% discount for quick sale
        elif target_days <= 30:
            discount_factor = 0.95  # 5% discount
        else:
            discount_factor = 0.98  # 2% discount for patient sale
        
        predicted_price = avg_price * discount_factor
        
        # Confidence based on sample size and price variance
        price_range = max_price - min_price
        variance_ratio = price_range / avg_price if avg_price > 0 else 1
        
        if len(prices) >= 10:
            base_confidence = 0.9
        elif len(prices) >= 5:
            base_confidence = 0.8
        elif len(prices) >= 3:
            base_confidence = 0.7
        else:
            base_confidence = 0.6
        
        # Add weighted information to results
        avg_weight = total_weight / len(prices) if len(prices) > 0 else 1.0
        
        # Calculate confidence properly
        confidence = base_confidence * (1 - min(variance_ratio * 0.1, 0.3))
        
        return {
            "predicted_price": predicted_price,
            "target_days": target_days,
            "data_points": len(prices),
            "model_accuracy_mae": f"{confidence * 100:.0f}",
            "price_stats": {
                "min": min_price,
                "max": max_price,
                "avg": avg_price
            },
            "time_stats": {
                "sample_size": len(prices),
                "confidence": confidence,
                "recommendation": f"Price at ${predicted_price:.0f} for {target_days}-day sale"
            }
        }
        
    except Exception as e:
        # Return valid JSON structure for errors too
        result = {
            'predicted_price': 0,
            'price_range': {
                'min': 0,
                'max': 0,
                'avg': 0
            },
            'confidence': 0,
            'target_days': target_days,
            'sample_size': 0,
            'recommendation': f'Error: {str(e)}',
            'market_analysis': {
                'lowest_price': 0,
                'highest_price': 0,
                'average_market_price': 0,
                'suggested_discount': '0%'
            },
            'status': 'error'
        }
        return result

if __name__ == "__main__":
    debug_print("Script started")
    
    if len(sys.argv) < 2:
        debug_print("Not enough arguments")
        print("Usage: python simple_price_predictor.py <csv_path> [target_days]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    target_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    debug_print(f"Arguments: csv_path={csv_path}, target_days={target_days}")
    
    if not os.path.exists(csv_path):
        debug_print(f"CSV file not found: {csv_path}")
        result = {
            'predicted_price': 0,
            'price_range': {'min': 0, 'max': 0, 'avg': 0},
            'confidence': 0,
            'target_days': target_days,
            'sample_size': 0,
            'recommendation': f'CSV file not found: {csv_path}',
            'market_analysis': {'lowest_price': 0, 'highest_price': 0, 'average_market_price': 0, 'suggested_discount': '0%'},
            'status': 'file_not_found'
        }
        print(json.dumps(result, indent=2))
        sys.exit(0)
    
    debug_print("Calling simple_predict_price function")
    result = simple_predict_price(csv_path, target_days)
    debug_print(f"Function returned: {result}")
    print(json.dumps(result, indent=2))
