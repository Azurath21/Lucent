#!/usr/bin/env python3

import pandas as pd
import sys

def debug_csv(csv_path):
    """Debug CSV file structure and data types"""
    try:
        print(f"Reading CSV: {csv_path}")
        df = pd.read_csv(csv_path)
        
        print(f"\nCSV Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        
        print("\nData Types:")
        print(df.dtypes)
        
        print("\nFirst few rows:")
        print(df.head())
        
        print("\nPrice column analysis:")
        print(f"Price dtype: {df['Price'].dtype}")
        print(f"Price values: {df['Price'].values}")
        print(f"Price unique values: {df['Price'].unique()}")
        
        # Test string operations
        print("\nTesting string operations:")
        try:
            df_test = df.copy()
            df_test['Price'] = df_test['Price'].astype(str)
            print("Successfully converted to string")
            
            df_test['Price_clean'] = df_test['Price'].str.replace('SGD', '').str.replace('S$', '').str.strip()
            print("Successfully applied string operations")
            print(f"Cleaned prices: {df_test['Price_clean'].values}")
            
            df_test['Price_numeric'] = pd.to_numeric(df_test['Price_clean'], errors='coerce')
            print(f"Numeric prices: {df_test['Price_numeric'].values}")
            
        except Exception as e:
            print(f"String operation error: {e}")
        
        return True
        
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_csv.py <csv_path>")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    debug_csv(csv_path)
