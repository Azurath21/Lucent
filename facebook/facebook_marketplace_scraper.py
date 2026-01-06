import os
import re
import csv
from datetime import datetime, timedelta
import time
import random
from urllib.request import urlopen, Request
from urllib.parse import quote
from typing import Optional
import requests

from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException


def find_chrome_binary() -> Optional[str]:
    env_path = os.environ.get("CHROME_BIN")
    if env_path and os.path.isfile(env_path):
        return env_path

    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path

    return None


class FacebookMarketplaceScraper(object):
    def __init__(self, item='air conditioner', min_price='200', max_price='', condition='new', 
                 location='singapore', days_since_listed=None, chromedriver_path='chromedriver.exe', 
                 headless=False, delay=20, mode='ultra_fast'):
        self.curdatetime = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.item = item
        self.min_price = min_price
        self.max_price = max_price
        self.condition = condition
        self.location = location
        self.days_since_listed = days_since_listed
        self.base_url = 'https://www.facebook.com'
        self.delay = delay
        self.mode = mode

        def map_condition(val):
            val_str = str(val).strip().lower()
            
            numeric_mapping = {
                '3': 'new',
                '4': 'used_like_new',
                '7': 'used_good',
                '5': 'used_good',
                '6': 'used_fair'
            }
            
            text_mapping = {
                'new': 'new',
                'brand new': 'new',
                'like new': 'used_like_new',
                'used_like_new': 'used_like_new',
                'lightly used': 'used_good',
                'used_good': 'used_good',
                'well used': 'used_good',
                'heavily used': 'used_fair',
                'used_fair': 'used_fair',
                'used': 'used_like_new,used_good,used_fair'
            }
            
            return numeric_mapping.get(val_str) or text_mapping.get(val_str, 'new')

        self.item_condition = map_condition(condition)
        self.encoded_item = quote(item)
        
        self.base_params = {
            'minPrice': min_price,
            'maxPrice': max_price,
            'itemCondition': self.item_condition,
            'query': self.encoded_item,
            'exact': 'false'
        }
        
        self.url = self.build_url(days_since_listed)
        print(f"Facebook Marketplace URL: {self.url}")
        
        self._init_chrome_driver(headless)

    def build_url(self, days_since_listed=None):
        url = f"{self.base_url}/marketplace/{self.location}/search?"
        params = []
        
        for key, value in self.base_params.items():
            if value:
                params.append(f"{key}={value}")
        
        if days_since_listed:
            params.append(f"daysSinceListed={days_since_listed}")
            
        return url + "&".join(params)

    def scrape_with_date_estimation(self):
        if self.mode == 'ultra_fast':
            return self.scrape_single_timeframe(self.days_since_listed)
        elif self.mode == 'fast':
            return self.scrape_with_interpolation('fast')
        elif self.mode == 'normal':
            return self.scrape_with_interpolation('normal')
        else:
            return self.scrape_single_timeframe(self.days_since_listed)

    def scrape_single_timeframe(self, days_since_listed):
        self.url = self.build_url(days_since_listed)
        print(f"Scraping with {days_since_listed} days since listed")
        
        self.load_facebook_url()
        result = self.extract_marketplace_items()
        
        if days_since_listed:
            estimated_date = (datetime.now() - timedelta(days=int(days_since_listed))).strftime('%Y-%m-%d')
            self.update_csv_with_estimated_dates(result['csv_path'], estimated_date)
        
        return result

    def scrape_with_interpolation(self, mode='fast'):
        if not self.days_since_listed:
            return self.scrape_single_timeframe(None)
        
        base_days = int(self.days_since_listed)
        
        if mode == 'fast':
            timeframes = [
                int(base_days * 0.5),
                base_days,
                int(base_days * 1.5)
            ]
        elif mode == 'normal':
            timeframes = [
                int(base_days * 0.4),
                int(base_days * 0.8),
                base_days,
                int(base_days * 1.4),
                int(base_days * 1.8)
            ]
        else:
            timeframes = [base_days]
        
        all_items = {}
        
        for i, days in enumerate(timeframes):
            print(f"Scraping timeframe {i+1}/{len(timeframes)}: {days} days since listed")
            
            self.url = self.build_url(days)
            self.load_facebook_url()
            
            html = self.driver.page_source
            soup = bs(html, 'lxml')
            marketplace_links = soup.find_all('a', href=re.compile(r'/marketplace/item/\d+'))
            
            for link in marketplace_links:
                href = link.get('href', '')
                if not href:
                    continue
                    
                title, price = self.extract_item_data(link, soup)
                if not title:
                    continue
                
                if href not in all_items:
                    all_items[href] = {
                        'title': title,
                        'price': price,
                        'timeframes': []
                    }
                
                all_items[href]['timeframes'].append(days)
        
        final_items = []
        for href, item_data in all_items.items():
            estimated_date = self.calculate_interpolated_date(item_data['timeframes'], timeframes)
            final_items.append({
                'date': estimated_date,
                'title': item_data['title'],
                'price': item_data['price']
            })
        
        return self.save_interpolated_results(final_items)

    def extract_item_data(self, link, soup):
        try:
            card_container = link
            for _ in range(8):
                parent = card_container.find_parent()
                if not parent:
                    break
                card_container = parent
                if len(parent.find_all('span')) > 5:
                    break
            
            title = ''
            if link.get('aria-label'):
                title = link.get('aria-label')
            else:
                spans = card_container.find_all('span')
                for span in spans:
                    text = span.get_text(strip=True)
                    if text and len(text) > 10 and not re.match(r'^[\$\d,\s]+$', text):
                        title = text
                        break
            
            price = ''
            card_text = card_container.get_text()
            price_patterns = [r'SGD\s?[\d,]+', r'\$[\d,]+', r'S\$\s?[\d,]+']
            
            for pattern in price_patterns:
                price_match = re.search(pattern, card_text)
                if price_match:
                    price = price_match.group(0)
                    break
            
            if title:
                title = re.sub(r'\s+', ' ', title).strip()
                for pattern in price_patterns:
                    title = re.sub(pattern, '', title).strip()
            
            return title, price
            
        except Exception as e:
            return '', ''

    def calculate_interpolated_date(self, found_timeframes, all_timeframes):
        if not found_timeframes:
            return ''
        
        found_timeframes.sort()
        all_timeframes.sort()
        
        if len(found_timeframes) == 1:
            days_ago = found_timeframes[0]
        elif len(found_timeframes) >= 2:
            min_days = min(found_timeframes)
            max_days = max(found_timeframes)
            
            if min_days == all_timeframes[0]:
                if all_timeframes[1] in found_timeframes:
                    days_ago = (min_days + all_timeframes[1]) / 2
                else:
                    days_ago = min_days
            else:
                prev_timeframe = 0
                for tf in all_timeframes:
                    if tf == min_days:
                        break
                    prev_timeframe = tf
                days_ago = (prev_timeframe + min_days) / 2
        else:
            days_ago = found_timeframes[0]
        
        estimated_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        return estimated_date

    def update_csv_with_estimated_dates(self, csv_path, estimated_date):
        try:
            rows = []
            with open(csv_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            for i in range(1, len(rows)):
                if len(rows[i]) > 0:
                    rows[i][0] = estimated_date
            
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
                
            print("CSV updated")
            
        except Exception as e:
            print("CSV update error")

    def save_interpolated_results(self, items):
        safe_item = re.sub(r'[^A-Za-z0-9]+', '', self.item)
        dest_path = os.path.join('processed', f"{self.curdatetime}_Facebook_Interpolated_{safe_item}.csv")
        
        with open(dest_path, 'w+', encoding='utf-8', newline='') as csvFile:
            writer = csv.writer(csvFile)
            writer.writerow(('Date', 'Item', 'Price'))
            
            for item in items:
                writer.writerow((
                    item['date'],
                    item['title'].strip(),
                    item['price'].strip()
                ))
        
        print(f'Saved interpolated results: {dest_path}')
        return {
            'csv_path': dest_path,
            'count': len(items),
            'screenshot_path': ''
        }

    def _init_chrome_driver(self, headless):
        chrome_options = Options()
        
        auto_headless = (
            headless or
            os.environ.get('HEADLESS', '').lower() == 'true' or
            not os.environ.get('DISPLAY')
        )
        if auto_headless:
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--window-size=1280,1024')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--metrics-recording-only')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--no-default-browser-check')
        chrome_options.add_argument('--mute-audio')
        chrome_options.add_argument('--hide-scrollbars')
        chrome_options.add_argument('--no-zygote')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        import random
        selected_ua = random.choice(user_agents)
        chrome_options.add_argument(f'--user-agent={selected_ua}')
        
        try:
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
        except Exception:
            pass
        
        chrome_options.add_argument('--lang=en-US')
        chrome_options.add_argument('--start-minimized')
        chrome_options.add_argument('--window-position=-4000,-4000')
        chrome_options.add_argument('--window-size=1,1')

        chrome_binary = find_chrome_binary()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
        
        chrome_options.page_load_strategy = 'none' if self.mode == 'ultra_fast' else 'eager'
        
        try:
            service = Service(log_output='chromedriver.log')
        except Exception:
            service = Service()
        
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        stealth_script = """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        
        // Remove automation indicators
        delete window.navigator.__proto__.webdriver;
        
        // Override plugins length
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
        
        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });
        """
        try:
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': stealth_script})
        except Exception:
            pass
        
        if not os.path.exists('raw'):
            os.mkdir('raw')
        if not os.path.exists('processed'):
            os.mkdir('processed')
    
    def load_facebook_url(self):
        try:
            self.driver.get(self.url)
        except Exception:
            pass
    
    def extract_marketplace_items(self):
        return {'csv_path': '', 'count': 0}
    
    def quit(self):
        try:
            self.driver.quit()
        except Exception:
            pass

if __name__ == '__main__':
    scraper = FacebookMarketplaceScraper(
        item='air conditioner',
        min_price='200',
        condition='new',
        days_since_listed=30,
        mode='fast'
    )
    result = scraper.scrape_with_date_estimation()
    scraper.quit()
    print(f"Scraped {result['count']} items, saved to {result['csv_path']}")
