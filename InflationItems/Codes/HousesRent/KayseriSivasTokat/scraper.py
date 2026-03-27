"""
scraper.py — Kayseri / Sivas / Tokat Kiralık Konut Scraper
Çekirdek scraping mantığı. Camoufox async API kullanır.

Koruma sayfaları:
  - Otomatik bypass YOK — tespit edilince kullanıcı uyarılır,
    tarayıcıda çözdükten sonra konsola ENTER basar, devam eder.
"""

import asyncio
import csv
import json
import logging
import os
import queue
import random
import re
import time
from datetime import datetime
from functools import partial

from bs4 import BeautifulSoup
from camoufox.async_api import AsyncCamoufox

import config

logger = logging.getLogger(__name__)


# ============================================================
# ÖZEL EXCEPTION'LAR  (konsol komutları için sinyal mekanizması)
# ============================================================

class SkipCitySignal(Exception):
    """Kullanıcı 'skip' komutu verdi — mevcut şehri atla."""
    pass


class SkipBracketSignal(Exception):
    """Kullanıcı 'next' komutu verdi — mevcut bracket'ı atla."""
    pass


class StopSignal(Exception):
    """Kullanıcı 'stop' komutu verdi — scraper'ı durdur."""
    pass


class BrowserBlockedError(Exception):
    """Kalıcı engel — tarayıcıyı yeniden başlatmak gerekiyor."""
    pass


# ============================================================
# KONSOL KOMUT KONTROLÜ
# ============================================================

def check_commands(cmd_queue: queue.Queue) -> None:
    """
    Komut kuyruğunu kontrol eder ve uygun signal fırlatır.
    Her sayfa döngüsünün başında çağrılır.

    Komutlar:
      skip   → mevcut şehri atla  (SkipCitySignal)
      next   → mevcut bracket'ı atla  (SkipBracketSignal)
      stop   → scraper'ı durdur  (StopSignal)
    """
    while not cmd_queue.empty():
        cmd = cmd_queue.get_nowait().strip().lower()
        if cmd in ("skip", "skip city"):
            logger.warning("⚡ Komut: şehir atlanıyor...")
            raise SkipCitySignal()
        elif cmd in ("next", "skip bracket"):
            logger.warning("⚡ Komut: bracket atlanıyor...")
            raise SkipBracketSignal()
        elif cmd == "stop":
            logger.warning("⚡ Komut: scraper durduruluyor...")
            raise StopSignal()
        else:
            logger.info("⚡ Bilinmeyen komut: '%s'", cmd)


# ============================================================
# SES UYARISI
# ============================================================

def beep_alert() -> None:
    """Koruma sayfası gelince Windows sistem sesi çalar."""
    try:
        import winsound
        for sound in ["SystemExclamation", "SystemHand", "SystemExclamation"]:
            try:
                winsound.PlaySound(sound, winsound.SND_ALIAS | winsound.SND_SYNC)
                time.sleep(0.3)
            except Exception:
                try:
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                    time.sleep(0.3)
                except Exception:
                    pass
    except Exception:
        print("\a\a\a")


# ============================================================
# MANUEL KORUMA SAYFASI BEKLEYİCİ
# ============================================================

async def wait_for_manual_solve(loop: asyncio.AbstractEventLoop,
                                 reason: str = "Bot koruması") -> None:
    """
    Kullanıcıdan manuel çözüm bekler.

    input() async event loop'u bloklamaz — executor'da çalıştırılır.
    Bu sayede loop diğer coroutine'leri (varsa) çalıştırmaya devam edebilir.
    """
    beep_alert()
    print(f"\n{'=' * 55}")
    print(f"🔒 {reason} tespit edildi!")
    print("   1. Tarayıcıda doğrulamayı tamamlayın.")
    print("   2. Tamamladıktan sonra buraya ENTER basın.")
    print(f"{'=' * 55}")
    await loop.run_in_executor(None, input, "   ▶ ENTER: ")
    print("✅ Devam ediliyor...")


# ============================================================
# KORUMA SAYFASI TESPİTİ
# ============================================================

