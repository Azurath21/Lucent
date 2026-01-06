#!/usr/bin/env python3

import sys
import os
import csv
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import warnings
warnings.filterwarnings('ignore')

def parse_price(price_str):
    if not price_str:
        return 0
    import re
    numbers = re.findall(r'\d+\.?\d*', str(price_str).replace(',', ''))
    return float(numbers[0]) if numbers else 0

def parse_date(date_str):
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

def predict_price(csv_path: str, target_days: int):
    try:
        df = pd.read_csv(csv_path)
        
        required_cols = ['Date', 'Item', 'Price']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        if len(df) == 0:
            raise ValueError("CSV file is empty")
        
        df['Price'] = df['Price'].astype(str)
        df['Price'] = df['Price'].str.replace(r'S\$', '', regex=True).str.replace('SGD', '').str.replace(r'\$', '', regex=True).str.replace(',', '').str.strip()
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        
        df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d', errors='coerce')
        
        if 'Relevance_Weight' not in df.columns:
            df['Relevance_Weight'] = 1.0
        else:
            df['Relevance_Weight'] = pd.to_numeric(df['Relevance_Weight'], errors='coerce').fillna(1.0)
        
        df = df.dropna(subset=['Price'])
        df = df[df['Price'] > 0]
        
        if len(df) == 0:
            raise ValueError("No valid data rows after cleaning")
            
    except Exception as e:
        raise ValueError(f"Data loading/cleaning error: {str(e)}")
    
    df['price_numeric'] = df['Price']
    
    today = datetime.now()
    df['days_to_sell'] = df['Date'].apply(lambda d: max(0, (today - d).days) if pd.notna(d) else 0)
    
    df = df[
        (df['price_numeric'] > 0) & 
        (df['Relevance_Weight'] > 0)
    ]
    
    if len(df) == 0:
        raise ValueError("No valid data after filtering")
    
    weights = df['Relevance_Weight'].values
    prices = df['price_numeric'].values
    days = df['days_to_sell'].values
    
    min_price = float(prices.min())
    max_price = float(prices.max())
    avg_price = float(prices.mean())
    median_price = float(np.median(prices))
    
    weighted_avg = float(np.average(prices, weights=weights))
    
    if len(df) < 5:
        high_rel_mask = weights >= np.percentile(weights, 50)
        if high_rel_mask.sum() > 0:
            predicted_price = float(np.median(prices[high_rel_mask]))
        else:
            predicted_price = weighted_avg
        
        return {
            "ok": True,
            "predicted_price": round(float(predicted_price), 2),
            "target_days": int(target_days),
            "data_points": int(len(df)),
            "model_accuracy_mae": "N/A - Insufficient data",
            "price_stats": {
                'min_price': min_price,
                'max_price': max_price,
                'avg_price': round(avg_price, 2),
                'median_price': median_price
            },
            "time_stats": {
                'min_days': int(days.min()) if len(days) > 0 else 0,
                'max_days': int(days.max()) if len(days) > 0 else 0,
                'avg_days': round(float(days.mean()), 1) if len(days) > 0 else 0
            },
            "avg_relevance_used": round(float(weights.mean()), 3)
        }
    
    X = np.column_stack([weights, days])
    y = prices
    
    model = XGBRegressor(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        random_state=42,
        verbosity=0
    )
    
    if len(df) >= 10:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        mae = float(mean_absolute_error(y_test, y_pred))
    else:
        model.fit(X, y)
        y_pred_all = model.predict(X)
        mae = float(mean_absolute_error(y, y_pred_all))
    
    avg_weight = max(0.7, float(np.percentile(weights, 75)))
    prediction_input = np.array([[avg_weight, target_days]])
    predicted_price = float(model.predict(prediction_input)[0])
    
    predicted_price = max(min_price * 0.8, min(predicted_price, max_price * 1.2))
    
    return {
        "ok": True,
        "predicted_price": round(float(predicted_price), 2),
        "target_days": int(target_days),
        "model_accuracy_mae": round(mae, 2),
        "data_points": int(len(df)),
        "price_stats": {
            'min_price': min_price,
            'max_price': max_price,
            'avg_price': round(avg_price, 2),
            'median_price': median_price
        },
        "time_stats": {
            'min_days': int(days.min()),
            'max_days': int(days.max()),
            'avg_days': round(float(days.mean()), 1)
        },
        "avg_relevance_used": round(float(weights.mean()), 3)
    }

def main():
    if len(sys.argv) != 3:
        print(json.dumps({"ok": False, "error": "Usage: python price_predictor.py <input_csv> <target_days>"}))
        sys.exit(1)
    
    csv_path = sys.argv[1]
    try:
        target_days = int(sys.argv[2])
    except ValueError:
        print(json.dumps({"ok": False, "error": "Target days must be an integer"}))
        sys.exit(1)
    
    if not os.path.exists(csv_path):
        print(json.dumps({"ok": False, "error": f"CSV file not found: {csv_path}"}))
        sys.exit(1)
    
    try:
        result = predict_price(csv_path, target_days)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Price prediction failed: {str(e)}"}))
        sys.exit(1)

if __name__ == "__main__":
    main()
