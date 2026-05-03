import requests
from bs4 import BeautifulSoup
import json
import csv
from datetime import datetime
import time
import re
import random
import os


def scrape_chakra_category(base_url, category_name):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    page = 1
    category_products = []
    seen_ids = set()
    retry_delays = [5, 15, 30]

    print(f"\n--- {category_name.upper()} Taraması Başlıyor ---")

    while True:
        url = f"{base_url}?page={page}"
        print(f"İstek atılıyor: {url}")

        request_success = False

        for attempt, delay in enumerate(retry_delays):
            try:
                response = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
                response.raise_for_status()
                request_success = True
                break
            except requests.exceptions.RequestException as e:
                print(f"Hata ({e}). {delay} saniye bekleniyor... (Deneme {attempt + 1}/3)")
                time.sleep(delay)

        if not request_success:
            print(f"Uyarı: {url} sayfasına 3 denemede de ulaşılamadı. Sayfa atlanıyor.")
            page += 1
            continue

        if response.history:
            print(f"Yönlendirme tespit edildi. {category_name} kategorisi bitti.")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        ld_json_script = soup.find('script', type='application/ld+json')

        if not ld_json_script:
            print("JSON verisi bulunamadı, sayfa yapısı farklı veya sayfalama sonu. Döngü kırılıyor.")
            break

        try:
            data = json.loads(ld_json_script.string)
        except json.JSONDecodeError:
            print("JSON ayrıştırma hatası, döngü kırılıyor.")
            break

        items = data.get('itemListElement', [])
        if not items:
            print("Sayfada ürün bulunamadı, döngü kırılıyor.")
            break

        new_items_found = False

        for item in items:
            product_url = item.get('url', '')
            name = item.get('name', 'İsimsiz Ürün')

            offers = item.get('offers')
            if isinstance(offers, list) and len(offers) > 0:
                price_val = offers[0].get('price')
            elif isinstance(offers, dict):
                price_val = offers.get('price')
            else:
                price_val = None

            if price_val is None or str(price_val).strip() == "":
                price = '0'
            else:
                price = str(price_val).strip()

            match = re.search(r'-(\d+)/?$', product_url)
            product_id = match.group(1) if match else product_url

            if price == '0' or price == 'None':
                wrapper = soup.find(attrs={'data-sku': product_id})

                if not wrapper:
                    product_link = soup.find('a', href=re.compile(f"{product_id}"))
                    if product_link:
                        wrapper = product_link.find_parent('div', class_=re.compile(r'product-item'))

                if wrapper:
                    for pz_price_tag in wrapper.find_all('pz-price'):
                        text = pz_price_tag.get_text(strip=True)
                        if text:
                            raw_price = text.replace(' TL', '').replace(' tl', '').replace('.', '').replace(',', '.')
                            price = raw_price.strip()
                            break

            if product_id not in seen_ids:
                seen_ids.add(product_id)
                new_items_found = True

                category_products.append({
                    'name': name,
                    'price': price,
                    'url': product_url,
                    'id': product_id
                })

        if not new_items_found:
            print(f"Uyarı: {page}. sayfadaki tüm ürünler zaten taranmış. Sınır aşıldı, döngü kırılıyor.")
            break

        print(f"Sayfa {page} başarıyla çekildi. Bekleniyor...")
        page += 1
        time.sleep(random.uniform(1, 3))

    return category_products


if __name__ == "__main__":
    targets = [
        {"url": "https://www.chakra.com.tr/mobilya/", "name": "mobilya"},
        {"url": "https://www.chakra.com.tr/yatak-odasi/", "name": "yatak_odasi"},
        {"url": "https://www.chakra.com.tr/ev-dekorasyonu/", "name": "ev_dekorasyonu"}
    ]

    all_scraped_data = []

    # Tüm kategorileri gez ve verileri tek bir ana listeye ekle
    for target in targets:
        data = scrape_chakra_category(target["url"], target["name"])
        all_scraped_data.extend(data)

        # Tarama bittikten sonra tek bir CSV'ye kaydet
        if all_scraped_data:
            # Scriptin bulunduğu klasörü (Codes/HomeGoods) bul ve 2 üst dizine (Repo Root) çık
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_dir = os.path.abspath(os.path.join(script_dir, "..", "..", "Datas", "HomeGoods"))

            # Hedef klasör yoksa hata vermemesi için oluştur
            os.makedirs(output_dir, exist_ok=True)

            date_str = datetime.now().strftime("%Y_%m_%d")
            filename = f"chakra_all_categories_{date_str}.csv"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['name', 'price', 'url', 'id'])
                writer.writeheader()
                writer.writerows(all_scraped_data)

            print(f"\nBAŞARILI: Toplam {len(all_scraped_data)} benzersiz ürün tek CSV olarak buraya kaydedildi:")
            print(f"-> {filepath}\n")
        else:
            print("\nUyarı: Hiçbir kategoriden ürün çekilemedi, CSV oluşturulmadı.\n")