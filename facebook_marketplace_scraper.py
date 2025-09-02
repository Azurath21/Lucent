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
    """Attempt to locate the Chrome executable on Windows.
    Honors CHROME_BIN env var first, then checks common install paths.
    """
    # 1) Environment override
    env_path = os.environ.get("CHROME_BIN")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2) Common Windows locations
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
        # For data logging
        self.curdatetime = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.item = item
        self.min_price = min_price
        self.max_price = max_price
        self.condition = condition
        self.location = location
        self.days_since_listed = days_since_listed
        self.base_url = 'https://www.facebook.com'
        self.delay = delay
        self.mode = mode  # 'ultra_fast', 'fast', 'normal'

        # Map condition to Facebook's itemCondition parameter
        def map_condition(val):
            # Handle both numeric (from Carousell) and text (from Facebook) conditions
            val_str = str(val).strip().lower()
            
            # Numeric mappings (from Carousell form)
            numeric_mapping = {
                '3': 'new',                    # Brand new
                '4': 'used_like_new',          # Like new
                '7': 'used_good',              # Lightly used
                '5': 'used_good',              # Well used
                '6': 'used_fair'               # Heavily used
            }
            
            # Text mappings (direct Facebook conditions)
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
                'used': 'used_like_new,used_good,used_fair'  # All used conditions
            }
            
            # Try numeric mapping first, then text mapping
            return numeric_mapping.get(val_str) or text_mapping.get(val_str, 'new')

        self.item_condition = map_condition(condition)
        self.encoded_item = quote(item)
        
        # Store base URL parameters for multiple queries
        self.base_params = {
            'minPrice': min_price,
            'maxPrice': max_price,
            'itemCondition': self.item_condition,
            'query': self.encoded_item,
            'exact': 'false'
        }
        
        # Build initial URL
        self.url = self.build_url(days_since_listed)
        print(f"Facebook Marketplace URL: {self.url}")
        
        # Initialize Chrome driver
        self._init_chrome_driver(headless)

    def build_url(self, days_since_listed=None):
        """Build Facebook Marketplace URL with optional daysSinceListed parameter"""
        url = f"{self.base_url}/marketplace/{self.location}/search?"
        params = []
        
        for key, value in self.base_params.items():
            if value:
                params.append(f"{key}={value}")
        
        if days_since_listed:
            params.append(f"daysSinceListed={days_since_listed}")
            
        return url + "&".join(params)

    def scrape_with_date_estimation(self):
        """Main scraping method that handles date estimation based on mode"""
        if self.mode == 'ultra_fast':
            # Ultra fast mode: single query with specified days
            return self.scrape_single_timeframe(self.days_since_listed)
        elif self.mode == 'fast':
            # Fast mode: 3 queries (0.5x, 1x, 1.5x)
            return self.scrape_with_interpolation('fast')
        elif self.mode == 'normal':
            # Normal mode: 5 queries (0.4x, 0.8x, 1x, 1.4x, 1.8x)
            return self.scrape_with_interpolation('normal')
        else:
            return self.scrape_single_timeframe(self.days_since_listed)

    def scrape_single_timeframe(self, days_since_listed):
        """Scrape with a single daysSinceListed value"""
        self.url = self.build_url(days_since_listed)
        print(f"Scraping with {days_since_listed} days since listed")
        
        self.load_facebook_url()
        result = self.extract_marketplace_items()
        
        # Estimate date based on days_since_listed
        if days_since_listed:
            estimated_date = (datetime.now() - timedelta(days=int(days_since_listed))).strftime('%Y-%m-%d')
            # Update all items with estimated date
            self.update_csv_with_estimated_dates(result['csv_path'], estimated_date)
        
        return result

    def scrape_with_interpolation(self, mode='fast'):
        """Scrape with multiple timeframes for date interpolation"""
        if not self.days_since_listed:
            return self.scrape_single_timeframe(None)
        
        base_days = int(self.days_since_listed)
        
        if mode == 'fast':
            timeframes = [
                int(base_days * 0.5),   # 0.5x
                base_days,              # 1x  
                int(base_days * 1.5)    # 1.5x
            ]
        elif mode == 'normal':
            timeframes = [
                int(base_days * 0.4),   # 0.4x
                int(base_days * 0.8),   # 0.8x
                base_days,              # 1x
                int(base_days * 1.4),   # 1.4x
                int(base_days * 1.8)    # 1.8x
            ]
        else:
            timeframes = [base_days]
        
        all_items = {}  # href -> {title, price, timeframes_found}
        
        for i, days in enumerate(timeframes):
            print(f"Scraping timeframe {i+1}/{len(timeframes)}: {days} days since listed")
            
            self.url = self.build_url(days)
            self.load_facebook_url()
            
            # Extract items for this timeframe
            html = self.driver.page_source
            soup = bs(html, 'lxml')
            marketplace_links = soup.find_all('a', href=re.compile(r'/marketplace/item/\d+'))
            
            for link in marketplace_links:
                href = link.get('href', '')
                if not href:
                    continue
                    
                # Extract item data
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
        
        # Calculate estimated dates based on timeframe appearances
        final_items = []
        for href, item_data in all_items.items():
            estimated_date = self.calculate_interpolated_date(item_data['timeframes'], timeframes)
            final_items.append({
                'date': estimated_date,
                'title': item_data['title'],
                'price': item_data['price']
            })
        
        # Save combined results
        return self.save_interpolated_results(final_items)

    def extract_item_data(self, link, soup):
        """Extract title and price for a single item link"""
        try:
            # Navigate up to find the card container
            card_container = link
            for _ in range(8):
                parent = card_container.find_parent()
                if not parent:
                    break
                card_container = parent
                if len(parent.find_all('span')) > 5:
                    break
            
            # Extract title
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
            
            # Extract price
            price = ''
            card_text = card_container.get_text()
            price_patterns = [r'SGD\s?[\d,]+', r'\$[\d,]+', r'S\$\s?[\d,]+']
            
            for pattern in price_patterns:
                price_match = re.search(pattern, card_text)
                if price_match:
                    price = price_match.group(0)
                    break
            
            # Clean up title
            if title:
                title = re.sub(r'\s+', ' ', title).strip()
                for pattern in price_patterns:
                    title = re.sub(pattern, '', title).strip()
            
            return title, price
            
        except Exception as e:
            print(f"Error extracting item data: {e}")
            return '', ''

    def calculate_interpolated_date(self, found_timeframes, all_timeframes):
        """Calculate estimated date based on which timeframes the item appeared in"""
        if not found_timeframes:
            return ''
        
        # Sort timeframes to find the range
        found_timeframes.sort()
        all_timeframes.sort()
        
        if len(found_timeframes) == 1:
            # Item found in only one timeframe - use that as estimate
            days_ago = found_timeframes[0]
        elif len(found_timeframes) >= 2:
            # Item found in multiple timeframes - take midpoint of smallest range
            min_days = min(found_timeframes)
            max_days = max(found_timeframes)
            
            # Find the gap where item first appears
            if min_days == all_timeframes[0]:  # Found in 0.5x
                if all_timeframes[1] in found_timeframes:  # Also in 1x
                    days_ago = (min_days + all_timeframes[1]) / 2
                else:
                    days_ago = min_days
            else:
                # Not in smallest timeframe, so between previous timeframe and this one
                prev_timeframe = 0
                for tf in all_timeframes:
                    if tf == min_days:
                        break
                    prev_timeframe = tf
                days_ago = (prev_timeframe + min_days) / 2
        else:
            days_ago = found_timeframes[0]
        
        # Convert to date
        estimated_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        return estimated_date

    def update_csv_with_estimated_dates(self, csv_path, estimated_date):
        """Update existing CSV with estimated dates"""
        try:
            # Read existing CSV
            rows = []
            with open(csv_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            
            # Update date column (skip header)
            for i in range(1, len(rows)):
                if len(rows[i]) > 0:
                    rows[i][0] = estimated_date
            
            # Write back
            with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
                
            print(f"Updated CSV with estimated date: {estimated_date}")
            
        except Exception as e:
            print(f"Error updating CSV with dates: {e}")

    def save_interpolated_results(self, items):
        """Save interpolated results to CSV"""
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
        """Initialize Chrome WebDriver with all necessary options"""
        chrome_options = Options()
        
        # Auto-enable headless in containers / non-GUI envs
        auto_headless = (
            headless or
            os.environ.get('HEADLESS', '').lower() == 'true' or
            not os.environ.get('DISPLAY')
        )
        if auto_headless:
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--window-size=1280,1024')
        
        # Recommended stability flags
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
        
        # Randomize User-Agent to reduce blocks/headless detection
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        import random
        selected_ua = random.choice(user_agents)
        chrome_options.add_argument(f'--user-agent={selected_ua}')
        print(f"Using User-Agent: {selected_ua}")
        
        try:
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
        except Exception:
            pass
        
        chrome_options.add_argument('--lang=en-US')
        # Start minimized/off-screen to avoid popping up while not being headless
        chrome_options.add_argument('--start-minimized')
        chrome_options.add_argument('--window-position=-4000,-4000')
        chrome_options.add_argument('--window-size=1,1')

        # Attempt to auto-detect Chrome binary if Selenium can't find it
        chrome_binary = find_chrome_binary()
        if chrome_binary:
            chrome_options.binary_location = chrome_binary
        else:
            print("[Warn] Chrome binary not found automatically. If Chrome is installed in a non-standard path, set CHROME_BIN env var to chrome.exe path.")

        # Use Selenium Manager (auto-resolves correct ChromeDriver for installed Chrome)
        print("[Info] Starting Chrome via Selenium Manager (no local chromedriver)")
        chrome_options.page_load_strategy = 'none' if self.mode == 'ultra_fast' else 'eager'
        
        # Log ChromeDriver output for debugging
        try:
            service = Service(log_output='chromedriver.log')
        except Exception:
            service = Service()
        
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Execute stealth script to hide automation indicators
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
        self.driver.execute_script(stealth_script)
        
        # If ultra fast mode, block heavy resources via CDP to speed up rendering
        if self.mode == 'ultra_fast':
            try:
                self.driver.execute_cdp_cmd('Network.enable', {})
                self.driver.execute_cdp_cmd('Network.setBlockedURLs', {
                    'urls': [
                        '*.png','*.jpg','*.jpeg','*.gif','*.webp','*.svg',
                        '*.mp4','*.webm','*.m4v','*.mov','*.avi','*.mkv',
                        '*.woff','*.woff2','*.ttf','*.otf'
                    ]
                })
            except Exception:
                pass
        
        try:
            # Allow slower loads in container cold starts
            self.driver.set_page_load_timeout(max(self.delay, 30))
        except Exception:
            pass

        # Ensure the window is minimized right after launch
        try:
            self.driver.minimize_window()
            # Move far off-screen and shrink to 1x1 (Windows convention)
            try:
                self.driver.set_window_position(-32000, -32000)
                self.driver.set_window_size(1, 1)
            except Exception:
                pass
        except Exception:
            pass

        # Create folder for data logging
        if not os.path.exists('raw'):
            os.mkdir('raw')
        if not os.path.exists('processed'):
            os.mkdir('processed')

    def load_facebook_url(self):
        print(f"Loading Facebook URL: {self.url}")
        
        # Re-apply off-screen/minimized before navigation to avoid any flash
        try:
            self.driver.minimize_window()
            self.driver.set_window_position(-32000, -32000)
            self.driver.set_window_size(1, 1)
        except Exception:
            pass

        # Try multiple strategies to bypass login redirect
        success = False
        strategies = [
            self.url,  # Original URL
            self.url.replace('facebook.com', 'm.facebook.com'),  # Mobile version
            f"https://www.facebook.com/marketplace/search/?query={quote(self.item)}&exact=false",  # Direct search
        ]
        
        for i, url_to_try in enumerate(strategies):
            print(f"Strategy {i+1}: Trying {url_to_try}")
            try:
                # Add random delay to appear more human
                time.sleep(random.uniform(2, 5))
                
                self.driver.get(url_to_try)
                
                # Wait and check if we got redirected to login
                time.sleep(3)
                current_url = self.driver.current_url
                page_source = self.driver.page_source.lower()
                
                if 'login' not in current_url.lower() and 'login' not in page_source[:1000]:
                    print(f"✓ Successfully loaded without login redirect")
                    success = True
                    break
                else:
                    print(f"✗ Redirected to login page")
                    
            except Exception as e:
                print(f"Strategy {i+1} failed: {e}")
                continue
        
        if not success:
            print("⚠️  All strategies failed - proceeding anyway to attempt data extraction")

        try:
            wait = WebDriverWait(self.driver, max(self.delay, 20))

            # Attempt to dismiss any cookie/marketing popups early
            self.dismiss_popups()

            # Wait for Facebook Marketplace listings to load
            try:
                wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='marketplace-item']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/marketplace/item/']")),
                        EC.presence_of_element_located((By.TAG_NAME, 'main')),
                    )
                )
            except Exception:
                pass

            # Scroll to trigger lazy loading
            try:
                for frac in (0.3, 0.6, 1.0):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * arguments[0]);", frac)
                    time.sleep(1.5)  # Longer wait for Facebook's heavy JS
            except Exception:
                pass

            # Extra wait for marketplace listings
            try:
                wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='marketplace-item']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/marketplace/item/']"))
                    )
                )
            except Exception:
                pass

            # Save page source for debugging/extraction
            dest_path = os.path.join('raw', f"{self.curdatetime}_FacebookSource.html")
            with open(dest_path, 'w+', encoding='utf-8') as f:
                f.write(self.driver.page_source)
                
        except TimeoutException:
            print('Time out to load', self.url)

        # Save screenshot (safe) unless ultra fast mode is enabled
        if self.mode != 'ultra_fast':
            try:
                screenshot_path = os.path.join('raw', f"{self.curdatetime}_FacebookSearch.png")
                self.driver.get_screenshot_as_file(screenshot_path)
                print('Saved:', screenshot_path)
            except Exception as e:
                print('[Warn] Failed to capture screenshot:', e)

    def _safe_click(self, element):
        try:
            self.driver.execute_script("arguments[0].click();", element)
        except Exception:
            try:
                element.click()
            except Exception:
                pass

    def dismiss_popups(self):
        # Try a series of common selectors/texts for Facebook popups
        wait_short = WebDriverWait(self.driver, 3)
        candidates = [
            # Facebook login/signup prompts
            (By.XPATH, "//div[@role='button'][contains(.,'Not Now') or contains(.,'Skip')]"),
            (By.XPATH, "//button[contains(.,'Not Now') or contains(.,'Skip') or contains(.,'Close')]"),
            # Cookie banners
            (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'accept')]"),
            (By.XPATH, "//button[contains(.,'Allow all') or contains(.,'Allow All')]"),
            # Dialog close buttons
            (By.XPATH, "//div[@role='dialog']//div[@role='button'][contains(@aria-label,'Close') or contains(.,'×')]")
        ]

        for by, sel in candidates:
            try:
                el = wait_short.until(EC.presence_of_element_located((by, sel)))
                if el:
                    self._safe_click(el)
                    time.sleep(1)
            except Exception:
                continue

        # As a last resort, press ESC to close potential modals
        try:
            from selenium.webdriver.common.keys import Keys
            self.driver.switch_to.active_element.send_keys(Keys.ESCAPE)
        except Exception:
            pass

    def extract_marketplace_items(self):
        # Prefer the DOM rendered by Selenium
        html = self.driver.page_source
        soup = bs(html, 'lxml')

        dates = []
        titles = []
        prices = []

        # Facebook Marketplace uses complex nested structures - look for marketplace item links
        try:
            # Find all links that go to marketplace items
            marketplace_links = soup.find_all('a', href=re.compile(r'/marketplace/item/\d+'))
            seen_hrefs = set()
            
            print(f"Found {len(marketplace_links)} marketplace item links")
            
            # Debug: Also check for any marketplace-related elements
            all_marketplace_elements = soup.find_all(attrs={'data-testid': re.compile(r'marketplace')})
            print(f"Found {len(all_marketplace_elements)} elements with marketplace data-testid")
            
            # Debug: Check page content
            page_text = soup.get_text()[:500]  # First 500 chars
            print(f"Page content preview: {page_text}")
            
            if len(marketplace_links) == 0:
                print("No marketplace links found. Checking for alternative selectors...")
                # Try alternative selectors
                alt_links = soup.find_all('a', href=re.compile(r'/marketplace/'))
                print(f"Found {len(alt_links)} general marketplace links")
                
                # Check if we're being redirected or blocked
                if 'login' in page_text.lower() or 'sign up' in page_text.lower():
                    print("WARNING: Page appears to require login")
                if 'blocked' in page_text.lower() or 'unavailable' in page_text.lower():
                    print("WARNING: Page may be blocked or unavailable")
            
            for link in marketplace_links:
                try:
                    href = link.get('href', '')
                    if href in seen_hrefs:
                        continue
                    seen_hrefs.add(href)
                    
                    # Navigate up to find the card container that holds all item info
                    card_container = link
                    for _ in range(8):  # Go up several levels to find the full card
                        parent = card_container.find_parent()
                        if not parent:
                            break
                        card_container = parent
                        # Look for a container that likely holds the full item card
                        if len(parent.find_all('span')) > 5:  # Cards typically have many spans
                            break
                    
                    # Extract title from the link's aria-label or nested spans
                    title = ''
                    if link.get('aria-label'):
                        title = link.get('aria-label')
                    else:
                        # Look for spans with item titles (usually longer text)
                        spans = card_container.find_all('span')
                        for span in spans:
                            text = span.get_text(strip=True)
                            # Skip if it's just a price or very short
                            if text and len(text) > 10 and not re.match(r'^[\$\d,\s]+$', text):
                                title = text
                                break
                    
                    # Extract price - look for currency patterns in the card
                    price = ''
                    card_text = card_container.get_text()
                    # Look for various currency formats
                    price_patterns = [
                        r'SGD\s?[\d,]+',  # SGD format
                        r'\$[\d,]+',      # $ format
                        r'S\$\s?[\d,]+'   # S$ format
                    ]
                    
                    for pattern in price_patterns:
                        price_match = re.search(pattern, card_text)
                        if price_match:
                            price = price_match.group(0)
                            break
                    
                    # Extract location/date info - Facebook often shows location
                    date = ''
                    location = ''
                    
                    # Look for relative time patterns
                    time_patterns = [
                        r'\d+\s+(?:minute|hour|day|week|month)s?\s+ago',
                        r'yesterday|today'
                    ]
                    
                    for pattern in time_patterns:
                        date_match = re.search(pattern, card_text, re.IGNORECASE)
                        if date_match:
                            date = date_match.group(0)
                            break
                    
                    # Clean up title - remove extra whitespace and newlines
                    if title:
                        title = re.sub(r'\s+', ' ', title).strip()
                        # Remove price from title if it got included
                        for pattern in price_patterns:
                            title = re.sub(pattern, '', title).strip()
                    
                    # Only add if we have meaningful data
                    if title and len(title) > 3:
                        titles.append(title)
                        prices.append(price)
                        dates.append(self.return_date(date))
                        
                        print(f"Extracted: {title[:50]}... | {price} | {date}")
                        
                except Exception as e:
                    print(f"Error extracting item: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error finding marketplace items: {e}")

        print(f'Final counts - dates: {len(dates)}, titles: {len(titles)}, prices: {len(prices)}')

        # Write to csv
        csv_path = os.path.join('processed', f"{self.curdatetime}_Facebook_Search_{self.item.replace(' ', '')}.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(('Date', 'Item', 'Price'))
            for i in range(len(titles)):
                date_val = dates[i] if i < len(dates) else ''
                price_val = prices[i] if i < len(prices) else ''
                writer.writerow((date_val.strip(), titles[i].strip(), price_val.strip()))
                
        print('Saved:', csv_path)
        return {
            'csv_path': csv_path,
            'count': len(titles)
        }

    def return_date(self, d: str) -> str:
        # Returns posting date (YYYY-mm-dd) or original string if unknown
        try:
            s = (d or '').strip()
            if not s:
                return s
            low = s.lower()
            now = datetime.now()
            
            # Absolute ISO-like date in page
            m_abs = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", s)
            if m_abs:
                y, mo, da = map(int, m_abs.groups())
                return datetime(y, mo, da).strftime('%Y-%m-%d')

            if 'minute' in low:
                minute = int(re.sub(r"[^0-9]", "", low) or '0')
                return (now - timedelta(minutes=minute)).strftime('%Y-%m-%d')
            if 'hour' in low:
                hour = int(re.sub(r"[^0-9]", "", low) or '0')
                return (now - timedelta(hours=hour)).strftime('%Y-%m-%d')
            if 'yesterday' in low:
                return (now - timedelta(days=1)).strftime('%Y-%m-%d')
            if 'today' in low:
                return now.strftime('%Y-%m-%d')
            if 'week' in low:
                wk = int(re.sub(r"[^0-9]", "", low) or '1')
                return (now - timedelta(days=7 * wk)).strftime('%Y-%m-%d')
            if 'month' in low:
                mo = int(re.sub(r"[^0-9]", "", low) or '1')
                return (now - timedelta(days=30 * mo)).strftime('%Y-%m-%d')
            if 'year' in low:
                yr = int(re.sub(r"[^0-9]", "", low) or '1')
                return (now - timedelta(days=365 * yr)).strftime('%Y-%m-%d')
            if 'day' in low:
                day = int(re.sub(r"[^0-9]", "", low) or '0')
                return (now - timedelta(days=day)).strftime('%Y-%m-%d')
            return s
        except Exception:
            return d

    def quit(self):
        try:
            self.driver.close()
        except Exception:
            pass

    def run_and_save(self):
        """Convenience method for web layer: loads URL, extracts items, returns paths and counts."""
        return self.scrape_with_date_estimation()


if __name__ == '__main__':
    # Test with air conditioner search using daysSinceListed
    scraper = FacebookMarketplaceScraper(
        item='air conditioner',
        min_price='200',
        condition='new',
        days_since_listed=30,  # Look for items listed in last 30 days
        mode='fast'  # Fast mode for testing (3 timeframes)
    )
    result = scraper.scrape_with_date_estimation()
    scraper.quit()
    print(f"Scraped {result['count']} items, saved to {result['csv_path']}")
