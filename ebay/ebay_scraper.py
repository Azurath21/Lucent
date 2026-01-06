import requests
from bs4 import BeautifulSoup
import csv
import json
import argparse
import sys
import time
import random
import os
import re
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote_plus

class EbayScraper:
    INTERVALS_BY_MODE = {
        'ultra_fast': [15],
        'fast': [5, 15],
        'normal': [1, 5, 15, 30]
    }
    
    PAGES_BY_MODE = {
        'ultra_fast': 3,
        'fast': 5,
        'normal': 8
    }
    
    def __init__(self, item, brand="", model="", notes="", condition="3", min_price="0", 
                 max_price="", location="1", delay=2, mode='ultra_fast'):
        self.item = item
        self.brand = brand
        self.model = model
        self.notes = notes
        self.condition = condition
        self.min_price = min_price
        self.max_price = max_price
        self.location = location
        self.delay = delay
        self.mode = mode
        self.curdatetime = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session = requests.Session()
        
        os.makedirs('raw', exist_ok=True)
        os.makedirs('processed', exist_ok=True)
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        self.url = self.build_url()
    
    def build_url(self, page=1, days_listed=None):
        search_parts = [self.item]
        if self.brand: search_parts.append(self.brand)
        if self.model: search_parts.append(self.model)
        if self.notes: search_parts.append(self.notes)
        search_term = " ".join(search_parts)
        
        params = {
            '_nkw': search_term,
            '_sacat': '0',
            'rt': 'nc',
            '_sop': '10',
            '_ipg': '60',
        }
        
        if page > 1:
            params['_pgn'] = str(page)
        
        if self.min_price and self.min_price != "0":
            params['_udlo'] = self.min_price
        if self.max_price:
            params['_udhi'] = self.max_price
            
        if self.location == "1":
            params['LH_PrefLoc'] = '1'
            
        if self.condition and self.condition != "0":
            params['LH_ItemCondition'] = self.condition
        
        if days_listed is not None:
            params['LH_Complete'] = '1'
            params['LH_Sold'] = '1'
            params['_ftrt'] = '901'
            params['_ftrv'] = str(days_listed)
            
        base_url = "https://www.ebay.com.sg/sch/i.html"
        return f"{base_url}?{urlencode(params)}"
    
    def scrape_page(self, url):
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            listings = []
            
            items = []
            container_selectors = [
                'ul.srp-results li.s-item',
                'ul#srp-river-results li.s-item',
                'li.s-item',
                'div.s-item'
            ]
            for sel in container_selectors:
                items = soup.select(sel)
                if items:
                    break
            if not items:
                items = soup.find_all(lambda tag: tag.name in ['li', 'div'] and 's-item' in ' '.join(tag.get('class', [])))
            
            for item in items:
                try:
                    text_blob = item.get_text(" ", strip=True).upper()
                    if 'SPONSORED' in text_blob or 'ADCHOICES' in text_blob:
                        continue
                        
                    title_elem = item.select_one('div.s-item__title, h3.s-item__title, span[role="heading"]')
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    
                    title = re.sub(r'^New Listing\s*', '', title, flags=re.IGNORECASE)
                    title = re.sub(r'Opens in a new window or tab.*$', '', title, flags=re.IGNORECASE)
                    title = title.strip()
                    
                    if "Shop on eBay" in title or title == "":
                        continue
                    
                    price_elem = item.select_one('span.s-item__price')
                    price = ""
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price = price_text.replace('S$', '$').replace('SGD', '$').replace(',', '').strip()
                        if 'to' in price.lower():
                            price = price.split('to')[0].strip()
                    
                    link_elem = item.select_one('a.s-item__link') or item.find('a', href=True)
                    link = link_elem['href'] if link_elem and link_elem.has_attr('href') else ""
                    
                    item_id = ""
                    if link:
                        id_match = re.search(r'/itm/(\d+)', link)
                        if id_match:
                            item_id = id_match.group(1)
                    
                    if title and price:
                        listings.append({
                            'title': title,
                            'price': price,
                            'link': link,
                            'item_id': item_id
                        })
                        
                except Exception as e:
                    continue
            
            return listings
            
        except Exception as e:
            return []
    
    def scrape_with_intervals(self):
        max_pages = self.PAGES_BY_MODE.get(self.mode, 3)
        intervals = self.INTERVALS_BY_MODE.get(self.mode, [15])
        all_items = {}
        
        
        for days in intervals:
            items_in_interval = 0
            
            for page in range(1, max_pages + 1):
                url = self.build_url(page=page, days_listed=days)
                
                if page > 1 or days > intervals[0]:
                    time.sleep(random.uniform(0.5, self.delay))
                
                listings = self.scrape_page(url)
                
                if not listings:
                    break
                items_in_interval += len(listings)
                
                for item in listings:
                    item_id = item.get('item_id') or item.get('link') or item.get('title')
                    if not item_id:
                        continue
                    
                    if item_id not in all_items:
                        all_items[item_id] = {
                            'title': item['title'],
                            'price': item['price'],
                            'intervals': []
                        }
                    
                    if days not in all_items[item_id]['intervals']:
                        all_items[item_id]['intervals'].append(days)
            
        
        final_items = []
        for item_id, item_data in all_items.items():
            estimated_date = self.estimate_date_from_intervals(item_data['intervals'])
            final_items.append({
                'date': estimated_date,
                'title': item_data['title'],
                'price': item_data['price']
            })
        
        return final_items
    
    def estimate_date_from_intervals(self, intervals):
        ALL_INTERVALS = [1, 5, 15, 30]
        
        if not intervals:
            return datetime.now().strftime('%Y-%m-%d')
        
        intervals = sorted(intervals)
        min_interval = min(intervals)
        
        prev_interval = 0
        for interval in ALL_INTERVALS:
            if interval == min_interval:
                break
            prev_interval = interval
        
        days_ago = (prev_interval + min_interval) / 2
        
        estimated_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        return estimated_date
    
    def scrape_listings(self):
        return self.scrape_page(self.url)
    
    def save_to_csv(self, listings, filename=None):
        if filename is None:
            safe_item = re.sub(r'[^A-Za-z0-9]+', '', self.item)
            filename = os.path.join('processed', f"{self.curdatetime}_eBay_Search_{safe_item}.csv")
        
        if not listings:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Date', 'Item', 'Price'])
            return {"count": 0, "csv_path": filename}
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Date', 'Item', 'Price'])
            
            for listing in listings:
                writer.writerow([
                    listing.get('date', datetime.now().strftime('%Y-%m-%d')),
                    listing.get('title', ''),
                    listing.get('price', '')
                ])
        
        return {"count": len(listings), "csv_path": filename}
    
    def run_and_save(self):
        listings = self.scrape_with_intervals()
        result = self.save_to_csv(listings)
        
        return {
            "ok": True,
            "query_url": self.build_url(),
            "count": result["count"],
            "csv_path": result["csv_path"],
            "screenshot_path": ""
        }
    
    def close(self):
        try:
            self.session.close()
        except:
            pass

