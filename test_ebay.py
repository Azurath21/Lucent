import requests
from bs4 import BeautifulSoup
import json

def test_ebay_scrape():
    # Test URL for airpods 4, used condition, min price 100, Singapore
    url = "https://www.ebay.com.sg/sch/i.html?_nkw=airpods+4&_sacat=0&_udlo=100&LH_PrefLoc=1&rt=nc&LH_ItemCondition=3"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        print(f"Testing URL: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find items
            items = soup.find_all('div', {'class': 's-item'})
            print(f"Found {len(items)} items")
            
            listings = []
            for i, item in enumerate(items[:5]):  # Test first 5 items
                try:
                    title_elem = item.find('h3', class_='s-item__title')
                    price_elem = item.find('span', class_='s-item__price')
                    
                    if title_elem and price_elem:
                        title = title_elem.get_text(strip=True)
                        price = price_elem.get_text(strip=True)
                        
                        if "Shop on eBay" not in title and title:
                            listings.append({
                                'title': title,
                                'price': price
                            })
                            print(f"Item {i+1}: {title} - {price}")
                            
                except Exception as e:
                    print(f"Error parsing item {i}: {e}")
            
            print(f"\nSuccessfully parsed {len(listings)} valid listings")
            return {"ok": True, "count": len(listings), "listings": listings}
            
        else:
            print(f"HTTP Error: {response.status_code}")
            return {"ok": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        print(f"Error: {e}")
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    result = test_ebay_scrape()
    print(f"\nFinal result: {json.dumps(result, indent=2)}")
