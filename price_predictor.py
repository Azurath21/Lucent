#!/usr/bin/env python3
"""
Price prediction model using tree regression.
Usage: python price_predictor.py <input_csv> <target_days>
Returns predicted price to sell within target timeframe.
"""

import sys
import os
import csv
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import warnings
warnings.filterwarnings('ignore')

def parse_price(price_str):
    """Extract numeric price from price string like 'S$488'."""
    if not price_str:
        return 0
    # Remove currency symbols and extract number
    import re
    numbers = re.findall(r'\d+\.?\d*', str(price_str).replace(',', ''))
    return float(numbers[0]) if numbers else 0

def parse_date(date_str):
    """Parse date string to datetime object."""
    try:
        # Try different date formats
        for fmt in ['%Y-%m-%d', '%Y-%d-%m', '%d-%m-%Y', '%m-%d-%Y']:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        return None
    except:
        return None

def calculate_days_to_sell(listing_date, today=None):
    """Calculate days from listing to today (assumed sold today)."""
    if today is None:
        today = datetime.now()
    
    if isinstance(listing_date, str):
        listing_date = parse_date(listing_date)
    
    if listing_date is None:
        return 0
    
    delta = today - listing_date
    return max(0, delta.days)

def predict_price(csv_path: str, target_days: int):
    """
    Predict price based on relevance weight, days to sell, and historical prices.
    """
    try:
        # Read CSV
        df = pd.read_csv(csv_path)
        
        # Ensure required columns exist
        required_cols = ['Date', 'Item', 'Price']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        if len(df) == 0:
            raise ValueError("CSV file is empty")
        
        # Clean and convert data
        # Handle Price column - convert to string first if needed
        df['Price'] = df['Price'].astype(str)
        df['Price'] = df['Price'].str.replace('S$', '').str.replace('SGD', '').str.replace(',', '').str.strip()
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        
        df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d', errors='coerce')
        
        # Handle Relevance_Weight column - add default if missing
        if 'Relevance_Weight' not in df.columns:
            df['Relevance_Weight'] = 1.0
        else:
            df['Relevance_Weight'] = pd.to_numeric(df['Relevance_Weight'], errors='coerce').fillna(1.0)
        
        # Remove rows with invalid dates
        df = df.dropna(subset=['Date'])
        
        if len(df) == 0:
            raise ValueError("No valid data rows after cleaning")
            
    except Exception as e:
        raise ValueError(f"Data loading/cleaning error: {str(e)}")
    
    # Process data
    df['price_numeric'] = df['Price']
    df['days_to_sell'] = df['Date'].apply(lambda x: calculate_days_to_sell(x))
    
    # Filter out invalid data
    df = df[
        (df['price_numeric'] > 0) & 
        (df['days_to_sell'] >= 0) & 
        (df['Relevance_Weight'] > 0)
    ]
    
    if len(df) < 3:
        # Insufficient data for ML prediction - return highest relevance item
        highest_relevance_item = df.loc[df['Relevance_Weight'].idxmax()]
        return {
            "ok": True,
            "predicted_price": float(highest_relevance_item['price_numeric']),
            "target_days": int(highest_relevance_item['days_to_sell']),
            "data_points": len(df),
            "model_accuracy_mae": "N/A - Insufficient data",
            "fallback_reason": "Used highest relevance item due to insufficient data for ML prediction",
            "price_stats": {
                'min_price': float(df['price_numeric'].min()),
                'max_price': float(df['price_numeric'].max()),
                'avg_price': float(df['price_numeric'].mean()),
                'median_price': float(df['price_numeric'].median())
            },
            "time_stats": {
                'min_days': int(df['days_to_sell'].min()),
                'max_days': int(df['days_to_sell'].max()),
                'avg_days': float(df['days_to_sell'].mean())
            },
            "avg_relevance_used": round(float(highest_relevance_item['Relevance_Weight']), 3)
        }
    
    # Features: Relevance_Weight, days_to_sell
    # Target: price_numeric
    X = df[['Relevance_Weight', 'days_to_sell']]
    y = df['price_numeric']
    
    # Train model
    if len(df) >= 10:
        # Use train/test split if enough data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=10)
        model.fit(X_train, y_train)
        
        # Calculate model accuracy
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
    else:
        # Use all data for training if small dataset
        model = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=10)
        model.fit(X, y)
        mae = 0
    
    # Get average relevance weight for prediction
    avg_relevance = df['Relevance_Weight'].mean()
    
    # Predict price for target timeframe
    prediction_input = np.array([[avg_relevance, target_days]])
    predicted_price = model.predict(prediction_input)[0]
    
    # Get price statistics for context
    price_stats = {
        'min_price': float(df['price_numeric'].min()),
        'max_price': float(df['price_numeric'].max()),
        'avg_price': float(df['price_numeric'].mean()),
        'median_price': float(df['price_numeric'].median())
    }
    
    # Get timeframe statistics
    time_stats = {
        'min_days': int(df['days_to_sell'].min()),
        'max_days': int(df['days_to_sell'].max()),
        'avg_days': float(df['days_to_sell'].mean())
    }
    
    return {
        "ok": True,
        "predicted_price": round(predicted_price, 2),
        "target_days": target_days,
        "model_accuracy_mae": round(mae, 2) if mae > 0 else "N/A",
        "data_points": len(df),
        "price_stats": price_stats,
        "time_stats": time_stats,
        "avg_relevance_used": round(avg_relevance, 3)
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
