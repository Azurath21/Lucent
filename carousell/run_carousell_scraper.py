import os
import re
import csv
from datetime import datetime, timedelta
import time
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


class CarousellScraper(object):
    def __init__(self, item='baby chair', condition='brand new', location='Woodlands',
                 distance='5', min_price='0', sort='recent',
                 chromedriver_path='chromedriver.exe', headless=False, delay=20, fast=False):
        self.curdatetime = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.item = item
        self.condition = condition
        self.location = location
        self.distance = distance
        self.min_price = min_price
        self.base_url = 'https://www.carousell.sg'
        self.delay = delay
        self.fast = fast

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
        self.url = (
            f"{self.base_url}/search/{encoded_item}?addRecent=true&canChangeKeyword=true&includeSuggestions=true"
            f"&layered_condition={layered_condition}&price_start={min_price}"
            f"&sort_by={sort_by}&t-search_query_source=direct_search"
        )
        print(self.url)

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
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
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
        
        chrome_options.page_load_strategy = 'none' if self.fast else 'eager'
        try:
            service = Service(log_output='chromedriver.log')
        except Exception:
            service = Service()
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        if self.fast:
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
            self.driver.set_page_load_timeout(max(self.delay, 30))
        except Exception:
            pass

        try:
            self.driver.minimize_window()
            try:
                self.driver.set_window_position(-32000, -32000)
                self.driver.set_window_size(1, 1)
            except Exception:
                pass
        except Exception:
            pass

        if not os.path.exists('raw'):
            os.mkdir('raw')
        if not os.path.exists('processed'):
            os.mkdir('processed')

    def load_carousell_url(self):
        try:
            self.driver.minimize_window()
            self.driver.set_window_position(-32000, -32000)
            self.driver.set_window_size(1, 1)
        except Exception:
            pass

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

            self.dismiss_popups()

            try:
                wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/p/']")),
                        EC.presence_of_element_located((By.TAG_NAME, 'main')),
                    )
                )
            except Exception:
                pass

            try:
                for frac in (0.3, 0.6, 1.0):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight * arguments[0]);", frac)
                    time.sleep(0.8)
            except Exception:
                pass

            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/p/']")))
            except Exception:
                pass

            dest_path = os.path.join('raw', f"{self.curdatetime}_CarousellSource.html")
            with open(dest_path, 'w+', encoding='utf-8') as f:
                f.write(self.driver.page_source)
        except TimeoutException:
            print('Time out to load', self.url)

        if not self.fast:
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
        wait_short = WebDriverWait(self.driver, 2)
        candidates = [
            (By.ID, 'onetrust-accept-btn-handler'),
            (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'accept')]"),
            (By.XPATH, "//button[contains(.,'Allow all') or contains(.,'Allow All')]"),
            (By.XPATH, "//button[contains(.,'Got it') or contains(.,'OK')]"),
            (By.XPATH, "//div[@role='dialog']//button[contains(@aria-label,'Close') or contains(.,'Close') or contains(.,'×') or contains(.,'✕')]")
        ]

        for by, sel in candidates:
            try:
                el = wait_short.until(EC.presence_of_element_located((by, sel)))
                if el:
                    self._safe_click(el)
            except Exception:
                continue

        try:
            from selenium.webdriver.common.keys import Keys
            self.driver.switch_to.active_element.send_keys(Keys.ESCAPE)
        except Exception:
            pass

    def extract_item_title(self):
        html = self.driver.page_source
        soup = bs(html, 'lxml')

        dates = []
        titles = []
        prices = []
        

        try:
            items = soup.find('main').find_all('div')[0].find_all('div')[0].children
        except Exception:
            items = []

        for item in items:
            try:
                base_items = item.find_all('a')
                if len(base_items) > 1:
                    base_items02 = base_items[1]
                    item_link = self.shorten_url(self.base_url + base_items02.get('href', ''))
                    ps = base_items02.find_all('p')
                    title = ps[0].text if len(ps) > 0 else ''
                    price = ps[1].text if len(ps) > 1 else ''

                    date = ''
                    try:
                        date = self.find_relative_date_near(item)
                    except Exception:
                        date = ''
                    if not date:
                        try:
                            date = self.extract_item_date(item_link)
                        except Exception:
                            date = ''
                    date = self.return_date(date)

                    if title:
                        dates.append(date)
                        titles.append(title)
                        prices.append(price)
            except Exception:
                continue

        if len(titles) == 0:
            try:
                anchors = soup.select("a[href^='/p/']")
                seen = set()
                for a in anchors:
                    href = a.get('href', '')
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    text = a.get('aria-label') or a.get_text(" ", strip=True)
                    if not text:
                        continue
                    link = href if href.startswith('http') else (self.base_url + href)
                    date_text = ''
                    try:
                        date_text = self.find_relative_date_near(a)
                    except Exception:
                        date_text = ''
                    if not date_text:
                        try:
                            date_text = self.extract_item_date(link)
                        except Exception:
                            date_text = ''
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
                    prices.append(price_text)
                    dates.append(self.return_date(date_text))

                    if len(titles) >= 100:
                        break
            except Exception:
                pass

        safe_item = re.sub(r'[^A-Za-z0-9]+', '', self.item)
        dest_path = os.path.join('processed', f"{self.curdatetime}_Carousell_Search_{safe_item}.csv")
        with open(dest_path, 'w+', encoding='utf-8', newline='') as csvFile:
            writer = csv.writer(csvFile)
            writer.writerow(('Date', 'Item', 'Price'))
            for i in range(len(dates)):
                writer.writerow((
                    dates[i].strip(), titles[i].strip(), prices[i].strip()
                ))
        print('Saved:', dest_path)
        return {
            'csv_path': dest_path,
            'count': len(titles)
        }

    def return_date(self, d: str) -> str:
        try:
            s = (d or '').strip()
            if not s:
                return s
            low = s.lower()
            now = datetime.now()
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

    def find_relative_date_near(self, node) -> str:
        try:
            if not node:
                return ''
            patt = re.compile(r"\b(\d+\s+(?:minute|hour|day|week|month|year)s?\s+ago|yesterday|today)\b", re.IGNORECASE)

            txt = node.get_text(" ", strip=True)
            m = patt.search(txt)
            if m:
                return m.group(1)

            for p in node.find_all('p'):
                t = p.get_text(" ", strip=True)
                m = patt.search(t)
                if m:
                    return m.group(1)

            parent = node
            for _ in range(3):
                parent = parent.find_parent()
                if not parent:
                    break
                t = parent.get_text(" ", strip=True)
                m = patt.search(t)
                if m:
                    return m.group(1)
                for p in parent.find_all('p'):
                    tt = p.get_text(" ", strip=True)
                    m2 = patt.search(tt)
                    if m2:
                        return m2.group(1)
        except Exception:
            return ''
        return ''

    def extract_item_date(self, item_url: str) -> str:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        try:
            html = ''
            for i in range(2):
                try:
                    r = requests.get(item_url, headers=headers, timeout=6)
                    if r.ok:
                        html = r.text
                        break
                except requests.RequestException:
                    time.sleep(0.5)
                    continue
            if not html:
                return ''
            soup = bs(html, 'lxml')
            full_text = soup.get_text(" ", strip=True)
            m = re.search(r"Listed\s+(?:on\s+)?(.*?)(?:\s+by\b|$)", full_text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
            time_el = soup.find('time')
            if time_el:
                if time_el.get('datetime'):
                    return time_el.get('datetime').strip()
                if time_el.text:
                    return time_el.text.strip()
            meta = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('meta', attrs={'itemprop': 'datePublished'})
            if meta and meta.get('content'):
                return meta.get('content').strip()
        except Exception:
            return ''
        return ''

    

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
        self.load_carousell_url()
        result = self.extract_item_title()
        result['screenshot_path'] = '' if self.fast else os.path.join('raw', f"{self.curdatetime}_CarousellSearch.png")
        return result


if __name__ == '__main__':
    scraper = CarousellScraper()
    scraper.load_carousell_url()
    scraper.extract_item_title()
    scraper.quit()
