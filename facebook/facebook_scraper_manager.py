#!/usr/bin/env python3

import os
import time
import random
from datetime import datetime
from typing import Dict, Optional, List

class FacebookScraperManager:
    
    def __init__(self, item='airpods max', min_price='200', max_price='', 
                 condition='new', location='singapore', days_since_listed=30):
        self.item = item
        self.min_price = min_price
        self.max_price = max_price
        self.condition = condition
        self.location = location
        self.days_since_listed = days_since_listed
        
        self.strategies = [
            self._try_requests_scraper,
            self._try_stealth_scraper,
            self._try_enhanced_selenium,
            self._try_playwright_scraper
        ]
    
    def scrape_with_fallback(self) -> Dict:
        for i, strategy in enumerate(self.strategies, 1):
            
            try:
                result = strategy()
                
                try:
                    from fix_csv_encoding import fix_corrupted_csvs
                    fix_corrupted_csvs()
                    
                    import glob
                    import os
                    clean_csvs = glob.glob('processed/*_clean.csv')
                    if clean_csvs:
                        latest_clean = max(clean_csvs, key=os.path.getctime)
                        result['csv_path'] = latest_clean
                        
                        valid_data_count = self._validate_csv_content(latest_clean)
                        if valid_data_count > 0:
                            result['count'] = valid_data_count
                            return result
                except Exception:
                    pass
                    
            except Exception:
                pass
            
            if i < len(self.strategies):
                wait_time = random.uniform(5, 10)
                time.sleep(wait_time)
        
        try:
            from fix_csv_encoding import fix_corrupted_csvs
            fix_corrupted_csvs()
        except Exception:
            pass
        
        return self._create_empty_result()
    
    def _try_requests_scraper(self) -> Optional[Dict]:
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
            
        except Exception:
            return None
    
    def _try_stealth_scraper(self) -> Optional[Dict]:
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
            return None
        except Exception:
            return None
    
    def _try_enhanced_selenium(self) -> Optional[Dict]:
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
            
            if isinstance(result, dict) and 'csv_path' in result:
                return result
            elif isinstance(result, str):
                return {'csv_path': result, 'count': self._count_csv_rows(result)}
            
            return None
            
        except Exception:
            return None
    
    def _try_playwright_scraper(self) -> Optional[Dict]:
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
            return None
        except Exception:
            return None
    
    def _count_csv_rows(self, csv_path: str) -> int:
        try:
            if not os.path.exists(csv_path):
                return 0
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return max(0, len(lines) - 1)
        except:
            return 0
    
    def _validate_csv_content(self, csv_path: str) -> int:
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
                    
                    if (item and item != 'No data - file was corrupted' and 
                        item != 'Unknown' and price and price != ''):
                        valid_count += 1
            
            return valid_count
        except:
            return 0
    
    def _create_empty_result(self) -> Dict:
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

if __name__ == "__main__":
    manager = FacebookScraperManager(item='airpods max', min_price='200', condition='new', days_since_listed=30)
    result = manager.scrape_with_fallback()
    print(result)
