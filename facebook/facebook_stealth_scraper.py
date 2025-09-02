#!/usr/bin/env python3

import undetected_chromedriver as uc
import time
import random
import os
import csv
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re

class FacebookStealthScraper:
    """
    Facebook scraper using undetected-chromedriver to bypass anti-bot detection
    """
    
    def __init__(self, item='airpods max', min_price='200', max_price='', 
                 condition='new', location='singapore', days_since_listed=30):
        self.item = item
        self.min_price = min_price
        self.max_price = max_price
        self.condition = condition
        self.location = location
        self.days_since_listed = days_since_listed
        self.curdatetime = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create directories
        os.makedirs('raw', exist_ok=True)
        os.makedirs('processed', exist_ok=True)
        
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Setup undetected Chrome driver"""
        try:
            options = uc.ChromeOptions()
            
            # Basic stealth options
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-extensions')
            
            # Randomize window size
            width = random.randint(1200, 1920)
            height = random.randint(800, 1080)
            options.add_argument(f'--window-size={width},{height}')
            
            # Random user agent
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            options.add_argument(f'--user-agent={random.choice(user_agents)}')
            
            self.driver = uc.Chrome(options=options)
            print("✅ Stealth Chrome driver initialized")
            
        except Exception as e:
            print(f"❌ Failed to setup stealth driver: {e}")
            print("💡 Install undetected-chromedriver: pip install undetected-chromedriver")
            raise
    
    def build_facebook_url(self):
        """Build Facebook Marketplace search URL"""
        base_url = "https://www.facebook.com/marketplace/search/?"
        params = []
        
        if self.item:
            params.append(f"query={self.item.replace(' ', '%20')}")
        if self.min_price:
            params.append(f"minPrice={self.min_price}")
        if self.max_price:
            params.append(f"maxPrice={self.max_price}")
        
        params.append("exact=false")
        
        return base_url + "&".join(params)
    
    def human_like_behavior(self):
        """Simulate human-like browsing behavior"""
        # Random scrolling
        scroll_pause = random.uniform(1, 3)
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/4);")
        time.sleep(scroll_pause)
        
        # Random mouse movements (simulated via JavaScript)
        self.driver.execute_script("""
            var event = new MouseEvent('mousemove', {
                'view': window,
                'bubbles': true,
                'cancelable': true,
                'clientX': Math.random() * window.innerWidth,
                'clientY': Math.random() * window.innerHeight
            });
            document.dispatchEvent(event);
        """)
        
        time.sleep(random.uniform(0.5, 2))
    
    def bypass_login_redirect(self):
        """Try to bypass login redirects"""
        current_url = self.driver.current_url.lower()
        page_source = self.driver.page_source.lower()
        
        if 'login' in current_url or 'login' in page_source[:1000]:
            print("🔄 Detected login redirect, trying bypass...")
            
            # Strategy 1: Try going back and forward
            try:
                self.driver.back()
                time.sleep(2)
                self.driver.forward()
                time.sleep(3)
            except:
                pass
            
            # Strategy 2: Try refreshing
            try:
                self.driver.refresh()
                time.sleep(5)
            except:
                pass
            
            # Strategy 3: Try mobile version
            try:
                mobile_url = self.build_facebook_url().replace('www.facebook.com', 'm.facebook.com')
                self.driver.get(mobile_url)
                time.sleep(5)
            except:
                pass
            
            # Check if bypass worked
            current_url = self.driver.current_url.lower()
            if 'login' not in current_url:
                print("✅ Login bypass successful")
                return True
            else:
                print("❌ Login bypass failed")
                return False
        
        return True
    
    def scrape_marketplace(self):
        """Main scraping method"""
        try:
            url = self.build_facebook_url()
            print(f"🔍 Navigating to: {url}")
            
            # Navigate with human-like delay
            self.driver.get(url)
            time.sleep(random.uniform(3, 7))
            
            # Try to bypass login if needed
            if not self.bypass_login_redirect():
                print("⚠️ Could not bypass login, continuing anyway...")
            
            # Human-like behavior
            self.human_like_behavior()
            
            # Wait for content to load
            try:
                wait = WebDriverWait(self.driver, 15)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except:
                pass
            
            # Additional wait and scroll
            time.sleep(5)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(3)
            
            # Save page source
            page_source = self.driver.page_source
            raw_path = os.path.join('raw', f"{self.curdatetime}_FacebookStealth.html")
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(page_source)
            print(f"📄 Saved page source: {raw_path}")
            
            # Extract data
            listings = self.extract_listings(page_source)
            
            # Save to CSV
            csv_path = self.save_to_csv(listings)
            
            return {
                'csv_path': csv_path,
                'count': len(listings),
                'status': 'success' if listings else 'no_data'
            }
            
        except Exception as e:
            print(f"❌ Scraping failed: {e}")
            return {'csv_path': None, 'count': 0, 'status': 'error'}
    
    def extract_listings(self, html_content):
        """Extract marketplace listings from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        listings = []
        
        print("🔍 Extracting listings...")
        
        # Check if we're on a login page
        if 'login' in html_content.lower()[:1000]:
            print("❌ Still on login page - no data to extract")
            return []
        
        # Multiple extraction strategies
        strategies = [
            self._extract_marketplace_links,
            self._extract_by_price_patterns,
            self._extract_by_data_testid
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                results = strategy(soup)
                if results:
                    print(f"✅ Strategy {i+1} found {len(results)} listings")
                    listings.extend(results)
                    break
                else:
                    print(f"❌ Strategy {i+1} found no listings")
            except Exception as e:
                print(f"❌ Strategy {i+1} failed: {e}")
        
        # Remove duplicates
        unique_listings = []
        seen_titles = set()
        for listing in listings:
            title = listing.get('title', '').strip()
            if title and title not in seen_titles and len(title) > 5:
                seen_titles.add(title)
                unique_listings.append(listing)
        
        print(f"📊 Final count: {len(unique_listings)} unique listings")
        return unique_listings
    
    def _extract_marketplace_links(self, soup):
        """Extract via marketplace item links"""
        listings = []
        links = soup.find_all('a', href=re.compile(r'/marketplace/item/\d+'))
        
        for link in links:
            try:
                # Find parent container
                container = link
                for _ in range(6):
                    parent = container.find_parent()
                    if not parent:
                        break
                    container = parent
                
                title = self._extract_title(link, container)
                price = self._extract_price(container)
                
                if title and len(title) > 5:
                    listings.append({
                        'title': title,
                        'price': price,
                        'date': 'Unknown'
                    })
            except:
                continue
        
        return listings
    
    def _extract_by_price_patterns(self, soup):
        """Extract by finding price patterns"""
        listings = []
        price_pattern = re.compile(r'(SGD|S\$|\$)\s*[\d,]+')
        
        for text in soup.find_all(string=price_pattern):
            try:
                parent = text.parent
                for _ in range(4):
                    parent = parent.find_parent() if parent else None
                    if not parent:
                        break
                
                if parent:
                    title = self._extract_title_from_element(parent)
                    price_match = price_pattern.search(text)
                    price = price_match.group(0) if price_match else ''
                    
                    if title and len(title) > 10:
                        listings.append({
                            'title': title,
                            'price': price,
                            'date': 'Unknown'
                        })
            except:
                continue
        
        return listings
    
    def _extract_by_data_testid(self, soup):
        """Extract by data-testid attributes"""
        listings = []
        elements = soup.find_all(attrs={'data-testid': re.compile(r'marketplace')})
        
        for element in elements:
            try:
                title = self._extract_title_from_element(element)
                price = self._extract_price(element)
                
                if title and len(title) > 5:
                    listings.append({
                        'title': title,
                        'price': price,
                        'date': 'Unknown'
                    })
            except:
                continue
        
        return listings
    
    def _extract_title(self, link, container):
        """Extract title from link or container"""
        if link.get('aria-label'):
            return link.get('aria-label').strip()
        
        spans = container.find_all('span')
        for span in spans:
            text = span.get_text(strip=True)
            if text and len(text) > 10 and not re.match(r'^[\$\d,\s]+$', text):
                return text
        
        return ''
    
    def _extract_title_from_element(self, element):
        """Extract title from any element"""
        texts = []
        
        # Get all meaningful text
        for tag in ['span', 'div', 'h1', 'h2', 'h3', 'a']:
            for el in element.find_all(tag):
                text = el.get_text(strip=True)
                if text and len(text) > 10:
                    texts.append(text)
        
        # Return longest meaningful text
        for text in sorted(texts, key=len, reverse=True):
            if len(text) > 10 and not re.match(r'^[\$\d,\s\W]+$', text):
                return text[:200]
        
        return ''
    
    def _extract_price(self, container):
        """Extract price from container"""
        text = container.get_text()
        patterns = [r'SGD\s*[\d,]+', r'S\$\s*[\d,]+', r'\$[\d,]+']
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return ''
    
    def save_to_csv(self, listings):
        """Save listings to CSV"""
        csv_path = os.path.join('processed', f"{self.curdatetime}_Facebook_Stealth_{self.item.replace(' ', '')}.csv")
        
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
        
        print(f"💾 Saved to: {csv_path}")
        return csv_path
    
    def quit(self):
        """Clean up driver"""
        if self.driver:
            try:
                self.driver.quit()
                print("🔒 Driver closed")
            except:
                pass

if __name__ == "__main__":
    scraper = FacebookStealthScraper(
        item='airpods max',
        min_price='200',
        condition='new'
    )
    
    try:
        result = scraper.scrape_marketplace()
        print(f"🎯 Final result: {result}")
    finally:
        scraper.quit()
