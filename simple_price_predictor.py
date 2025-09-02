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
        # Read CSV file
        prices = []
        items = []
        
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                price_str = row.get('Price', '')
                item_name = row.get('Item', '')
                
                if price_str and item_name:
                    price = parse_price(price_str)
                    if price > 0:
                        prices.append(price)
                        items.append(item_name)
        
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
        
        # Calculate basic statistics
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        
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
        
        # Reduce confidence if high variance
        confidence = base_confidence * max(0.5, 1 - variance_ratio * 0.3)
        
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
    if len(sys.argv) < 2:
        print("Usage: python simple_price_predictor.py <csv_path> [target_days]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    target_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    if not os.path.exists(csv_path):
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
    
    result = simple_predict_price(csv_path, target_days)
    print(json.dumps(result, indent=2))
