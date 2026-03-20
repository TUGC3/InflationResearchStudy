import os
import csv
import re
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
from camoufox.sync_api import Camoufox

# ============================================================
# Per-city price brackets, calibrated from real data (2026-02-27)
# ============================================================

KAYSERI_BRACKETS = [
    (0, 19_999),
    (20_000, 39_999),
    (40_000, 59_999),
    (60_000, 99_999),
    (100_000, 9_999_999),
]

SIVAS_BRACKETS = [
    (0, 19_999),
    (20_000, 39_999),
    (40_000, 59_999),
    (60_000, 99_999),
    (100_000, 9_999_999),
]

TOKAT_BRACKETS = [
    (0, 19_999),
    (20_000, 39_999),
    (40_000, 59_999),
    (60_000, 99_999),
    (100_000, 9_999_999),
]

CITIES = {
    "kayseri": {"folder": "Kayseri", "brackets": KAYSERI_BRACKETS},
    "sivas":   {"folder": "Sivas",   "brackets": SIVAS_BRACKETS},
    "tokat":   {"folder": "Tokat",   "brackets": TOKAT_BRACKETS},
}

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../Datas/HousesRent/"))


# ============================================================
# BROWSER LIFECYCLE HELPER
# ============================================================

class BrowserBlockedError(Exception):
    """safe_goto tüm denemelerde başarısız olunca fırlatılır.
    scrape_city bu exception'ı yakalayarak tarayıcıyı kapatır
    ve close_and_wait() ile 15-20s bekler."""
    pass


def close_and_wait(label, reason="normal"):
    """Tarayıcı kapatıldıktan sonra her zaman çağrılır.
    Şehirler arası geçişte veya CAPTCHA/engel sonrası yeniden
    başlatmada — nedeni ne olursa olsun aynı bekleme uygulanır.
    """
    if reason == "engel":
        print(f"🚫 {label} tarayıcısı engel nedeniyle kapatıldı — çerezler ve oturum temizlendi.")
    else:
        print(f"🧹 {label} tarayıcısı kapatıldı — çerezler ve oturum temizlendi.")
    wait = random.uniform(16.0, 21.0)
    print(f"⏳ Sonraki açılış için {wait:.1f} saniye bekleniyor...")
    time.sleep(wait)


# ============================================================
# PROTECTION HANDLERS
# ============================================================

def get_page_content(page, timeout=10_000):
    """Sayfa navigasyonu bitene kadar bekleyip HTML içeriğini döner.

    Turnstile / redirect sonrası page.content() 'page is navigating'
    hatası verebilir. Bu helper her çağrıda önce load state bekler.
    """
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout)
    except Exception:
        pass  # Zaten yüklenmiş olabilir, devam et
    try:
        return page.content()
    except Exception:
        # Hâlâ navigasyon varsa kısa bekleyip bir kez daha dene
        time.sleep(2)
        return page.content()


def beep_alert(times=3):
    """Windows'ta kısa bip sesi çıkarır — Cloudflare sayfası gelince çağrılır."""
    try:
        import winsound
        for _ in range(times):
            winsound.Beep(1000, 400)   # 1000 Hz, 400ms
            time.sleep(0.15)
    except Exception:
        # Windows değilse (veya winsound yoksa) terminale görsel uyarı bas
        print("\a\a\a")  # terminal bell


def handle_browser_check(page):
    """Sahibinden'in Cloudflare Turnstile sayfasını geçer."""
    if "tarayıcınızı kontrol ediyoruz" not in get_page_content(page).lower():
        return

    print("🤖 Browser check sayfası tespit edildi, Turnstile bekleniyor...")
    beep_alert(times=3)   # 🔔 sesli uyarı
    try:
        page.wait_for_selector("#turnStileWidget", timeout=25_000)
        print("   ⏳ Turnstile token bekleniyor (shadow DOM)...")
        time.sleep(random.uniform(11.0, 14.0))
        page.wait_for_selector("#btn-continue", timeout=15_000)
        page.click("#btn-continue")
        print("✅ 'Devam Et' butonuna tıklandı, sayfa geçişi bekleniyor...")
        page.wait_for_function(
            "() => !document.body.innerText.toLowerCase().includes('tarayıcınızı kontrol ediyoruz')",
            timeout=20_000,
        )
    except Exception as e:
        print(f"⚠️ Browser check geçilemedi: {e}")


def is_waiting_page(html):
    lower = html.lower()
    return any(s in lower for s in ["bir dakika lütfen", "lütfen bekleyiniz"])


def is_login_page(html):
    lower = html.lower()
    signals = ["giriş yap", "üye girişi", "captcha", "güvenlik doğrulama", "robot olmadığınızı"]
    return sum(1 for s in signals if s in lower) >= 1 and "searchresultstable" not in lower


