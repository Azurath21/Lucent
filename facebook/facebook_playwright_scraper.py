#!/usr/bin/env python3

import os
import csv
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from typing import List, Dict

class FacebookPlaywrightScraper:
    
    def __init__(self, item='road bike', min_price='0', max_price='', 
                 condition='new', location='singapore', days_since_listed=30, proxy=None):
        self.item = item
        self.min_price = min_price
        self.max_price = max_price
        self.condition = condition
        self.location = location
        self.days_since_listed = days_since_listed
        self.curdatetime = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.proxy = proxy
        
        os.makedirs('raw', exist_ok=True)
        os.makedirs('processed', exist_ok=True)
    
    def build_search_url(self) -> str:
        location_map = {
            'singapore': 'singapore',
            'kuala lumpur': 'kualalumpur',
            'bangkok': 'bangkok',
            'manila': 'manila',
            'jakarta': 'jakarta'
        }
        
        fb_location = location_map.get(self.location.lower(), 'singapore')
        query_encoded = self.item.replace(' ', '+')
        
        url = f'https://www.facebook.com/marketplace/{fb_location}/search/?query={query_encoded}'
        
        if self.min_price:
            url += f'&minPrice={self.min_price}'
        if self.max_price:
            url += f'&maxPrice={self.max_price}'
        
        return url
    
    def scrape_with_playwright(self) -> List[Dict]:
        url = self.build_search_url()
        print(f"Scraping URL: {url}")
        
        listings = []
        
        try:
            with sync_playwright() as p:
                launch_opts = {'headless': True}
                if self.proxy:
                    launch_opts['proxy'] = {'server': self.proxy}
                browser = p.chromium.launch(**launch_opts)
                page = browser.new_page()
                
                page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                
                page.goto(url, wait_until='networkidle')
                
                html_content = page.content()
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                raw_file = f"raw/{timestamp}_FacebookPlaywright.html"
                os.makedirs("raw", exist_ok=True)
                with open(raw_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                print(f"Page title: {page.title()}")
                print(f"Current URL: {page.url}")
                
                if "login" in page.url.lower() or "login" in page.title().lower():
                    pass
                    
                print(f"HTML content length: {len(html_content)} chars")
                
                soup = BeautifulSoup(html_content, 'html.parser')
                listings = self.extract_listings(soup)
                
                browser.close()
                
        except Exception as e:
            listings = []
            
        return listings
    
    def extract_listings(self, soup: BeautifulSoup) -> List[Dict]:
        listings = []
        
        try:
            items = soup.find_all('div', class_='x9f619 x78zum5 x1r8uery xdt5ytf x1iyjqo2 xs83m0k x1e558r4 x150jy0e x1iorvi4 xjkvuk6 xnpuxes x291uyu x1uepa24')
            
            for item in items:
                try:
                    img_elem = item.find('img', class_='xt7dq6l xl1xv1r x6ikm8r x10wlt62 xh8yej3')
                    image = img_elem['src'] if img_elem else ''
                    
                    title_elem = item.find('span', 'x1lliihq x6ikm8r x10wlt62 x1n2onr6')
                    title = title_elem.text.strip() if title_elem else ''
                    
                    price_elem = item.find('span', 'x193iq5w xeuugli x13faqbe x1vvkbs x1xmvt09 x1lliihq x1s928wv xhkezso x1gmr53x x1cpjm7i x1fgarty x1943h6x xudqn12 x676frb x1lkfr7t x1lbecb7 x1s688f xzsf02u')
                    price = price_elem.text.strip() if price_elem else ''
                    
                    location_elem = item.find('span', 'x1lliihq x6ikm8r x10wlt62 x1n2onr6 xlyipyv xuxw1ft x1j85h84')
                    location = location_elem.text.strip() if location_elem else ''
                    
                    url_elem = item.find('a', class_='x1i10hfl xjbqb8w x6umtig x1b1mbwd xaqea5y xav7gou x9f619 x1ypdohk xt0psk2 xe8uvvx xdj266r x11i5rnm xat24cr x1mh8g0r xexx8yu x4uap5 x18d9i69 xkhd6sd x16tdsg8 x1hl2dhg xggy1nq x1a2a7pz x1heor9g x1lku1pv')
                    post_url = url_elem['href'] if url_elem else ''
                    
                    if title and price:
                        listings.append({
                            'title': title,
                            'price': price,
                            'location': location,
                            'image': image,
                            'post_url': post_url,
                            'date': datetime.now().strftime('%Y-%m-%d')
                        })
                        print(f"Found item: {title} - {price}")
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            pass
        
        if not listings:
            try:
                items = soup.find_all('div', {'data-pagelet': True})
                
                for item in items:
                    price_spans = item.find_all('span', string=lambda text: text and ('$' in text or 'SGD' in text))
                    title_spans = item.find_all('span')
                    
                    for price_span in price_spans:
                        price_text = price_span.text.strip()
                        parent = price_span.parent
                        for _ in range(5):
                            if parent:
                                title_elem = parent.find('span')
                                if title_elem and title_elem != price_span:
                                    title_text = title_elem.text.strip()
                                    if len(title_text) > 5 and title_text != price_text:
                                        listings.append({
                                            'title': title_text,
                                            'price': price_text,
                                            'location': self.location,
                                            'image': '',
                                            'post_url': '',
                                            'date': datetime.now().strftime('%Y-%m-%d')
                                        })
                                        break
                                parent = parent.parent
                            else:
                                break
                                
            except Exception as e:
                pass
        
        print(f"Total listings extracted: {len(listings)}")
        return listings
    
    def save_to_csv(self, listings: List[Dict]) -> str:
        csv_path = os.path.join('processed', f"{self.curdatetime}_Facebook_Playwright_{self.item.replace(' ', '')}.csv")
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Date', 'Item', 'Price']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for listing in listings:
                writer.writerow({
                    'Date': listing.get('date', datetime.now().strftime('%Y-%m-%d')),
                    'Item': listing.get('title', ''),
                    'Price': listing.get('price', '')
                })
        
        print(f"Saved to CSV")
        return csv_path
    
    def scrape(self) -> Dict:
        print(f"Starting Playwright scraper for: {self.item}")
        
        listings = self.scrape_with_playwright()
        
        if listings:
            csv_path = self.save_to_csv(listings)
            return {
                'csv_path': csv_path,
                'count': len(listings),
                'status': 'success'
            }
        else:
            csv_path = self.save_to_csv([])
            return {
                'csv_path': csv_path,
                'count': 0,
                'status': 'no_data'
            }

if __name__ == "__main__":
    scraper = FacebookPlaywrightScraper(
        item='road bike',
        min_price='0',
        condition='new',
        days_since_listed=30
    )
    result = scraper.scrape()
    print(result)
