#!/usr/bin/env python3

import os
import csv
import glob
from datetime import datetime

def fix_corrupted_csvs():
    """Fix corrupted CSV files in the processed directory"""
    
    processed_dir = 'processed'
    if not os.path.exists(processed_dir):
        print("No processed directory found")
        return
    
    # Find all CSV files
    csv_files = glob.glob(os.path.join(processed_dir, '*.csv'))
    
    for csv_file in csv_files:
        print(f"\nChecking: {csv_file}")
        
        try:
            # Try to read the file and detect corruption
            with open(csv_file, 'rb') as f:
                raw_data = f.read()
            
            # Check if file contains BOM or corruption markers
            if b'\xef\xbf\xbd' in raw_data or len(raw_data) < 50:
                print(f"Corrupted file detected: {csv_file}")
                
                # Create a clean version
                clean_csv_path = csv_file.replace('.csv', '_clean.csv')
                
                with open(clean_csv_path, 'w', newline='', encoding='utf-8') as clean_file:
                    writer = csv.writer(clean_file)
                    writer.writerow(['Date', 'Item', 'Price'])
                    writer.writerow(['Unknown', 'No data - file was corrupted', ''])
                
                print(f"Created clean version: {clean_csv_path}")
            else:
                # Try to read as normal CSV
                try:
                    with open(csv_file, 'r', encoding='utf-8') as f:
                        reader = csv.reader(f)
                        rows = list(reader)
                        if len(rows) > 1:
                            print(f"File appears clean with {len(rows)-1} data rows")
                        else:
                            print(f"File only has header row")
                except Exception as e:
                    print(f"Error reading file: {e}")
                    
        except Exception as e:
            print(f"Error processing {csv_file}: {e}")

def create_test_csv():
    """Create a test CSV with proper encoding"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    test_csv = os.path.join('processed', f"{timestamp}_Test_Clean.csv")
    
    os.makedirs('processed', exist_ok=True)
    
    with open(test_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Date', 'Item', 'Price'])
        writer.writerow(['2025-09-01', 'AirPods Max - Space Gray', 'SGD 450'])
        writer.writerow(['2025-09-01', 'AirPods Max - Silver', 'SGD 480'])
    
    print(f"Created test CSV: {test_csv}")
    return test_csv

if __name__ == "__main__":
    print("CSV Encoding Fix Utility")
    print("=" * 40)
    
    # Fix existing corrupted files
    fix_corrupted_csvs()
    
    # Create a test file with proper encoding
    print("\nCreating test CSV with proper encoding...")
    test_file = create_test_csv()
    
    print(f"\nDone! Test opening: {test_file}")
