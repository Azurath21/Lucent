#!/usr/bin/env python3

import sys
import os
import csv
import json
import re
from datetime import datetime
from sklearn.linear_model import LinearRegression
import numpy as np

def parse_price(price_str):
    if not price_str:
        return 0
    numbers = re.findall(r'\d+\.?\d*', str(price_str).replace(',', ''))
    return float(numbers[0]) if numbers else 0

def parse_date(date_str):
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
    if today is None:
        today = datetime.now()
    if isinstance(listing_date, str):
        listing_date = parse_date(listing_date)
    if listing_date is None:
        return 0
    delta = today - listing_date
    return max(0, delta.days)

def simple_predict_price(csv_path: str, target_days: int):
    try:
        
        data = []
        
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
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
        
        prices = np.array([d['price'] for d in data])
        weights = np.array([d['weight'] for d in data])
        days = np.array([d['days'] for d in data])
        
        min_price = float(prices.min())
        max_price = float(prices.max())
        avg_price = float(prices.mean())
        
        if len(data) < 3:
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
        
        X = np.column_stack([weights, days])
        y = prices
        
        model = LinearRegression()
        model.fit(X, y)
        
        r2_score = model.score(X, y)
        
        avg_weight = weights.mean()
        prediction_input = np.array([[avg_weight, target_days]])
        predicted_price = model.predict(prediction_input)[0]
        
        predicted_price = max(min_price * 0.5, min(predicted_price, max_price * 1.5))
        
        return {
            "ok": True,
            "predicted_price": round(float(predicted_price), 2),
            "target_days": target_days,
            "data_points": len(data),
            "model_accuracy_mae": round(r2_score * 100, 1),
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
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "Usage: python simple_price_predictor.py <csv_path> [target_days]"}))
        sys.exit(1)
    
    csv_path = sys.argv[1]
    target_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    if not os.path.exists(csv_path):
        print(json.dumps({"ok": False, "error": f"File not found: {csv_path}"}))
        sys.exit(0)
    
    result = simple_predict_price(csv_path, target_days)
    print(json.dumps(result))
