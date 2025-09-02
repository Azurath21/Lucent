#!/usr/bin/env python3

import requests
import random
import time
from itertools import cycle
from facebook_marketplace_scraper import FacebookMarketplaceScraper

class FacebookProxyScraper(FacebookMarketplaceScraper):
    """
    Enhanced Facebook scraper with proxy rotation and session management
    """
    
    def __init__(self, *args, **kwargs):
        # Free proxy list (you can add paid proxies for better reliability)
        self.proxy_list = [
            # Add your proxy servers here
            # Format: 'http://username:password@proxy_ip:port'
            # For free proxies, check: https://free-proxy-list.net/
        ]
        self.proxy_cycle = cycle(self.proxy_list) if self.proxy_list else None
        super().__init__(*args, **kwargs)
    
    def get_random_proxy(self):
        """Get next proxy from rotation"""
        if self.proxy_cycle:
            return next(self.proxy_cycle)
        return None
    
    def _init_chrome_driver(self, headless):
        """Override to add proxy support"""
        proxy = self.get_random_proxy()
        if proxy:
            print(f"Using proxy: {proxy}")
            # Add proxy to Chrome options
            self.chrome_options.add_argument(f'--proxy-server={proxy}')
        
        return super()._init_chrome_driver(headless)

# Usage with proxy rotation
def scrape_with_retry(item, max_retries=3):
    """Retry scraping with different strategies"""
    
    strategies = [
        {'headless': True, 'mode': 'ultra_fast'},
        {'headless': False, 'mode': 'normal'},  # Sometimes non-headless works better
        {'headless': True, 'mode': 'slow'},     # Slower might avoid detection
    ]
    
    for attempt in range(max_retries):
        for i, strategy in enumerate(strategies):
            print(f"\n🔄 Attempt {attempt + 1}, Strategy {i + 1}: {strategy}")
            
            try:
                scraper = FacebookProxyScraper(
                    item=item,
                    min_price='200',
                    condition='new',
                    days_since_listed=30,
                    **strategy
                )
                
                result = scraper.scrape_with_date_estimation()
                scraper.quit()
                
                if result and result.get('count', 0) > 0:
                    print(f"✅ Success! Found {result['count']} items")
                    return result
                else:
                    print(f"❌ No data found with this strategy")
                    
            except Exception as e:
                print(f"❌ Strategy failed: {e}")
                try:
                    scraper.quit()
                except:
                    pass
            
            # Wait between strategies
            time.sleep(random.uniform(10, 20))
    
    print("❌ All strategies failed")
    return None

if __name__ == "__main__":
    result = scrape_with_retry('airpods max')
    print(f"Final result: {result}")
