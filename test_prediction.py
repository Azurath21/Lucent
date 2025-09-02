#!/usr/bin/env python3

import pandas as pd
import numpy as np
from datetime import datetime
import json

def simple_price_prediction(csv_path, target_days=30):
    """Simple price prediction for testing"""
    try:
        # Read the CSV
        df = pd.read_csv(csv_path)
        print(f"Loaded CSV with {len(df)} rows")
        print("Data preview:")
        print(df.head())
        
        # Parse prices
        prices = []
        for price_str in df['Price']:
            # Extract numeric value from price string
            import re
            numbers = re.findall(r'\d+\.?\d*', str(price_str).replace(',', ''))
            if numbers:
                prices.append(float(numbers[0]))
        
        if not prices:
            return {
                'error': 'No valid prices found in CSV',
                'predicted_price': 0,
                'confidence': 0
            }
        
        # Calculate statistics
        avg_price = np.mean(prices)
        min_price = np.min(prices)
        max_price = np.max(prices)
        
        # Simple prediction: average price with slight discount for faster sale
        discount_factor = 0.95 if target_days <= 30 else 0.98
        predicted_price = avg_price * discount_factor
        
        result = {
            'predicted_price': round(predicted_price, 2),
            'price_range': {
                'min': round(min_price, 2),
                'max': round(max_price, 2),
                'avg': round(avg_price, 2)
            },
            'confidence': 0.8,
            'target_days': target_days,
            'sample_size': len(prices),
            'recommendation': f'Price at SGD {predicted_price:.0f} for {target_days}-day sale'
        }
        
        print(f"\nPrice Analysis:")
        print(f"Sample size: {len(prices)} items")
        print(f"Price range: SGD {min_price:.0f} - SGD {max_price:.0f}")
        print(f"Average price: SGD {avg_price:.0f}")
        print(f"Recommended price: SGD {predicted_price:.0f}")
        
        return result
        
    except Exception as e:
        return {
            'error': str(e),
            'predicted_price': 0,
            'confidence': 0
        }

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python test_prediction.py <csv_path> [target_days]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    target_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    result = simple_price_prediction(csv_path, target_days)
    print(f"\nFinal Result: {json.dumps(result, indent=2)}")
