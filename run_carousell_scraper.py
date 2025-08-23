import os
import re
import csv
from datetime import datetime, timedelta
import time
from urllib.request import urlopen, Request
from urllib.parse import quote
from typing import Optional

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


class CarousellScraper(object):
    def __init__(self, item='baby chair', condition='brand new', location='Woodlands',
                 distance='5', min_price='0', max_price='150', sort='recent',
                 chromedriver_path='chromedriver.exe', headless=False, delay=20):
        # For data logging
        self.curdatetime = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.item = item
        self.condition = condition
        self.location = location
        self.distance = distance
        self.min_price = min_price
        self.max_price = max_price
        # New domain and URL shape
        self.base_url = 'https://www.carousell.sg'
        self.delay = delay

        # Map human-friendly condition/sort to new layered_condition/sort_by values
        def map_condition(val):
            mapping = {
                'brand new': 3,
                'like new': 4,
                'lightly used': 7,
                'well used': 5,
                'heavily used': 6,
                'new': 3,
                'used': 7,
            }
            try:
                # numeric string or int is passed through
                return int(val)
            except Exception:
                return mapping.get(str(val).strip().lower(), 3)

        def map_sort(val):
            mapping = {
                'best': 1,
                'best_match': 1,
                'recent': 3,
                'date_desc': 3,
                'price_desc': 5,
                'high_to_low': 5,
                'price_asc': 4,
                'low_to_high': 4,
                'nearby': 6,
            }
            try:
                return int(val)
            except Exception:
                return mapping.get(str(val).strip().lower(), 3)

        layered_condition = map_condition(condition)
        sort_by = map_sort(sort)

        encoded_item = quote(item)
        # New URL: drop location; include new flags and params
        self.url = (
            f"{self.base_url}/search/{encoded_item}?addRecent=true&canChangeKeyword=true&includeSuggestions=true"
            f"&layered_condition={layered_condition}&price_end={max_price}&price_start={min_price}"
            f"&sort_by={sort_by}&t-search_query_source=direct_search"
        )
        print(self.url)

        # Selenium 4-compatible driver initialization
        chrome_options = Options()
        # Auto-enable headless in containers / non-GUI envs
        auto_headless = (
            headless or
            os.environ.get('HEADLESS', '').lower() == 'true' or
            not os.environ.get('DISPLAY') or
            os.environ.get('RENDER') is not None
        )
        if auto_headless:
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--window-size=1280,1024')
        # Recommended stability flags
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--remote-debugging-port=9222')
        chrome_options.add_argument('--disable-gpu')  # also disable when non-headless to avoid context errors
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
        # Realistic User-Agent to reduce blocks/headless detection
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
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
        # We intentionally do NOT fall back to the bundled chromedriver.exe to avoid version mismatches.
        print("[Info] Starting Chrome via Selenium Manager (no local chromedriver)")
        chrome_options.page_load_strategy = 'eager'
        # Log ChromeDriver output for debugging
        try:
            service = Service(log_output='chromedriver.log')
        except Exception:
            service = Service()
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
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

    def load_carousell_url(self):
        # Re-apply off-screen/minimized before navigation to avoid any flash
        try:
            self.driver.minimize_window()
            self.driver.set_window_position(-32000, -32000)
            self.driver.set_window_size(1, 1)
        except Exception:
            pass

        # Navigate with a retry if renderer/page load times out
        try:
            self.driver.get(self.url)
        except Exception:
            try:
                time.sleep(2)
                self.driver.get(self.url)
            except Exception:
                pass

        try:
            wait = WebDriverWait(self.driver, max(self.delay, 20))

            # Attempt to dismiss any cookie/marketing popups early
            self.dismiss_popups()

            # Wait for results: either listing anchors or main present
            try:
                wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/p/']")),
                        EC.presence_of_element_located((By.TAG_NAME, 'main')),
                    )
                )
            except Exception:
                pass

            # Scroll to trigger lazy loading
            try:
                for frac in (0.3, 0.6, 1.0):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * arguments[0]);", frac)
                    time.sleep(0.8)
            except Exception:
                pass

            # Extra wait for listing anchors
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/p/']")))
            except Exception:
                pass

            # Save page source for debugging/extraction
            dest_path = os.path.join('raw', f"{self.curdatetime}_CarousellSource.html")
            with open(dest_path, 'w+', encoding='utf-8') as f:
                f.write(self.driver.page_source)
        except TimeoutException:
            print('Time out to load', self.url)

        # Save screenshot (safe)
        try:
            screenshot_path = os.path.join('raw', f"{self.curdatetime}_CarousellSearch.png")
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
        # Try a series of common selectors/texts for cookie banners and modals
        wait_short = WebDriverWait(self.driver, 2)
        candidates = [
            # OneTrust common id
            (By.ID, 'onetrust-accept-btn-handler'),
            # Generic cookie accept buttons
            (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'accept')]"),
            (By.XPATH, "//button[contains(.,'Allow all') or contains(.,'Allow All')]"),
            (By.XPATH, "//button[contains(.,'Got it') or contains(.,'OK')]"),
            # Dialog close buttons
            (By.XPATH, "//div[@role='dialog']//button[contains(@aria-label,'Close') or contains(.,'Close') or contains(.,'×') or contains(.,'✕')]")
        ]

        for by, sel in candidates:
            try:
                el = wait_short.until(EC.presence_of_element_located((by, sel)))
                if el:
                    self._safe_click(el)
            except Exception:
                continue

        # As a last resort, press ESC to close potential modals
        try:
            from selenium.webdriver.common.keys import Keys
            self.driver.switch_to.active_element.send_keys(Keys.ESCAPE)
        except Exception:
            pass

    def extract_item_title(self):
        # Prefer the DOM rendered by Selenium, avoids blocking by anti-bot/CDN
        html = self.driver.page_source
        soup = bs(html, 'lxml')

        sellers = []
        seller_links = []
        dates = []
        titles = []
        item_links = []
        prices = []
        seller_ratings = []

        # Try original structure first but guard against None
        try:
            items = soup.find('main').find_all('div')[0].find_all('div')[0].children
        except Exception:
            items = []

        for item in items:
            try:
                base_items = item.find_all('a')
                if len(base_items) > 1:
                    # seller, seller's page, date time
                    base_items01 = base_items[0]
                    seller = base_items01.find_all('p')[0].text if base_items01.find_all('p') else ''
                    seller_link = self.shorten_url(self.base_url + base_items01.get('href', ''))
                    date = base_items01.find_all('p')[-1].text if base_items01.find_all('p') else ''
                    date = self.return_date(date)

                    base_items02 = base_items[1]
                    item_link = self.shorten_url(self.base_url + base_items02.get('href', ''))
                    ps = base_items02.find_all('p')
                    title = ps[0].text if len(ps) > 0 else ''
                    price = ps[1].text if len(ps) > 1 else ''

                    seller_rating = self.extract_item_seller_ratings(seller_link) if seller_link else ''

                    if title and re.search(r'(?i)(baby.*chair)', title) is not None:
                        sellers.append(seller)
                        seller_links.append(seller_link)
                        dates.append(date)
                        item_links.append(item_link)
                        titles.append(title)
                        prices.append(price)
                        seller_ratings.append(seller_rating)
            except Exception:
                continue

        # Fallback: if nothing captured, try generic anchors and heuristics (new site)
        if len(titles) == 0:
            try:
                anchors = soup.select("a[href^='/p/']")
                seen = set()
                for a in anchors:
                    href = a.get('href', '')
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    # Title from aria-label or text
                    text = a.get('aria-label') or a.get_text(" ", strip=True)
                    if not text:
                        continue
                    # Resolve absolute link
                    link = href if href.startswith('http') else (self.base_url + href)
                    # Price: look up to 2 levels of parents for S$ pattern
                    price_text = ''
                    try:
                        node = a
                        for _ in range(2):
                            node = node.find_parent()
                            if not node:
                                break
                            m = re.search(r"S\$\s?\d[\d,\.]*", node.get_text(" ", strip=True))
                            if m:
                                price_text = m.group(0)
                                break
                    except Exception:
                        pass

                    titles.append(text)
                    item_links.append(link)
                    prices.append(price_text)
                    sellers.append('')
                    seller_links.append('')
                    seller_ratings.append('')
                    dates.append('')

                    if len(titles) >= 100:
                        break
            except Exception:
                pass

        print(
            'sellers:', len(sellers),
            ', seller_links:', len(seller_links),
            ', dates:', len(dates),
            ', titles:', len(titles),
            ', title links:', len(item_links),
            ', prices:', len(prices),
            ', seller_ratings:', len(seller_ratings)
        )

        # Write to csv
        dest_path = os.path.join('processed', f"{self.curdatetime}_Carousell_Search_{self.item}.csv").replace(' ', '')
        with open(dest_path, 'w+', encoding='utf-8', newline='') as csvFile:
            writer = csv.writer(csvFile)
            writer.writerow(('Date', 'Item', 'Item_Link', 'Price', 'Seller', 'Seller_Link', 'Seller_Ratings'))
            for i in range(len(dates)):
                writer.writerow((
                    dates[i].strip(), titles[i].strip(), item_links[i].strip(), prices[i].strip(),
                    sellers[i].strip(), seller_links[i].strip(), seller_ratings[i].strip()
                ))
        print('Saved:', dest_path)
        return {
            'csv_path': dest_path,
            'count': len(titles)
        }

    def return_date(self, d: str) -> str:
        # Returns posting date (YYYY-mm-dd) or original string if unknown
        try:
            if 'hour' in d:
                hour = int(re.sub(r"[^0-9]", "", d))
                t = datetime.now() - timedelta(hours=hour)
                return t.strftime('%Y-%m-%d')
            elif 'day' in d:
                day = int(re.sub(r"[^^0-9]", "", d))
                t = datetime.now() - timedelta(days=day)
                return t.strftime('%Y-%m-%d')
            elif 'minute' in d:
                minute = int(re.sub(r"[^^0-9]", "", d))
                t = datetime.now() - timedelta(minutes=minute)
                return t.strftime('%Y-%m-%d')
            else:
                return d
        except Exception:
            return d

    def extract_item_seller_ratings(self, seller_url: str) -> str:
        headers = {'User-Agent': 'Chrome/24.0.1312.27'}
        request = Request(seller_url, headers=headers)
        html = urlopen(request).read()
        soup = bs(html, 'lxml')

        NA_RATINGS = 'No ratings yet'
        contents = soup.find_all('p')
        seller_rating = ''
        for cont in contents:
            text = cont.text.strip()
            if NA_RATINGS in text:
                seller_rating = text
                break
            if re.match(r'^\d+\.\d+$', text):
                seller_rating = text
        return seller_rating

    def shorten_url(self, url: str) -> str:
        pos = url.find('?')
        if pos != -1:
            return url[:pos]
        return url

    def quit(self):
        try:
            self.driver.close()
        except Exception:
            pass

    def run_and_save(self):
        """Convenience method for web layer: loads URL, extracts items, returns paths and counts."""
        self.load_carousell_url()
        result = self.extract_item_title()
        # Find latest screenshot saved in raw for this run timestamp
        screenshot_path = os.path.join('raw', f"{self.curdatetime}_CarousellSearch.png")
        result['screenshot_path'] = screenshot_path
        return result


if __name__ == '__main__':
    # Create instance and run
    scraper = CarousellScraper()
    scraper.load_carousell_url()
    scraper.extract_item_title()
    scraper.quit()
