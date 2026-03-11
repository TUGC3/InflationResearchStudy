# -*- coding: utf-8 -*-
"""
Created on Wed Mar 11 10:45:04 2026

@author: orenl
"""

import time
import re
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

base_url = "https://www.altinyildizclassics.com/"
driver.get(base_url)
time.sleep(5)

# -------------------------
# KATEGORİLERİ TOPLA
# -------------------------
links = driver.find_elements(By.TAG_NAME, "a")
categories = set()

for l in links:
    href = l.get_attribute("href")
    if href and "-c" in href and "altinyildizclassics.com" in href:
        categories.add(href)

categories = list(categories)
print("Kategori sayısı:", len(categories))

all_products = []

# -------------------------
# HER KATEGORİ İÇİN AYRI unique set
# -------------------------
for cat in categories:
    print("\nKategori:", cat)

    page = 1
    seen_in_category = set()

    while True:
        if page == 1:
            url = cat
        else:
            sep = "&" if "?" in cat else "?"
            url = f"{cat}{sep}pagenumber={page}"

        driver.get(url)
        time.sleep(4)

        products = driver.find_elements(By.CLASS_NAME, "ac-pc")
        print(f"Sayfa {page} → {len(products)} ürün")

        if len(products) == 0:
            print("Ürün yok, kategori bitti")
            break

        new_found = 0

        for p in products:
            try:
                link = p.find_element(By.TAG_NAME, "a").get_attribute("href")

                if not link or link in seen_in_category:
                    continue

                seen_in_category.add(link)
                new_found += 1

                name = link.rstrip("/").split("/")[-1]

                price = "NA"
                for selector in [".ac-pc__price", "[class*='price']"]:
                    try:
                        price = p.find_element(By.CSS_SELECTOR, selector).text.strip()
                        if price:
                            break
                    except:
                        pass

                all_products.append({
                    "urun": name,
                    "fiyat": price,
                    "kategori": cat,
                    "url": link
                })

            except:
                pass

        # Bu sayfada hiç yeni ürün gelmediyse artık devam etme
        if new_found == 0:
            print("Yeni ürün gelmedi, kategori bitti")
            break

        # İsteğe bağlı: toplam ürün sayısına ulaştıysak dur
        try:
            count_text = driver.find_element(By.CLASS_NAME, "product-count").text
            total_products = int(re.findall(r"\d+", count_text)[0])
            print("Toplam ürün:", total_products)

            if len(seen_in_category) >= total_products:
                print("Toplam ürün sayısına ulaşıldı")
                break
        except:
            pass

        page += 1

driver.quit()

# -------------------------
# DATAFRAME / CSV
# -------------------------
df = pd.DataFrame(all_products).drop_duplicates(subset=["url"])
print("\nToplam çekilen ürün:", len(df))

df.to_csv("altinyildiz_tum_urunler.csv", index=False, encoding="utf-8-sig")
print("CSV oluşturuldu: altinyildiz_tum_urunler.csv")