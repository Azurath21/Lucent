#!/usr/bin/env python3

import requests
import re
import csv
import os
import time
import random
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

class FacebookRequestsScraper:
    
    def __init__(self, item='airpods max', min_price='200', max_price='', 
                 condition='new', location='singapore', days_since_listed=30, proxy=None):
        self.item = item
        self.min_price = min_price
        self.max_price = max_price
        self.condition = condition
        self.location = location
        self.days_since_listed = days_since_listed
        self.curdatetime = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        os.makedirs('raw', exist_ok=True)
        os.makedirs('processed', exist_ok=True)
        
        self.session = requests.Session()
        self.proxy = proxy
        self.setup_session()
    
    def setup_session(self):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        selected_ua = random.choice(user_agents)
        
        self.session.headers.update({
            'User-Agent': selected_ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })
        
        if self.proxy:
            self.session.proxies = {'http': self.proxy, 'https': self.proxy}
    
    def build_search_urls(self) -> List[str]:
        base_params = {
            'query': self.item,
            'exact': 'false'
        }
        
        if self.min_price:
            base_params['minPrice'] = self.min_price
        if self.max_price:
            base_params['maxPrice'] = self.max_price
            
        urls = [
            f"https://www.facebook.com/marketplace/search/?{urlencode(base_params)}",
            f"https://m.facebook.com/marketplace/search/?{urlencode(base_params)}",
            f"https://www.facebook.com/marketplace/singapore/search/?{urlencode(base_params)}",
        ]
        
        return urls
    
    def fetch_page(self, url: str, retries: int = 3) -> Optional[str]:
        for attempt in range(retries):
            try:
                
                time.sleep(random.uniform(1, 3))
                
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    response.encoding = response.apparent_encoding or 'utf-8'
                    content = response.text
                    
                    if 'login' in content.lower()[:1000]:
                        if attempt < retries - 1:
                            time.sleep(random.uniform(5, 10))
                            continue
                        else:
                            return content
                    
                    return content
                    
            except Exception:
                if attempt < retries - 1:
                    time.sleep(random.uniform(2, 5))
                    
        return None
    
    def extract_marketplace_data(self, html_content: str) -> List[Dict]:
        if not html_content:
            return []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        raw_path = os.path.join('raw', f"{self.curdatetime}_FacebookRequests.html")
        with open(raw_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        strategies = [
            self._extract_strategy_1,
            self._extract_strategy_2,
            self._extract_strategy_3
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                results = strategy(soup)
                if results:
                    listings.extend(results)
            except Exception:
                pass
        
        seen_titles = set()
        unique_listings = []
        for listing in listings:
            if listing['title'] not in seen_titles:
                seen_titles.add(listing['title'])
                unique_listings.append(listing)
        
        return unique_listings
    
    def _extract_strategy_1(self, soup) -> List[Dict]:
        listings = []
        marketplace_links = soup.find_all('a', href=re.compile(r'/marketplace/item/\d+'))
        
        for link in marketplace_links:
            try:
                container = link
                for _ in range(5):
                    parent = container.find_parent()
                    if not parent:
                        break
                    container = parent
                    if len(parent.find_all('span')) > 3:
                        break
                
                title = self._extract_title(link, container)
                price = self._extract_price(container)
                
                if title and len(title) > 3:
                    listings.append({
                        'title': title,
                        'price': price,
                        'date': 'Unknown',
                        'url': link.get('href', '')
                    })
                    
            except Exception:
                continue
                
        return listings
    
    def _extract_strategy_2(self, soup) -> List[Dict]:
        listings = []
        elements = soup.find_all(attrs={'data-testid': re.compile(r'marketplace')})
        
        for element in elements:
            try:
                title = self._extract_title_from_element(element)
                price = self._extract_price(element)
                
                if title and len(title) > 3:
                    listings.append({
                        'title': title,
                        'price': price,
                        'date': 'Unknown',
                        'url': ''
                    })
                    
            except Exception:
                continue
                
        return listings
    
    def _extract_strategy_3(self, soup) -> List[Dict]:
        listings = []
        
        price_pattern = re.compile(r'(SGD|S\$|\$)\s*[\d,]+')
        price_elements = soup.find_all(string=price_pattern)
        
        for price_text in price_elements:
            try:
                parent = price_text.parent
                if not parent:
                    continue
                
                container = parent
                for _ in range(3):
                    container = container.find_parent()
                    if not container:
                        break
                
                title = self._extract_title_from_element(container)
                price = price_pattern.search(price_text).group(0) if price_pattern.search(price_text) else ''
                
                if title and len(title) > 10:
                    listings.append({
                        'title': title,
                        'price': price,
                        'date': 'Unknown',
                        'url': ''
                    })
                    
            except Exception:
                continue
                
        return listings
    
    def _extract_title(self, link, container) -> str:
        if link.get('aria-label'):
            return link.get('aria-label').strip()
        
        spans = container.find_all('span')
        for span in spans:
            text = span.get_text(strip=True)
            if text and len(text) > 10 and not re.match(r'^[\$\d,\s]+$', text):
                return text
        
        return ''
    
    def _extract_title_from_element(self, element) -> str:
        texts = []
        
        all_text = element.get_text(strip=True)
        if all_text:
            texts.append(all_text)
        
        for tag in ['span', 'div', 'h1', 'h2', 'h3', 'a']:
            elements = element.find_all(tag)
            for el in elements:
                text = el.get_text(strip=True)
                if text and len(text) > 10:
                    texts.append(text)
        
        for text in sorted(texts, key=len, reverse=True):
            if len(text) > 10 and not re.match(r'^[\$\d,\s]+$', text):
                return text[:200]
        
        return ''
    
    def _extract_price(self, container) -> str:
        text = container.get_text()
        price_patterns = [
            r'SGD\s*[\d,]+',
            r'S\$\s*[\d,]+',
            r'\$[\d,]+'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return ''
    
    def save_to_csv(self, listings: List[Dict]) -> str:
        csv_path = os.path.join('processed', f"{self.curdatetime}_Facebook_Requests_{self.item.replace(' ', '')}.csv")
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Date', 'Item', 'Price']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for listing in listings:
                writer.writerow({
                    'Date': listing.get('date', 'Unknown'),
                    'Item': listing.get('title', ''),
                    'Price': listing.get('price', '')
                })
        
        print(f"Saved to CSV")
        return csv_path
    
    def scrape(self) -> Dict:
        
        urls = self.build_search_urls()
        all_listings = []
        
        for url in urls:
            print(f"\nTrying URL: {url}")
            html_content = self.fetch_page(url)
            
            if html_content:
                listings = self.extract_marketplace_data(html_content)
                all_listings.extend(listings)
                
                if listings:
                    break
        
        seen_titles = set()
        unique_listings = []
        for listing in all_listings:
            if listing['title'] not in seen_titles:
                seen_titles.add(listing['title'])
                unique_listings.append(listing)
        
        if unique_listings:
            csv_path = self.save_to_csv(unique_listings)
            return {
                'csv_path': csv_path,
                'count': len(unique_listings),
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
    scraper = FacebookRequestsScraper(
        item='airpods max',
        min_price='200',
        condition='new',
        days_since_listed=30
    )
    result = scraper.scrape()
    print(result)
