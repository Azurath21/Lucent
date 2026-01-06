#!/usr/bin/env python3

import sys
import os
from .facebook_marketplace_scraper import FacebookMarketplaceScraper

def test_facebook_scraper():
    scraper = None
    try:
        scraper = FacebookMarketplaceScraper(
            item='airpods max',
            min_price='200',
            condition='new',
            days_since_listed=30,
            mode='ultra_fast',
            headless=True
        )
        result = scraper.scrape_with_date_estimation()
        print(result)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if scraper:
            scraper.quit()

if __name__ == "__main__":
    test_facebook_scraper()
