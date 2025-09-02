#!/usr/bin/env python3

import sys
import os
from facebook_marketplace_scraper import FacebookMarketplaceScraper

def test_facebook_scraper():
    print("=== Facebook Scraper Debug Test ===")
    
    # Test with minimal parameters
    try:
        print("Creating scraper instance...")
        scraper = FacebookMarketplaceScraper(
            item='airpods max',
            min_price='200',
            condition='new',
            days_since_listed=30,
            mode='ultra_fast',
            headless=True
        )
        print("✓ Scraper created successfully")
        
        print("\nStarting scrape...")
        result = scraper.scrape_with_date_estimation()
        print(f"✓ Scraping completed. Result: {result}")
        
        # Check if CSV file was created
        if result and os.path.exists(result):
            print(f"✓ CSV file exists: {result}")
            with open(result, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"CSV file size: {len(content)} characters")
                if len(content) > 0:
                    lines = content.split('\n')
                    print(f"CSV has {len(lines)} lines")
                    if len(lines) > 1:
                        print(f"First few lines:\n{content[:500]}")
                    else:
                        print("CSV only has header row - no data extracted")
                else:
                    print("CSV file is empty")
        else:
            print("✗ CSV file not found or result is None")
            
        print("\nCleaning up...")
        scraper.quit()
        print("✓ Scraper closed")
        
    except Exception as e:
        print(f"✗ Error during scraping: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to cleanup
        try:
            scraper.quit()
        except:
            pass

if __name__ == "__main__":
    test_facebook_scraper()
