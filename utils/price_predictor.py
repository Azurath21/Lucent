#!/usr/bin/env python3
"""
Price prediction model using XGBoost regression.
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
from xgboost import XGBRegressor
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
    Predict optimal selling price using XGBoost.
    
    Strategy:
    - Use Relevance_Weight to identify the most relevant comparable items
    - Calculate weighted price statistics
    - Apply time-based discount for faster sales
    - Use XGBoost to model price ~ Relevance_Weight relationship
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
        df['Price'] = df['Price'].astype(str)
        # Handle currency symbols: S$, SGD, $
        df['Price'] = df['Price'].str.replace(r'S\$', '', regex=True).str.replace('SGD', '').str.replace(r'\$', '', regex=True).str.replace(',', '').str.strip()
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce')
        
        df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d', errors='coerce')
        
        # Handle Relevance_Weight column - add default if missing
        if 'Relevance_Weight' not in df.columns:
            df['Relevance_Weight'] = 1.0
        else:
            df['Relevance_Weight'] = pd.to_numeric(df['Relevance_Weight'], errors='coerce').fillna(1.0)
        
        # Remove rows with invalid prices
        df = df.dropna(subset=['Price'])
        df = df[df['Price'] > 0]
        
        if len(df) == 0:
            raise ValueError("No valid data rows after cleaning")
            
    except Exception as e:
        raise ValueError(f"Data loading/cleaning error: {str(e)}")
    
    # Process data
    df['price_numeric'] = df['Price']
    
    # Filter out invalid data
    df = df[
        (df['price_numeric'] > 0) & 
        (df['Relevance_Weight'] > 0)
    ]
    
    if len(df) == 0:
        raise ValueError("No valid data after filtering")
    
    # Calculate weighted statistics
    weights = df['Relevance_Weight'].values
    prices = df['price_numeric'].values
    
    # Weighted average price (more weight to relevant items)
    weighted_avg = float(np.average(prices, weights=weights))
    
    # Price statistics
    min_price = float(prices.min())
    max_price = float(prices.max())
    avg_price = float(prices.mean())
    median_price = float(np.median(prices))
    
    if len(df) < 3:
        # Insufficient data - use weighted average with time discount
        if target_days <= 7:
            discount = 0.85  # 15% discount for very quick sale
        elif target_days <= 14:
            discount = 0.90  # 10% discount
        elif target_days <= 30:
            discount = 0.95  # 5% discount
        else:
            discount = 1.0   # No discount for patient sale
        
        predicted_price = weighted_avg * discount
        
        return {
            "ok": True,
            "predicted_price": round(float(predicted_price), 2),
            "target_days": int(target_days),
            "data_points": int(len(df)),
            "model_accuracy_mae": "N/A - Used weighted average",
            "price_stats": {
                'min_price': min_price,
                'max_price': max_price,
                'avg_price': avg_price,
                'median_price': median_price
            },
            "time_stats": {
                'weighted_avg': round(weighted_avg, 2),
                'discount_applied': f"{(1-discount)*100:.0f}%"
            },
            "avg_relevance_used": round(float(weights.mean()), 3)
        }
    
    # Use XGBoost to model: price ~ Relevance_Weight
    # This learns which prices correspond to which relevance levels
    X = df[['Relevance_Weight']].values
    y = prices
    
    # Train model
    model = XGBRegressor(
        n_estimators=100,
        max_depth=4,
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
        mae = 0.0
    
    # Predict price for high-relevance items (relevance=0.8-1.0)
    # These are the most comparable items
    high_relevance = min(1.0, weights.max())
    base_price = float(model.predict(np.array([[high_relevance]]))[0])
    
    # Apply time-based discount
    # Faster sale = lower price, patient sale = closer to market price
    if target_days <= 7:
        discount = 0.88  # 12% discount for very quick sale
    elif target_days <= 14:
        discount = 0.92  # 8% discount
    elif target_days <= 30:
        discount = 0.96  # 4% discount
    else:
        discount = 1.0   # No discount
    
    predicted_price = base_price * discount
    
    # Ensure price is within reasonable bounds
    predicted_price = max(min_price * 0.7, min(predicted_price, max_price * 1.1))
    
    return {
        "ok": True,
        "predicted_price": round(float(predicted_price), 2),
        "target_days": int(target_days),
        "model_accuracy_mae": round(mae, 2) if mae > 0 else "N/A",
        "data_points": int(len(df)),
        "price_stats": {
            'min_price': min_price,
            'max_price': max_price,
            'avg_price': round(avg_price, 2),
            'median_price': median_price
        },
        "time_stats": {
            'base_price': round(base_price, 2),
            'discount_applied': f"{(1-discount)*100:.0f}%"
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
