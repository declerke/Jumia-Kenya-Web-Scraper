import requests
import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Dict

def scrape_jumia_category(url: str, category_name: str) -> pd.DataFrame:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        product_cards = soup.select('article.prd')
        print(f"✓ Found {len(product_cards)} {category_name} on the page")
        products = [
            extract_product_info(card) 
            for card in product_cards
        ]
        df = pd.DataFrame(products)
        filename = f"jumia_{category_name.lower().replace(' ', '_')}.csv"
        df.to_csv(filename, index=False, encoding='utf-8')
        print(f"✓ Data saved to {filename}")
        return df
    except requests.RequestException as e:
        print(f"✗ Error fetching data: {e}")
        return pd.DataFrame()

def extract_product_info(card) -> Dict[str, str]:
    name_elem = card.select_one('h3.name')
    price_elem = card.select_one('div.prc')
    old_price_elem = card.select_one('div.old')
    discount_elem = card.select_one('div.bdg._dsct')
    link_elem = card.select_one('a.core')
    return {
        'Product Name': name_elem.text.strip() if name_elem else 'N/A',
        'Current Price': price_elem.text.strip() if price_elem else 'N/A',
        'Old Price': old_price_elem.text.strip() if old_price_elem else 'N/A',
        'Discount': discount_elem.text.strip() if discount_elem else 'N/A',
        'Product URL': f"https://www.jumia.co.ke{link_elem['href']}" if link_elem else 'N/A'
    }

smartphones_df = scrape_jumia_category(
    url="https://www.jumia.co.ke/smartphones/",
    category_name="Smartphones"
)
print("\n📱 Smartphone Sample Data:")
smartphones_df.head(10)

computing_df = scrape_jumia_category(
    url="https://www.jumia.co.ke/computing/",
    category_name="Computing Devices"
)
print("\n💻 Computing Devices Sample Data:")
computing_df.head(10)

print("\n📊 Scraping Summary:")
print(f"Total Smartphones: {len(smartphones_df)}")
print(f"Total Computing Devices: {len(computing_df)}")
print(f"\nTotal Products Scraped: {len(smartphones_df) + len(computing_df)}")