def is_protection_page(html: str, page) -> tuple[bool, str]:
    """
    Herhangi bir koruma sayfasını tespit eder.

    Tespit edilen tipler:
    1. PerimeterX (px-captcha)   — "Bağlantınız kontrol ediliyor" + px-captcha
    2. Cloudflare Managed        — /cs/checkLoading URL
    3. Cloudflare Turnstile      — cf-turnstile widget
    4. Cloudflare Waiting Page   — "bir dakika lütfen" vb.

    Returns:
        (True, açıklama) — koruma sayfasıysa
        (False, "")      — normal sayfaysa
    """
    lower = html.lower()

    # ------------------------------------------------------------------
    # DOM SELECTOR BAZLI TESPİT
    # Her bot korumasının sayfaya bıraktığı CSS id/class'ları kontrol
    # eder. HTML'de bu string'lerden biri geçiyorsa koruma sayfasıdır.
    # ------------------------------------------------------------------
    CAPTCHA_SIGNATURES: list[tuple[str, str]] = [
        # (html'de aranacak string, açıklama)
        ("px-captcha",           "PerimeterX"),
        ("cf-turnstile",         "Cloudflare Turnstile"),
        ("datadome-captcha",     "DataDome"),
        ("g-recaptcha",          "Google reCAPTCHA"),
        ("h-captcha",            "hCaptcha"),
        ("aws-waf-captcha",      "AWS WAF CAPTCHA"),
        ("geetest-captcha",      "GeeTest CAPTCHA"),
        ("keycaptcha",           "KeyCAPTCHA"),
        ("funcaptcha",           "FunCaptcha"),
        ("yandex-captcha",       "Yandex CAPTCHA"),
    ]

    for signature, name in CAPTCHA_SIGNATURES:
        if signature in lower:
            return True, f"{name} ({signature})"

    # ------------------------------------------------------------------
    # METİN BAZLI TESPİT — sahibinden'e özgü Türkçe koruma metinleri
    # ------------------------------------------------------------------
    if "olağan dışı erişim" in lower or "bağlantınız kontrol ediliyor" in lower:
        return True, "PerimeterX Bağlantı Kontrolü"

    # Cloudflare Managed Challenge (checkLoading) — URL bazlı
    try:
        url = page.url.lower()
        if "/cs/checkloading" in url or "secure.sahibinden.com" in url:
            return True, "Cloudflare Managed Challenge (checkLoading)"
    except Exception:
        pass

    if "güvenlik doğrulaması" in lower:
        return True, "Cloudflare Güvenlik Doğrulaması"

    if "tarayıcınızı kontrol ediyoruz" in lower:
        return True, "Cloudflare Tarayıcı Kontrolü"

    if any(s in lower for s in ["bir dakika lütfen", "lütfen bekleyiniz", "doğrulanıyor"]):
        return True, "Cloudflare Waiting Page"

    return False, ""


def is_login_page(html: str, page=None) -> bool:
    """
    Login / CAPTCHA duvarı tespiti.

    URL bazlı kontrol önce — secure.sahibinden.com/giris kesin login sayfası.
    HTML bazlı kontrol yedek — eşik 2, footer'daki tek "giriş yap" yanlış pozitif vermesin.
    """
    # URL bazlı — en güvenilir yöntem
    if page is not None:
        try:
            url = page.url.lower()
            if "secure.sahibinden.com/giris" in url or "/giris?" in url:
                return True
        except Exception:
            pass

    lower = html.lower()
    signals = [
        "giriş yap", "üye girişi", "captcha",
        "güvenlik doğrulama", "robot olmadığınızı",
    ]
    return (
        sum(1 for s in signals if s in lower) >= 2
        and "searchresultstable" not in lower
    )


# ============================================================
# PAGE CONTENT HELPER
# ============================================================

async def get_page_content(page, timeout: int = 10_000) -> str:
    """Navigasyon bitmeden page.content() çağrısını önler."""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=timeout)
    except Exception:
        pass
    try:
        return await page.content()
    except Exception:
        await asyncio.sleep(3)
        return await page.content()


