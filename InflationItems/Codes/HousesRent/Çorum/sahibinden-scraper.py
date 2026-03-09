import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import csv
import time
from datetime import date

CITIES = {
    "corum":    "https://www.sahibinden.com/kiralik-daire/corum",
    "cankiri":  "https://www.sahibinden.com/kiralik-daire/cankiri",
    "kirikkale":"https://www.sahibinden.com/kiralik-daire/kirikkale",
    "kirsehir": "https://www.sahibinden.com/kiralik-daire/kirsehir"
}

driver = uc.Chrome(version_main=145)

"""driver.get("https://secure.sahibinden.com/giris")

input("Tarayıcıda giriş yap, sonra buraya tıkla ve Enter'a bas...")"""


for sehir, base_url in CITIES.items():
    print(f"\n{sehir.upper()} işleniyor...")

    driver.get(base_url)
    time.sleep(10)


    sayfa_linkleri = driver.find_elements(By.CSS_SELECTOR, ".pageNavigator a")
    numaralar = []
    for a in sayfa_linkleri:
        if "prevNextBut" in (a.get_attribute("class") or ""):
            break  # sonraki butonuna gelince dur
        try:
            numaralar.append(int(a.text.strip()))
        except:
            continue
    son_sayfa = max(numaralar) if numaralar else 1
    print(f"Toplam sayfa: {son_sayfa}")

    with open(f"{sehir}_{date.today()}.csv", mode="w", newline="", encoding="utf-8-sig") as csvfile:
        yazici = csv.writer(csvfile)
        yazici.writerow(["Date", "Price", "District", "Rooms"])

        for sayfa in range(son_sayfa):
            offset = sayfa * 20
            url = f"{base_url}?pagingOffset={offset}"
            driver.get(url)
            time.sleep(5)

            rows = driver.find_elements(By.CSS_SELECTOR, "tr.searchResultsItem")
            print(f"  Sayfa {sayfa+1}: {len(rows)} ilan")

            for row in rows:
                try:
                    price    = row.find_element(By.CSS_SELECTOR, ".searchResultsPriceValue").text.strip()
                    location = row.find_element(By.CSS_SELECTOR, ".searchResultsLocationValue").text.strip()
                    attrs    = row.find_elements(By.CSS_SELECTOR, ".searchResultsAttributeValue")
                    rooms    = attrs[1].text.strip()

                    yazici.writerow([date.today(), price, location, rooms])
                    print(f"  {location} | {rooms} | {price}")
                except Exception as e:
                    print(f"  Hata: {e}")
                    continue

    print(f"{sehir} CSV kaydedildi!")

driver.quit()
print("\nTüm şehirler tamamlandı!")
