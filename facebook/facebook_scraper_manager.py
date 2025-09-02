#!/usr/bin/env python3

import os
import time
import random
from datetime import datetime
from typing import Dict, Optional, List

class FacebookScraperManager:
    """
    Manages multiple Facebook scraping strategies with automatic fallback
    """
    
    def __init__(self, item='airpods max', min_price='200', max_price='', 
                 condition='new', location='singapore', days_since_listed=30):
        self.item = item
        self.min_price = min_price
        self.max_price = max_price
        self.condition = condition
        self.location = location
        self.days_since_listed = days_since_listed
        
        self.strategies = [
            self._try_requests_scraper,  # Strategy 3 first
            self._try_playwright_scraper,  # New Playwright strategy
            self._try_stealth_scraper,
            self._try_enhanced_selenium,
            self._try_proxy_scraper
        ]
    
    def scrape_with_fallback(self) -> Dict:
        """
        Try multiple scraping strategies with automatic fallback
        """
        print("Starting Facebook Marketplace scraping with multiple strategies...")
        
        for i, strategy in enumerate(self.strategies, 1):
            print(f"\nStrategy {i}/{len(self.strategies)}: {strategy.__name__}")
            
            try:
                result = strategy()
                
                # Run CSV encoding fix and validate content
                try:
                    from fix_csv_encoding import fix_corrupted_csvs
                    print("Running CSV encoding fix...")
                    fix_corrupted_csvs()
                    
                    # Update result with clean CSV if available
                    import glob
                    import os
                    clean_csvs = glob.glob('processed/*_clean.csv')
                    if clean_csvs:
                        latest_clean = max(clean_csvs, key=os.path.getctime)
                        result['csv_path'] = latest_clean
                        
                        # Validate CSV content - check for corrupted data
                        valid_data_count = self._validate_csv_content(latest_clean)
                        if valid_data_count > 0:
                            result['count'] = valid_data_count
                            print(f"Strategy {i} succeeded! Found {valid_data_count} valid items")
                            print(f"Using clean CSV: {latest_clean}")
                            return result
                        else:
                            print(f"Strategy {i} returned corrupted/placeholder data only")
                            # Continue to next strategy
                    else:
                        print(f"Strategy {i} returned no clean CSV")
                        # Continue to next strategy
                except Exception as e:
                    print(f"Warning: Could not run CSV encoding fix: {e}")
                    # Continue to next strategy
                else:
                    print(f"Strategy {i} returned no data")
                    # Continue to next strategy instead of returning early
                    
            except Exception as e:
                print(f"Strategy {i} failed: {e}")
            
            # Wait between strategies to avoid rate limiting (but not after last strategy)
            if i < len(self.strategies):
                wait_time = random.uniform(5, 10)  # Reduced wait time
                print(f"Waiting {wait_time:.1f}s before next strategy...")
                time.sleep(wait_time)
        
        print("All strategies failed - creating empty result")
        
        # Run CSV encoding fix after scraping
        try:
            from fix_csv_encoding import fix_corrupted_csvs
            print("Running CSV encoding fix...")
            fix_corrupted_csvs()
        except Exception as e:
            print(f"Warning: Could not run CSV encoding fix: {e}")
        
        return self._create_empty_result()
    
    def _try_stealth_scraper(self) -> Optional[Dict]:
        """Try undetected Chrome scraper"""
        try:
            from .facebook_stealth_scraper import FacebookStealthScraper
            
            scraper = FacebookStealthScraper(
                item=self.item,
                min_price=self.min_price,
                max_price=self.max_price,
                condition=self.condition,
                location=self.location,
                days_since_listed=self.days_since_listed
            )
            
            result = scraper.scrape_marketplace()
            scraper.quit()
            return result
            
        except ImportError:
            print("undetected-chromedriver not available, skipping stealth scraper")
            return None
        except Exception as e:
            print(f"Stealth scraper error: {e}")
            return None
    
    def _try_enhanced_selenium(self) -> Optional[Dict]:
        """Try enhanced Selenium scraper"""
        try:
            from .facebook_marketplace_scraper import FacebookMarketplaceScraper
            
            scraper = FacebookMarketplaceScraper(
                item=self.item,
                min_price=self.min_price,
                max_price=self.max_price,
                condition=self.condition,
                location=self.location,
                days_since_listed=self.days_since_listed,
                headless=True,
                mode='ultra_fast'
            )
            
            result = scraper.scrape_with_date_estimation()
            scraper.quit()
            
            # Convert result format if needed
            if isinstance(result, dict) and 'csv_path' in result:
                return result
            elif isinstance(result, str):
                return {'csv_path': result, 'count': self._count_csv_rows(result)}
            
            return None
            
        except Exception as e:
            print(f"Enhanced Selenium error: {e}")
            return None
    
    def _try_requests_scraper(self) -> Optional[Dict]:
        """Try requests-based scraper"""
        try:
            from .facebook_requests_scraper import FacebookRequestsScraper
            
            scraper = FacebookRequestsScraper(
                item=self.item,
                min_price=self.min_price,
                max_price=self.max_price,
                condition=self.condition,
                location=self.location,
                days_since_listed=self.days_since_listed
            )
            
            return scraper.scrape()
            
        except Exception as e:
            print(f"Requests scraper error: {e}")
            return None
    
    def _try_playwright_scraper(self) -> Optional[Dict]:
        """Try Playwright scraper (based on passivebot repo)"""
        try:
            from .facebook_playwright_scraper import FacebookPlaywrightScraper
            
            scraper = FacebookPlaywrightScraper(
                item=self.item,
                min_price=self.min_price,
                max_price=self.max_price,
                condition=self.condition,
                location=self.location,
                days_since_listed=self.days_since_listed
            )
            
            return scraper.scrape()
            
        except ImportError:
            print("Playwright not available, skipping Playwright scraper")
            return None
        except Exception as e:
            print(f"Playwright scraper error: {e}")
            return None
    
    def _try_proxy_scraper(self) -> Optional[Dict]:
        """Try proxy rotation scraper"""
        try:
            from .facebook_proxy_scraper import scrape_with_retry
            
            result = scrape_with_retry(self.item, max_retries=2)
            return result
            
        except Exception as e:
            print(f"Proxy scraper error: {e}")
            return None
    
    def _count_csv_rows(self, csv_path: str) -> int:
        """Count rows in CSV file (excluding header)"""
        try:
            if not os.path.exists(csv_path):
                return 0
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return max(0, len(lines) - 1)  # Exclude header
        except:
            return 0
    
    def _validate_csv_content(self, csv_path: str) -> int:
        """Validate CSV content and return count of valid data rows"""
        try:
            if not os.path.exists(csv_path):
                return 0
            
            import csv
            valid_count = 0
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    item = row.get('Item', '').strip()
                    price = row.get('Price', '').strip()
                    
                    # Skip corrupted/placeholder rows
                    if (item and item != 'No data - file was corrupted' and 
                        item != 'Unknown' and price and price != ''):
                        valid_count += 1
            
            return valid_count
        except:
            return 0
    
    def _create_empty_result(self) -> Dict:
        """Create empty CSV result when all strategies fail"""
        import csv
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = os.path.join('processed', f"{timestamp}_Facebook_Fallback_{self.item.replace(' ', '')}.csv")
        
        os.makedirs('processed', exist_ok=True)
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Date', 'Item', 'Price']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
        
        return {
            'csv_path': csv_path,
            'count': 0,
            'status': 'all_strategies_failed'
        }

def main():
    """Main function for testing"""
    manager = FacebookScraperManager(
        item='airpods max',
        min_price='200',
        condition='new',
        days_since_listed=30
    )
    
    result = manager.scrape_with_fallback()
    print(f"\nFinal Result: {result}")
    
    if result['count'] > 0:
        print(f"Successfully scraped {result['count']} items")
        print(f"Data saved to: {result['csv_path']}")
    else:
        print("No data found with any strategy")
        print("\nRecommendations:")
        print("   1. Try running at different times of day")
        print("   2. Use VPN to change IP location")
        print("   3. Consider using eBay or Carousell scrapers instead")
        print("   4. Set up rotating proxies for better success rate")

if __name__ == "__main__":
    main()
