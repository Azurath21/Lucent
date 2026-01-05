#!/usr/bin/env python3
"""
Price prediction using Linear Regression.
Usage: python simple_price_predictor.py <input_csv> <target_days>
"""

import sys
import os
import csv
import json
import re
from datetime import datetime
from sklearn.linear_model import LinearRegression
import numpy as np

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

def parse_date(date_str):
    """Parse date string to datetime object."""
    if not date_str:
        return None
    try:
        for fmt in ['%Y-%m-%d', '%Y-%d-%m', '%d-%m-%Y', '%m-%d-%Y']:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        return None
    except:
        return None

def calculate_days_to_sell(listing_date, today=None):
    """Calculate days from listing to today."""
    if today is None:
        today = datetime.now()
    if isinstance(listing_date, str):
        listing_date = parse_date(listing_date)
    if listing_date is None:
        return 0
    delta = today - listing_date
    return max(0, delta.days)

def simple_predict_price(csv_path: str, target_days: int):
    """
    Price prediction using Linear Regression model.
    Features: Relevance_Weight, days_to_sell
    Target: price
    """
    try:
        debug_print(f"Reading CSV file: {csv_path}")
        
        # Read CSV file
        data = []
        
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            debug_print(f"CSV columns: {reader.fieldnames}")
            
            for row in reader:
                price_str = row.get('Price', '')
                date_str = row.get('Date', '')
                weight_str = row.get('Relevance_Weight', '1.0')
                
                if price_str:
                    price = parse_price(price_str)
                    weight = float(weight_str) if weight_str else 1.0
                    days = calculate_days_to_sell(date_str) if date_str else 0
                    
                    if price > 0 and weight > 0:
                        data.append({
                            'price': price,
                            'weight': weight,
                            'days': days
                        })
                        debug_print(f"Added: price={price}, weight={weight}, days={days}")
        
        debug_print(f"Total data points: {len(data)}")
        
        if not data:
            return {
                'predicted_price': 0,
                'price_range': {'min': 0, 'max': 0, 'avg': 0},
                'confidence': 0,
                'target_days': target_days,
                'sample_size': 0,
                'recommendation': 'No market data available - consider manual pricing',
                'status': 'no_data'
            }
        
        # Extract features and target
        prices = np.array([d['price'] for d in data])
        weights = np.array([d['weight'] for d in data])
        days = np.array([d['days'] for d in data])
        
        min_price = float(prices.min())
        max_price = float(prices.max())
        avg_price = float(prices.mean())
        
        if len(data) < 3:
            # Not enough data for regression - use weighted average
            weighted_avg = np.sum(prices * weights) / np.sum(weights)
            return {
                "ok": True,
                "predicted_price": round(float(weighted_avg), 2),
                "target_days": target_days,
                "data_points": len(data),
                "model_accuracy_mae": "N/A - Insufficient data for regression",
                "price_stats": {"min": min_price, "max": max_price, "avg": avg_price},
                "time_stats": {"min_days": int(days.min()), "max_days": int(days.max()), "avg_days": float(days.mean())},
                "avg_relevance_used": round(float(weights.mean()), 3)
            }
        
        # Build features matrix: [weight, days]
        X = np.column_stack([weights, days])
        y = prices
        
        # Train Linear Regression model
        model = LinearRegression()
        model.fit(X, y)
        
        # Calculate R² score for accuracy
        r2_score = model.score(X, y)
        
        # Predict for target days with average relevance weight
        avg_weight = weights.mean()
        prediction_input = np.array([[avg_weight, target_days]])
        predicted_price = model.predict(prediction_input)[0]
        
        # Ensure predicted price is reasonable (within min-max range with some buffer)
        predicted_price = max(min_price * 0.5, min(predicted_price, max_price * 1.5))
        
        return {
            "ok": True,
            "predicted_price": round(float(predicted_price), 2),
            "target_days": target_days,
            "data_points": len(data),
            "model_accuracy_mae": round(r2_score * 100, 1),  # R² as percentage
            "price_stats": {"min": min_price, "max": max_price, "avg": avg_price},
            "time_stats": {
                "min_days": int(days.min()),
                "max_days": int(days.max()),
                "avg_days": round(float(days.mean()), 1)
            },
            "avg_relevance_used": round(float(avg_weight), 3),
            "model_coefficients": {
                "weight_coef": round(float(model.coef_[0]), 4),
                "days_coef": round(float(model.coef_[1]), 4),
                "intercept": round(float(model.intercept_), 2)
            }
        }
        
    except Exception as e:
        debug_print(f"Error: {str(e)}")
        return {
            'ok': False,
            'predicted_price': 0,
            'price_range': {'min': 0, 'max': 0, 'avg': 0},
            'confidence': 0,
            'target_days': target_days,
            'sample_size': 0,
            'recommendation': f'Error: {str(e)}',
            'status': 'error'
        }

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