def wait_for_challenge(page, max_wait=20):
    print(f"⏳ Challenge sayfasının kendi kendine çözülmesi bekleniyor (max {max_wait}s)...")
    for i in range(max_wait // 2):
        time.sleep(random.uniform(7.0, 10.0))
        if not is_waiting_page(get_page_content(page)):
            print(f"✅ Challenge ~{(i + 1) * 2}s sonra çözüldü.")
            return True
    print("⏰ Challenge zamanında çözülmedi.")
    return False


def wait_for_listings(page, timeout=15_000):
    try:
        page.wait_for_selector(
            "#searchResultsTable tbody tr.searchResultsItem",
            timeout=timeout,
        )
        return True
    except Exception:
        return False


def goto_with_retry(page, url, retries=3, timeout=60_000):
    """page.goto() çağrısını timeout hatalarına karşı retry ile sarar.

    Timeout 30s → 60s'ye yükseltildi. Her timeout'ta 10-15s bekleyip
    tekrar dener. Tüm denemeler tükenirse BrowserBlockedError fırlatır.
    """
    for attempt in range(1, retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            return  # Başarılı
        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str:
                print(f"   ⏱️ page.goto timeout (deneme {attempt}/{retries}): {url}")
                if attempt < retries:
                    wait = random.uniform(11.0, 16.0)
                    print(f"   {wait:.1f}s bekleniyor...")
                    time.sleep(wait)
                else:
                    print("   ❌ Tüm goto denemeleri tükendi — tarayıcı yeniden başlatılacak.")
                    raise BrowserBlockedError(f"Kalıcı goto timeout: {url}") from e
            else:
                raise BrowserBlockedError(f"goto hatası: {e}") from e


def safe_goto(page, url):
    """Sahibinden'in tüm koruma katmanlarını yöneterek URL'ye gider."""
    goto_with_retry(page, url)
    time.sleep(random.uniform(7.0, 10.0))

    handle_browser_check(page)
    html = get_page_content(page)

    if is_login_page(html):
        print("🔄 Login sayfasına yönlendirildi, tekrar deneniyor...")
        time.sleep(random.uniform(9, 13))
        goto_with_retry(page, url)
        time.sleep(random.uniform(7, 10))
        handle_browser_check(page)
        html = get_page_content(page)

    if is_waiting_page(html):
        resolved = wait_for_challenge(page)
        if resolved:
            handle_browser_check(page)
            html = get_page_content(page)
        else:
            print("🔄 Challenge takılı kaldı, tekrar yükleniyor...")
            goto_with_retry(page, url)
            time.sleep(random.uniform(7, 10))
            handle_browser_check(page)
            html = get_page_content(page)
            if is_waiting_page(html):
                wait_for_challenge(page)
                handle_browser_check(page)
                html = get_page_content(page)

    if is_login_page(html):
        print("🔄 Login/CAPTCHA sayfası, tekrar deneniyor...")
        time.sleep(random.uniform(7, 11))
        goto_with_retry(page, url)
        time.sleep(random.uniform(7, 10))
        handle_browser_check(page)
        html = get_page_content(page)

        if is_waiting_page(html):
            wait_for_challenge(page)
            handle_browser_check(page)
            html = get_page_content(page)

        if is_login_page(html):
            print("❌ Yeniden denemeden sonra hâlâ engellendi — tarayıcı yeniden başlatılacak.")
            raise BrowserBlockedError(f"Kalıcı engel: {url}")

    wait_for_listings(page)
    return True


# ============================================================
# PRICE NORMALIZATION
# ============================================================

def normalize_price(price_text):
    if not price_text or price_text == "N/A":
        return None
    cleaned = price_text.lower().replace("tl", "").replace("₺", "").strip()
    cleaned = re.sub(r"[^\d,\.]", "", cleaned)
    if not cleaned:
        return None

    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 1 and all(p.isdigit() for p in parts):
            if all(len(p) == 3 for p in parts[1:]):
                cleaned = "".join(parts)

    try:
        return float(cleaned)
    except ValueError:
        return None


# ============================================================
# DISCOVERY
# ============================================================

def discover_pages(page, city_url_name, brackets):
    """Tüm bracket + sayfalama kombinasyonlarını tarar, HTML'i önbelleğe alır."""
    discovered = []

    for min_price, max_price in brackets:
        print(f"\n🔍 Bracket {min_price}-{max_price} TL taranıyor...")
        page_num    = 1
        current_url = (
            f"https://www.sahibinden.com/kiralik/{city_url_name}"
            f"?pagingSize=50&price_min={min_price}&price_max={max_price}"
        )

        while True:
            safe_goto(page, current_url)

            html  = get_page_content(page)
            soup  = BeautifulSoup(html, "html.parser")
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                html_lower = html.lower()
                if "ilan bulunamadı" in html_lower or "bulunamamıştır" in html_lower:
                    print(f"   {min_price}-{max_price} TL aralığında ilan yok.")
                else:
                    print(f"   Sayfa {page_num}'de ilan bulunamadı, durduruluyor.")
                break

            discovered.append((current_url, html, min_price, max_price))
            print(f"   ✔ Sayfa {page_num} kuyruğa alındı ({len(listings)} ilan)")

            next_button = soup.find("a", title="Sonraki")
            if next_button and "href" in next_button.attrs:
                current_url = "https://www.sahibinden.com" + next_button["href"]
                page_num   += 1
                time.sleep(random.uniform(7.0, 10.0))
            else:
                print(f"   Son sayfa — bracket {min_price}-{max_price} TL tamamlandı.")
                break

    print(f"\n📋 Discovery tamamlandı. Toplam {len(discovered)} sayfa kuyruğa alındı.")
    return discovered


# ============================================================
# EXTRACTION
# ============================================================

def extract_page(html):
    """Önbellekteki HTML'den ilan verilerini çeker. Ek istek gönderilmez."""
    soup     = BeautifulSoup(html, "html.parser")
    listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
    results  = []

    for row in listings:
        try:
            price_elem = row.select_one(".searchResultsPriceValue")
            price      = normalize_price(price_elem.text.strip() if price_elem else None)

            location_elem = row.select_one(".searchResultsLocationValue")
            district = " / ".join(location_elem.stripped_strings) if location_elem else "N/A"

            attributes = row.select(".searchResultsAttributeValue")
            rooms = attributes[1].text.strip() if len(attributes) > 1 else "N/A"

            if price is not None and district != "N/A":
                results.append({"District": district, "Rooms": rooms, "Price": price})
        except Exception as e:
            print(f"   ⚠️ Satır parse hatası: {e}")
            continue

    return results


def extract_all_pages(discovered_pages, folder_name):
    """Önbellekteki tüm sayfalardan veri çeker — sıfır ek istek."""
    print(f"\n{'=' * 50}")
    print(f"VERİ ÇEKME: {folder_name.upper()}")
    print(f"{'=' * 50}")

    for i, (url, html, min_price, max_price) in enumerate(discovered_pages, 1):
        print(f"\n[{i}/{len(discovered_pages)}] Bracket {min_price}-{max_price} TL çekiliyor")
        records = extract_page(html)

        if records:
            save_to_csv_incremental(folder_name, records)
            print(f"   ✅ {len(records)} kayıt kaydedildi.")
        else:
            print(f"   ⚠️ Bu sayfadan kayıt çıkmadı.")


# ============================================================
# CSV HELPER
# ============================================================

def save_to_csv_incremental(folder_name, data_batch):
    today_str  = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(DATA_BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_path  = os.path.join(target_dir, f"{today_str}.csv")

    file_exists = os.path.isfile(file_path)
    with open(file_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)

    print(f"   💾 {len(data_batch)} kayıt eklendi → {file_path}")


# ============================================================

# ============================================================
# PER-CITY SCRAPE — her şehir için sıfırdan tarayıcı
# ============================================================

def scrape_city(city_url_name, city_data):
    """
    Her şehir için bağımsız bir Camoufox örneği başlatır.

    Kalıcı profil yolu verilmediği için tarayıcı her açılışta
    tamamen temiz başlar: çerez, önbellek, localStorage, oturum —
    hiçbir şey bir önceki şehirden taşınmaz.

    BrowserBlockedError fırlatılırsa (CAPTCHA / kalıcı engel):
      1. `with` bloğu otomatik kapanır → tarayıcı + profil silinir
      2. close_and_wait() ile 15-20s beklenir
      3. Yeni clean-slate tarayıcıyla yeniden denenir (max 3 kez)

    Tarayıcı her kapandığında — ister normal, ister engel nedeniyle —
    close_and_wait() çağrılır, bekleme süresi her zaman aynıdır.
    """
    folder_name  = city_data["folder"]
    brackets     = city_data["brackets"]
    max_restarts = 3

    for attempt in range(1, max_restarts + 1):
        print(f"\n{'=' * 50}")
        print(f"ŞEHİR: {folder_name.upper()} — clean slate tarayıcı başlatılıyor 🧹"
              + (f" (deneme {attempt}/{max_restarts})" if attempt > 1 else ""))
        print(f"{'=' * 50}")

        try:
            with Camoufox(headless=False) as browser:
                page = browser.new_page()

                # COMPONENT 1: Tüm sayfa URL + HTML keşfi
                # BrowserBlockedError burada fırlatılabilir →
                # with bloğu kapanır, aşağıdaki except yakalanır
                discovered_pages = discover_pages(page, city_url_name, brackets)

                # COMPONENT 2: Önbellekteki HTML'den veri çekimi (sıfır ek istek)
                extract_all_pages(discovered_pages, folder_name)

            # ── Normal kapanış ──────────────────────────────
            close_and_wait(folder_name, reason="normal")
            break  # Başarılı, döngüden çık

        except BrowserBlockedError as e:
            # ── Engel nedeniyle kapanış ─────────────────────
            # `with` bloğu zaten kapandı (exception tarafından)
            print(f"   Engel detayı: {e}")
            if attempt < max_restarts:
                print(f"🔄 Yeniden başlatılıyor (deneme {attempt + 1}/{max_restarts})...")
                close_and_wait(folder_name, reason="engel")
            else:
                print(f"❌ {max_restarts} denemeden sonra {folder_name} atlandı.")
                close_and_wait(folder_name, reason="engel")


# ============================================================
# MAIN
# ============================================================

def main():
    for city_url_name, city_data in CITIES.items():
        scrape_city(city_url_name, city_data)

    print("\n✅ Tüm şehirler tamamlandı.")


if __name__ == "__main__":
    main()