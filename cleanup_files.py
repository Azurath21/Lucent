#!/usr/bin/env python3

import os
import glob
from datetime import datetime

def cleanup_project_files():
    """Clean up irrelevant and duplicate files"""
    
    files_to_remove = []
    
    # 1. Remove corrupted CSV files (keep only clean ones)
    corrupted_csvs = glob.glob('processed/*Facebook*airpodsmax.csv')
    for csv_file in corrupted_csvs:
        if '_clean' not in csv_file and os.path.getsize(csv_file) < 100:
            files_to_remove.append(csv_file)
    
    # 2. Remove duplicate/test files
    test_files = [
        'test_facebook_scraper.py',  # Replaced by facebook_scraper_manager.py
        'fix_csv_encoding.py',       # One-time utility, no longer needed
    ]
    files_to_remove.extend(test_files)
    
    # 3. Remove old raw HTML files (keep latest 2)
    raw_files = glob.glob('raw/*.html')
    raw_files.sort(key=os.path.getmtime)
    if len(raw_files) > 4:  # Keep latest 4
        files_to_remove.extend(raw_files[:-4])
    
    # 4. Identify irrelevant directories/files
    irrelevant_items = [
        '--item=Your browser does not support HTML5 video. Ready Stock Baby Foldable Rocking Swinging High Chair S Brand new/',
        'chromedriver.log',  # Large log file
        'dist/',  # Build artifacts
        'node_modules/',  # Can be regenerated
        '.venv/',  # Virtual environment
        '__pycache__/',  # Python cache
    ]
    
    print("🧹 Project Cleanup Analysis")
    print("=" * 50)
    
    print("\n📁 Files to remove:")
    for item in files_to_remove:
        if os.path.exists(item):
            size = os.path.getsize(item)
            print(f"  - {item} ({size} bytes)")
    
    print(f"\n📂 Irrelevant directories (recommend manual cleanup):")
    for item in irrelevant_items:
        if os.path.exists(item):
            if os.path.isdir(item):
                try:
                    size = sum(os.path.getsize(os.path.join(dirpath, filename))
                              for dirpath, dirnames, filenames in os.walk(item)
                              for filename in filenames)
                    print(f"  - {item}/ ({size:,} bytes)")
                except:
                    print(f"  - {item}/ (directory)")
            else:
                size = os.path.getsize(item)
                print(f"  - {item} ({size:,} bytes)")
    
    return files_to_remove

def identify_core_files():
    """Identify core project files"""
    
    core_files = {
        'Web Interface': [
            'server.js',
            'web/',
            'templates/',
            'package.json'
        ],
        'Scrapers': [
            'facebook_marketplace_scraper.py',
            'facebook_scraper_manager.py',
            'facebook_requests_scraper.py',
            'facebook_stealth_scraper.py',
            'facebook_proxy_scraper.py',
            'run_carousell_scraper.py'
        ],
        'Utilities': [
            'csv_score.py',
            'price_predictor.py',
            'merge_csvs.py',
            'scrape_cli.py'
        ],
        'Data': [
            'processed/',
            'raw/'
        ],
        'Config': [
            'requirements.txt',
            'Dockerfile',
            '.gitignore',
            'README.md'
        ]
    }
    
    print("\n📋 Core Project Structure:")
    for category, files in core_files.items():
        print(f"\n{category}:")
        for file in files:
            if os.path.exists(file):
                if os.path.isdir(file):
                    count = len(os.listdir(file))
                    print(f"  ✅ {file} ({count} items)")
                else:
                    size = os.path.getsize(file)
                    print(f"  ✅ {file} ({size:,} bytes)")
            else:
                print(f"  ❌ {file} (missing)")

if __name__ == "__main__":
    cleanup_project_files()
    identify_core_files()
