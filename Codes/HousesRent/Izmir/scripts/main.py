"""
main.py — Izmir Rent Scraper (GitHub Actions Uyumlu Versiyon)
=========================================================

Bu versiyon GitHub sunucu dakikalarını (action minutes) korumak için
özel olarak tasarlanmıştır. Her çalıştırıldığında sadece 1 fiyat aralığını
çeker, kaydeder ve sunucuyu kapatır.
"""

import argparse
import json
import logging
import os
import time
import random

import config
from scraper import setup_driver, scrape_range, save_incremental

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Checkpoint (Kaldığı Yeri Kaydetme) İşlemleri ──────────────────────────────

def _load_checkpoint() -> dict:
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_ranges": []}

def _save_checkpoint(data: dict) -> None:
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Ana Çalıştırma Fonksiyonu ─────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    # GitHub Actions için varsayılan olarak HER ZAMAN kaldığı yerden devam eder.
    # Sadece --restart parametresi verilirse veriler sıfırlanır.
    checkpoint = _load_checkpoint() if not args.restart else {"done_ranges": []}

    done_ranges: set[tuple[int, int]] = {
        tuple(r) for r in checkpoint["done_ranges"]
    }

    if args.restart and os.path.exists(config.CSV_OUTPUT_FILE):
        os.remove(config.CSV_OUTPUT_FILE)
        logger.info("Eski CSV dosyası temizlendi: %s", config.CSV_OUTPUT_FILE)
        _save_checkpoint({"done_ranges": []})
        done_ranges = set()

    def mark_done(min_p: int, max_p: int) -> None:
        done_ranges.add((min_p, max_p))
        checkpoint["done_ranges"] = [list(r) for r in done_ranges]
        _save_checkpoint(checkpoint)

    logger.info(
        "GitHub Actions için Izmir verisi çekme işlemi başlıyor... "
        "(Toplam %d aralık, %d tanesi zaten çekilmiş)",
        len(config.SEED_RANGES),
        len(done_ranges),
    )

    total_saved = 0

    try:
        for seed_min, seed_max in config.SEED_RANGES:
            # Eğer bu aralık zaten "done_ranges" içindeyse (çekilmişse), atla ve diğerine geç.
            if (seed_min, seed_max) in done_ranges:
                continue

            logger.info(f"\n--- YENİ TARAYICI OTURUMU BAŞLATILIYOR ({seed_min} - {seed_max} TL) ---")
            driver = setup_driver()

            try:
                saved = scrape_range(
                    driver=driver,
                    min_price=seed_min,
                    max_price=seed_max,
                    done_ranges=done_ranges,
                    save_fn=save_incremental,
                    save_checkpoint_fn=mark_done,
                    indent=0,
                )
                total_saved += saved

            except Exception as e:
                logger.error(f"Hata oluştu: {e}")

            finally:
                # O aralığın işi bitince tarayıcıyı mutlaka kapatıyoruz
                driver.quit()

            # GITHUB ACTIONS KORUMASI: Sadece 1 aralık çekip programı bitir!
            logger.info("✅ 1 fiyat aralığı başarıyla çekildi.")
            logger.info("🛑 GitHub Sunucu süresini (dakika kotasını) tüketmemek için program sonlandırılıyor.")
            logger.info("Bir sonraki tetiklenmede sıradaki aralıktan devam edecektir.")
            break

    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından manuel olarak durduruldu.")

    logger.info("\nİşlem Tamamlandı! ✓ Bu seansta kaydedilen yeni ilan sayısı: %d", total_saved)
    logger.info("Çıktı Dosyası → %s", config.CSV_OUTPUT_FILE)


# ── Komut Satırı (CLI) Ayarları ───────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="izmir-scraper",
        description="Scrape house rental listings for Izmir from sahibinden.com (GitHub Actions Optimized).",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Günün tüm kayıtlarını ve CSV dosyasını silip en baştan (0 TL'den) başlar.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Detaylı (debug) hata ayıklama loglarını gösterir.",
    )
    return parser

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    run(args)

if __name__ == "__main__":
    main()