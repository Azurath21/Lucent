import requests
from bs4 import BeautifulSoup
import csv
import json
import argparse
import sys
import time
import random
from urllib.parse import urlencode, quote_plus

class EbayScraper:
    def __init__(self, item, brand="", model="", notes="", condition="3", min_price="0", max_price="", location="1", delay=2):
        self.item = item
        self.brand = brand
        self.model = model
        self.notes = notes
        self.condition = condition
        self.min_price = min_price
        self.max_price = max_price
        self.location = location
        self.delay = delay
        self.session = requests.Session()
        
        # Set realistic headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        self.url = self.build_url()
    
    def build_url(self):
        # Build search term
        search_parts = [self.item]
        if self.brand: search_parts.append(self.brand)
        if self.model: search_parts.append(self.model)
        if self.notes: search_parts.append(self.notes)
        search_term = " ".join(search_parts)
        
        # Build URL parameters
        params = {
            '_nkw': search_term,
            '_sacat': '0',
            'rt': 'nc'
        }
        
        # Add price filters
        if self.min_price and self.min_price != "0":
            params['_udlo'] = self.min_price
        if self.max_price:
            params['_udhi'] = self.max_price
            
        # Add location filter (Singapore)
        if self.location == "1":
            params['LH_PrefLoc'] = '1'
            
        # Add condition filter
        if self.condition and self.condition != "0":
            params['LH_ItemCondition'] = self.condition
            
        base_url = "https://www.ebay.com.sg/sch/i.html"
        return f"{base_url}?{urlencode(params)}"
    
    def scrape_listings(self):
        try:
            print(f"Scraping URL: {self.url}")
            response = self.session.get(self.url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            listings = []
            
            # Find listing containers with multiple fallback selectors
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
            # If still empty, try a very loose fallback
            if not items:
                items = soup.find_all(lambda tag: tag.name in ['li', 'div'] and 's-item' in ' '.join(tag.get('class', [])))
            
            for item in items:
                try:
                    # Skip sponsored/ad items (different variants)
                    text_blob = item.get_text(" ", strip=True).upper()
                    if 'SPONSORED' in text_blob or 'ADCHOICES' in text_blob:
                        continue
                        
                    # Extract title
                    title_elem = item.select_one('div.s-item__title, h3.s-item__title, span[role="heading"]')
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    
                    # Skip "Shop on eBay" entries
                    if "Shop on eBay" in title or title == "":
                        continue
                    
                    # Extract price
                    price_elem = item.select_one('span.s-item__price')
                    price = ""
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        # Clean price text
                        price = price_text.replace('S$', '').replace('SGD', '').replace('$', '').replace(',', '').strip()
                        # Handle price ranges (take the lower price)
                        if 'to' in price:
                            price = price.split('to')[0].strip()
                    
                    # Extract link
                    link_elem = item.select_one('a.s-item__link') or item.find('a', href=True)
                    link = link_elem['href'] if link_elem and link_elem.has_attr('href') else ""
                    
                    # Extract image
                    img_elem = item.select_one('img.s-item__image-img, img.s-item__image, img')
                    image = ""
                    if img_elem:
                        image = img_elem.get('src') or img_elem.get('data-src') or ""
                        if not image:
                            # Some images use srcset; take the first URL
                            srcset = img_elem.get('srcset', '')
                            if srcset:
                                image = srcset.split(',')[0].strip().split(' ')[0]
                    
                    # Extract condition
                    condition_elem = item.select_one('span.SECONDARY_INFO')
                    condition = condition_elem.get_text(strip=True) if condition_elem else "Used"
                    
                    # Extract location/shipping
                    shipping_elem = item.select_one('.s-item__shipping, .s-item__logisticsCost')
                    shipping = shipping_elem.get_text(strip=True) if shipping_elem else ""
                    
                    if title and price:
                        listings.append({
                            'title': title,
                            'price': price,
                            'link': link,
                            'image': image,
                            'condition': condition,
                            'shipping': shipping
                        })
                        
                except Exception as e:
                    print(f"Error parsing item: {e}")
                    continue
            
            return listings
            
        except Exception as e:
            print(f"Error scraping eBay: {e}")
            return []
    
    def save_to_csv(self, listings, filename="ebay_listings.csv"):
        if not listings:
            return {"count": 0, "csv_path": filename}
            
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['title', 'price', 'link', 'image', 'condition', 'shipping']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for listing in listings:
                writer.writerow(listing)
        
        return {"count": len(listings), "csv_path": filename}
    
    def run_and_save(self):
        # Add random delay to avoid being blocked
        time.sleep(random.uniform(1, self.delay))
        
        listings = self.scrape_listings()
        result = self.save_to_csv(listings, f"raw/ebay_{int(time.time())}.csv")
        
        return {
            "ok": True,
            "query_url": self.url,
            "count": result["count"],
            "csv_path": result["csv_path"],
            "screenshot_path": ""  # No screenshot for requests-based scraper
        }

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
            delay=args.delay
        )
        
        result = scraper.run_and_save()
        print(json.dumps(result))
        
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