# ============================================================
# GOTO WITH RETRY
# ============================================================

async def goto_with_retry(page, url: str, retries: int = 3,
                           timeout: int = 60_000) -> None:
    """page.goto() timeout hatalarına karşı retry ile sarar."""
    for attempt in range(1, retries + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            return
        except Exception as e:
            if "timeout" in str(e).lower():
                logger.warning("⏱️ goto timeout (deneme %d/%d)", attempt, retries)
                if attempt < retries:
                    wait = random.uniform(*config.GOTO_RETRY_WAIT)
                    logger.info("   %.1fs bekleniyor...", wait)
                    await asyncio.sleep(wait)
                else:
                    raise BrowserBlockedError(f"Kalıcı goto timeout: {url}") from e
            else:
                raise BrowserBlockedError(f"goto hatası: {e}") from e


# ============================================================
# SAFE GOTO
# ============================================================

async def safe_goto(page, url: str, loop: asyncio.AbstractEventLoop) -> str:
    """
    URL'ye gider, tüm koruma katmanlarını yönetir.

    Koruma sayfası tespit edilince:
      1. Sesli uyarı
      2. Kullanıcıdan ENTER bekler
      3. ENTER sonrası sayfanın normal yüklendiğini doğrular

    Returns: sayfanın HTML içeriği
    """
    await goto_with_retry(page, url)
    await asyncio.sleep(random.uniform(*config.PAGE_LOAD_AFTER_GOTO))

    html = await get_page_content(page)

    # Koruma sayfası kontrolü — döngü: kullanıcı çözene kadar bekle
    for _ in range(5):
        is_prot, reason = is_protection_page(html, page)
        if not is_prot:
            break
        logger.warning("🔒 %s", reason)
        await wait_for_manual_solve(loop, reason)
        await asyncio.sleep(random.uniform(*config.POST_CHECK_WAIT))
        html = await get_page_content(page)

    # Login / CAPTCHA kontrolü
    if is_login_page(html, page):
        logger.warning("🔄 Login/CAPTCHA sayfası, tekrar deneniyor...")
        await asyncio.sleep(random.uniform(*config.LOGIN_RETRY_WAIT))
        await goto_with_retry(page, url)
        await asyncio.sleep(random.uniform(*config.PAGE_LOAD_AFTER_GOTO))
        html = await get_page_content(page)

        for _ in range(5):
            is_prot, reason = is_protection_page(html, page)
            if not is_prot:
                break
            logger.warning("🔒 %s", reason)
            await wait_for_manual_solve(loop, reason)
            await asyncio.sleep(random.uniform(*config.POST_CHECK_WAIT))
            html = await get_page_content(page)

        if is_login_page(html, page):
            raise BrowserBlockedError(f"Kalıcı engel: {url}")

    # İlan tablosunun yüklenmesini bekle
    try:
        await page.wait_for_selector(
            "#searchResultsTable tbody tr.searchResultsItem",
            timeout=20_000,
        )
    except Exception:
        pass  # Boş sayfa da olabilir — caller kontrol eder

    return await get_page_content(page)


# ============================================================
# HOMEPAGE WARMUP
# ============================================================

async def warmup_homepage(page, loop: asyncio.AbstractEventLoop) -> None:
    """
    Sahibinden ana sayfasına gider.

    Doğrudan bracket URL'ine gitmek yerine önce ana sayfa:
    - cf_clearance cookie'sini ana sayfada alır
    - Referrer header'ı doğal görünür
    - Cloudflare trust score'unu artırır
    """
    logger.info("🏠 Ana sayfa ısınma turu başlıyor...")
    try:
        await page.goto(
            "https://www.sahibinden.com",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        await asyncio.sleep(random.uniform(*config.HOMEPAGE_WAIT))

        html = await get_page_content(page)

        for _ in range(5):
            is_prot, reason = is_protection_page(html, page)
            if not is_prot:
                break
            logger.warning("🔒 Ana sayfada %s", reason)
            await wait_for_manual_solve(loop, f"Ana sayfa — {reason}")
            await asyncio.sleep(random.uniform(*config.POST_CHECK_WAIT))
            html = await get_page_content(page)

        logger.info("✅ Ana sayfa ısınma turu tamamlandı.")
    except BrowserBlockedError:
        logger.warning("⚠️ Ana sayfa ısınmasında engel, devam ediliyor...")
    except Exception as e:
        logger.warning("⚠️ Ana sayfa ısınma hatası (önemsiz): %s", e)


# ============================================================
# PRICE NORMALIZATION
# ============================================================

def normalize_price(price_text: str | None) -> float | None:
    if not price_text or price_text == "N/A":
        return None
    cleaned = price_text.lower().replace("tl", "").replace("₺", "").strip()
    cleaned = re.sub(r"[^\d,.]", "", cleaned)
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
# ROOMS HELPERS
# ============================================================

def resolve_rooms_index(soup: BeautifulSoup) -> int | None:
    """Tablo başlığından 'Oda' sütununun indeksini dinamik bulur."""
    headers = [
        th.get_text(strip=True)
        for th in soup.select(
            "#searchResultsTable thead th.searchResultsAttributeHeader"
        )
    ]
    for idx, header in enumerate(headers):
        if "oda" in header.lower().replace("ı", "i"):
            return idx
    return None


def extract_rooms(attributes, room_index: int | None) -> str:
    if room_index is not None and len(attributes) > room_index:
        return attributes[room_index].text.strip()
    if len(attributes) > 1:
        return attributes[1].text.strip()
    if len(attributes) == 1:
        return attributes[0].text.strip()
    return "N/A"


# ============================================================
# CSV HELPER
# ============================================================

def save_incremental(city_name: str, data_batch: list[dict]) -> None:
    """Klasör yoksa oluşturur, mevcut CSV'ye ekler."""
    if not data_batch:
        return
    csv_path = config.get_city_csv_path(city_name)
    os.makedirs(config.get_city_output_dir(city_name), exist_ok=True)

    file_exists = os.path.isfile(csv_path)
    with open(csv_path, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)

    logger.info("   💾 %d kayıt eklendi → %s", len(data_batch), csv_path)


# ============================================================
# CHECKPOINT
# ============================================================

def load_checkpoint() -> dict:
    cp = config.get_checkpoint_file()
    if os.path.exists(cp):
        try:
            with open(cp, encoding="utf-8") as f:
                data = json.load(f)
            logger.info(
                "📌 Checkpoint yüklendi → şehir: %s, bracket: %s, sayfa: %s",
                data.get("city"), data.get("bracket_index"), data.get("page_num"),
            )
            return data
        except Exception as e:
            logger.warning("⚠️ Checkpoint okunamadı: %s", e)
    return {}


def save_checkpoint(city_slug: str, bracket_index: int, page_num: int) -> None:
    """CSV'ye yazıldıktan SONRA çağrılır — veri kaybını önler."""
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    data = {
        "city":          city_slug,
        "bracket_index": bracket_index,
        "page_num":      page_num,
        "saved_at":      datetime.now().isoformat(),
    }
    try:
        with open(config.get_checkpoint_file(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("⚠️ Checkpoint yazılamadı: %s", e)


def clear_checkpoint() -> None:
    cp = config.get_checkpoint_file()
    if os.path.exists(cp):
        os.remove(cp)
        logger.info("🗑️ Checkpoint temizlendi.")


def get_resume_point(checkpoint: dict, city_slug: str) -> tuple[int, int]:
    if checkpoint.get("city") == city_slug:
        return checkpoint.get("bracket_index", 0), checkpoint.get("page_num", 1)
    return 0, 1


# ============================================================
# TEK SAYFAYI PARSE ET
# ============================================================

def parse_page(html: str) -> list[dict]:
    """Bir arama sayfasından ilan kayıtlarını çıkarır."""
    soup = BeautifulSoup(html, "html.parser")
    listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
    room_index = resolve_rooms_index(soup)
    records = []

    for row in listings:
        try:
            price_elem = row.select_one(".searchResultsPriceValue")
            price      = normalize_price(price_elem.text.strip() if price_elem else None)

            loc_elem = row.select_one(".searchResultsLocationValue")
            district = " / ".join(loc_elem.stripped_strings) if loc_elem else "N/A"

            attributes = row.select(".searchResultsAttributeValue")
            rooms      = extract_rooms(attributes, room_index)

            if price is not None and district != "N/A":
                records.append({"District": district, "Rooms": rooms, "Price": price})
        except Exception as e:
            logger.debug("Satır parse hatası: %s", e)

    return records, soup


# ============================================================
# CORE SCRAPE
# ============================================================

async def scrape_city_brackets(
    page,
    city_slug: str,
    city_name: str,
    brackets: list[tuple[int, int]],
    loop: asyncio.AbstractEventLoop,
    cmd_queue: queue.Queue,
    start_bracket: int = 0,
    start_page: int = 1,
) -> int:
    """
    Tüm bracket + sayfalamaları dolaşır.

    Her sayfa anında CSV'ye yazılır — blok gelirse o ana kadar
    toplanan veri kaybolmaz.

    Checkpoint, CSV'ye yazıldıktan SONRA güncellenir.
    """
    total_saved = 0

    for bracket_index, (min_price, max_price) in enumerate(brackets):

        # Konsol komutlarını kontrol et
        check_commands(cmd_queue)

        if bracket_index < start_bracket:
            logger.info(
                "   ⏭️ Bracket %d-%d TL checkpoint'te tamamlandı, atlanıyor.",
                min_price, max_price,
            )
            continue

        logger.info("\n🔍 Bracket %d-%d TL taranıyor...", min_price, max_price)

        if bracket_index > start_bracket:
            wait = random.uniform(*config.BETWEEN_BRACKETS)
            logger.info("   😮‍💨 Bracket molası: %.1fs", wait)
            await asyncio.sleep(wait)

        page_num    = start_page if bracket_index == start_bracket else 1
        current_url = (
            f"https://www.sahibinden.com/kiralik/{city_slug}"
            f"?pagingSize={config.PAGE_SIZE}"
            f"&price_min={min_price}&price_max={max_price}"
        )

        if page_num > 1:
            current_url += f"&pagingOffset={(page_num - 1) * config.PAGE_SIZE}"
            logger.info("   📌 Checkpoint'ten devam: sayfa %d", page_num)

        while True:
            # Güvenlik kapağı — sonsuz döngü önleme
            if page_num > config.MAX_PAGES_PER_BRACKET:
                logger.warning(
                    "   ⚠️ Maksimum sayfa sayısına ulaşıldı (%d), bracket tamamlandı.",
                    config.MAX_PAGES_PER_BRACKET,
                )
                break

            # Konsol komutlarını kontrol et
            check_commands(cmd_queue)

            html = await safe_goto(page, current_url, loop)
            records, soup = parse_page(html)

            if not records:
                html_lower = html.lower()
                if "ilan bulunamadı" in html_lower or "bulunamamıştır" in html_lower:
                    logger.info("   Bu bracket'ta ilan yok.")
                else:
                    logger.info(
                        "   Sayfa %d'de ilan bulunamadı, bracket tamamlandı.", page_num
                    )
                break

            save_incremental(city_name, records)
            total_saved += len(records)
            logger.info(
                "   ✔ Sayfa %d: %d kayıt yazıldı (toplam: %d)",
                page_num, len(records), total_saved,
            )

            # CSV'ye yazıldıktan SONRA checkpoint güncelle
            save_checkpoint(city_slug, bracket_index, page_num)

            next_button = soup.find("a", title="Sonraki")
            if next_button and "href" in next_button.attrs:
                current_url = "https://www.sahibinden.com" + next_button["href"]
                page_num   += 1
                await asyncio.sleep(random.uniform(*config.BETWEEN_PAGES))
            else:
                logger.info(
                    "   Son sayfa — bracket %d-%d TL tamamlandı.", min_price, max_price
                )
                break

    return total_saved


# ============================================================
# PER-CITY SCRAPE
# ============================================================

async def scrape_city(
    city: dict,
    checkpoint: dict,
    cmd_queue: queue.Queue,
) -> None:
    """
    Her şehir için bağımsız AsyncCamoufox örneği başlatır.

    Clean slate — kalıcı profil yok, her açılışta sıfırdan başlar.
    Tarayıcı with bloğu kapanınca tüm çerezler/oturum silinir.

    BrowserBlockedError fırlatılırsa MAX_RESTARTS_PER_CITY kez yeniden dener.
    """
    city_slug = city["url_slug"]
    city_name = city["name"]
    brackets  = city["brackets"]
    loop      = asyncio.get_event_loop()

    start_bracket, start_page = get_resume_point(checkpoint, city_slug)
    if start_bracket > 0 or start_page > 1:
        logger.info(
            "📌 %s için checkpoint: bracket %d, sayfa %d",
            city_name, start_bracket, start_page,
        )

    for attempt in range(1, config.MAX_RESTARTS_PER_CITY + 1):
        logger.info("\n%s", "=" * 50)
        logger.info(
            "ŞEHİR: %s — clean slate tarayıcı başlatılıyor 🧹%s",
            city_name.upper(),
            f" (deneme {attempt}/{config.MAX_RESTARTS_PER_CITY})" if attempt > 1 else "",
        )
        logger.info("%s", "=" * 50)

        try:
            async with AsyncCamoufox(
                headless=False,
                humanize=True,
                disable_coop=True,
                i_know_what_im_doing=True,
                os=config.CAMOUFOX_OS,
                locale=config.CAMOUFOX_LOCALE,
            ) as browser:
                page = await browser.new_page()

                # Ana sayfa ısınma turu
                await warmup_homepage(page, loop)
                await asyncio.sleep(random.uniform(*config.HOMEPAGE_WAIT))

                total = await scrape_city_brackets(
                    page=page,
                    city_slug=city_slug,
                    city_name=city_name,
                    brackets=brackets,
                    loop=loop,
                    cmd_queue=cmd_queue,
                    start_bracket=start_bracket,
                    start_page=start_page,
                )
                logger.info(
                    "\n✅ %s tamamlandı — toplam %d kayıt kaydedildi.",
                    city_name, total,
                )

            # Normal kapanış — 30s bekle
            logger.info(
                "🧹 %s tarayıcısı kapatıldı — çerezler ve oturum temizlendi.", city_name
            )
            logger.info("⏳ Sonraki açılış için 30 saniye bekleniyor...")
            await asyncio.sleep(config.CITY_CLOSE_WAIT)
            break

        except (SkipCitySignal, StopSignal):
            raise  # Yukarıya ilet

        except SkipBracketSignal:
            # Bracket skip gelirse şehri yeniden başlatmaya gerek yok,
            # sadece bir sonraki iterasyonda checkpoint'ten devam et
            logger.warning("⚡ Bracket atlandı, şehir devam edecek...")
            start_bracket, start_page = get_resume_point(
                load_checkpoint(), city_slug
            )
            start_bracket += 1  # Bir sonraki bracket'tan başla
            start_page = 1
            continue

        except BrowserBlockedError as e:
            logger.error("   Engel detayı: %s", e)
            start_bracket, start_page = get_resume_point(
                load_checkpoint(), city_slug
            )
            if attempt < config.MAX_RESTARTS_PER_CITY:
                logger.info(
                    "🔄 Yeniden başlatılıyor (deneme %d/%d)...",
                    attempt + 1, config.MAX_RESTARTS_PER_CITY,
                )
                logger.info("⏳ 30 saniye bekleniyor...")
                await asyncio.sleep(config.CITY_CLOSE_WAIT)
            else:
                logger.error(
                    "❌ %d denemeden sonra %s atlandı.",
                    config.MAX_RESTARTS_PER_CITY, city_name,
                )
                await asyncio.sleep(config.CITY_CLOSE_WAIT)