def main():
    parser = argparse.ArgumentParser(description="eBay scraper with CSV output")
    parser.add_argument("--item", required=True, help="Main item to search for")
    parser.add_argument("--brand", default="", help="Brand name")
    parser.add_argument("--model", default="", help="Model name")
    parser.add_argument("--notes", default="", help="Additional search terms")
    parser.add_argument("--condition", default="3", help="Condition: 1000=New, 3=Used, 7=For parts")
    parser.add_argument("--min_price", default="0", help="Minimum price")
    parser.add_argument("--max_price", default="", help="Maximum price")
    parser.add_argument("--location", default="1", help="Location preference: 1=Singapore")
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests")
    parser.add_argument("--mode", default="ultra_fast", choices=['ultra_fast', 'fast', 'normal'],
                        help="Speed mode: ultra_fast (5 pages), fast (10 pages), normal (15 pages)")
    
    args = parser.parse_args()
    
    try:
        scraper = EbayScraper(
            item=args.item,
            brand=args.brand,
            model=args.model,
            notes=args.notes,
            condition=args.condition,
            min_price=args.min_price,
            max_price=args.max_price,
            location=args.location,
            delay=args.delay,
            mode=args.mode
        )
        
        result = scraper.run_and_save()
        print(json.dumps(result))
        
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
    finally:
        try:
            scraper.close()
        except:
            pass

if __name__ == "__main__":
    main()
