
import pandas as pd
import datetime
import csv
import requests


month = datetime.date.today().month
day = datetime.date.today().day
api_url = "https://www.beymen.com/tr/kozmetik-30894"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.beymen.com/tr"
}

total_data = []
seen_product_ids = set()
page = 1

while True:
    try:
        response = requests.get(f"https://www.beymen.com/tr/Product/GetFilteredProductList_V2?currentFacets=marka_3,cinsiyet_6,alt-kategori_564,urun-cesidi_4,renk_23,surdurulebilir-urunler_81,koleksiyon-adi_72,fiyat_26,urun-ailesi_67&urunSayisi=48&categoryId=30894&includeFacets=&includeDocuments=true&currentScrollCount=1&siralama=akillisiralama&sayfa={page}", headers=headers)
        response.raise_for_status()
        data = response.json()

        products = data.get("Data", {}).get("ProductListingItemList", [])
        if not products:
            break

        new_items = 0
        for item in products:
            pid = item.get("ProductId")
            if pid in seen_product_ids:
                continue
            seen_product_ids.add(pid)

            brand = item.get("BrandName", "")
            name = item.get("DisplayName", "")
            price = item.get("ActualPrice", "")
            total_data.append([f"{brand} {name}", price])
            new_items += 1


        if new_items == 0:
            break

        page += 1

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        break
    except ValueError as e:
        print(f"JSON error: {e}")
        break

csv_name = f"Datas\\Cosmetics{month}-{day}.csv"
with open(csv_name, mode="a", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(total_data)
print("Saved " ,len(total_data))




