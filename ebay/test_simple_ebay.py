#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import csv
import os
import time
import random

def test_ebay_simple():
    # Create raw directory if it doesn't exist
    os.makedirs("raw", exist_ok=True)
    
    # Test URL - airpods 4, used condition, min price 100, Singapore
    url = "https://www.ebay.com.sg/sch/i.html?_nkw=airpods+4&_sacat=0&_udlo=100&LH_PrefLoc=1&rt=nc&LH_ItemCondition=3"
    
    print(f"Testing eBay scraper with anti-bot measures...")
    print(f"URL: {url}")
    
    # Enhanced headers with more realistic browser simulation
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }
    
    # Create session with cookies
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"Failed to fetch page: {response.status_code}")
            return
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Save HTML for debugging
        with open('debug_ebay.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("Saved HTML to debug_ebay.html for inspection")
        
        # Debug: Check what containers exist
        print("Debugging HTML structure...")
        
        # Try multiple possible selectors
        selectors_to_try = [
            ('div', 's-item'),
            ('div', 'srp-item'), 
            ('div', 'it-ttl'),
            ('li', 's-item'),
            ('div', {'data-testid': 'item-card'}),
            ('div', {'class': lambda x: x and 'item' in x.lower() if x else False}),
            ('div', {'class': lambda x: x and 'srp' in x.lower() if x else False}),
            ('article', None),
            ('li', None),
        ]
        
        items = []
        for tag, class_attr in selectors_to_try:
            if isinstance(class_attr, str):
                found = soup.find_all(tag, class_=class_attr)
            else:
                found = soup.find_all(tag, class_attr)
            print(f"  {tag}.{class_attr}: {len(found)} items")
            if found and len(found) > len(items):
                items = found
        
        print(f"Using best match: {len(items)} item containers")
        
        listings = []
        
        for i, item in enumerate(items):
            try:
                # Try multiple title selectors
                title_elem = (item.find('h3', class_='s-item__title') or 
                            item.find('h3', class_='it-ttl') or
                            item.find('a', class_='s-item__link'))
                
                if not title_elem:
                    continue
                    
                title = title_elem.get_text(strip=True)
                
                # Skip ads and empty titles
                if not title or "Shop on eBay" in title or title == "":
                    continue
                
                # Try multiple price selectors
                price_elem = (item.find('span', class_='s-item__price') or
                            item.find('span', class_='notranslate') or
                            item.find('span', {'class': lambda x: x and 'price' in x.lower() if x else False}))
                
                price = ""
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price = price_text.replace('S$', '').replace('$', '').replace(',', '').strip()
                    if 'to' in price:
                        price = price.split('to')[0].strip()
                    # Remove any non-numeric characters except decimal point
                    import re
                    price_match = re.search(r'[\d.]+', price)
                    if price_match:
                        price = price_match.group()
                
                # Get link
                link_elem = item.find('a', class_='s-item__link')
                link = link_elem['href'] if link_elem else ""
                
                # Get condition
                condition_elem = item.find('span', class_='SECONDARY_INFO')
                condition = condition_elem.get_text(strip=True) if condition_elem else "Used"
                
                if title and price:
                    listing = {
                        'title': title,
                        'price': price,
                        'link': link,
                        'condition': condition
                    }
                    listings.append(listing)
                    print(f"  {len(listings)}. {title} - S${price}")
                    
            except Exception as e:
                print(f"Error parsing item {i}: {e}")
                continue
        
        # Save to CSV
        if listings:
            csv_filename = f"raw/ebay_test_{int(time.time())}.csv"
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['title', 'price', 'link', 'condition']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for listing in listings:
                    writer.writerow(listing)
            
            print(f"\nSaved {len(listings)} listings to {csv_filename}")
            print(f"SUCCESS: eBay scraper working!")
            
            # Output JSON result
            result = {
                "ok": True,
                "count": len(listings),
                "csv_path": csv_filename,
                "query_url": url
            }
            print(f"\nJSON Output: {result}")
            
        else:
            print("No valid listings found")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_ebay_simple()
