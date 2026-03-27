"""
main.py — Kayseri / Sivas / Tokat Kiralık Konut Scraper
CLI giriş noktası ve orkestratör.

Kullanım:
  python main.py                   # Tüm şehirleri sıfırdan çek
  python main.py --resume          # Checkpoint'ten devam et
  python main.py --city kayseri    # Sadece bir şehri çek
  python main.py -v                # Verbose (debug) log

Çalışırken konsol komutları:
  skip    → Mevcut şehri atla, sonrakine geç
  next    → Mevcut bracket'ı atla, sonrakine geç
  stop    → Scraper'ı düzgünce durdur
  status  → Mevcut durumu yazdır
  help    → Komut listesini göster
"""

import argparse
import asyncio
import logging
import queue
import sys
import threading

import config
from scraper import (
    SkipCitySignal,
    StopSignal,
    clear_checkpoint,
    load_checkpoint,
    save_checkpoint,
    scrape_city,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

HELP_TEXT = """
╔══════════════════════════════════════════╗
║         Konsol Komutları                 ║
╠══════════════════════════════════════════╣
║  skip   → Mevcut şehri atla             ║
║  next   → Mevcut bracket'ı atla         ║
║  stop   → Scraper'ı durdur              ║
║  status → Mevcut durumu göster          ║
║  help   → Bu listeyi göster             ║
╚══════════════════════════════════════════╝
"""


# ============================================================
# KONSOL MÜDAHALE SİSTEMİ
# ============================================================

# Mevcut durumu paylaşmak için thread-safe yapı
_current_status: dict = {"city": "-", "bracket": "-", "page": "-"}
_status_lock = threading.Lock()


def update_status(city: str = None, bracket: str = None, page: str = None) -> None:
    with _status_lock:
        if city    is not None: _current_status["city"]    = city
        if bracket is not None: _current_status["bracket"] = bracket
        if page    is not None: _current_status["page"]    = page


def print_status() -> None:
    with _status_lock:
        s = _current_status
    print(f"\n📊 Durum: Şehir={s['city']} | Bracket={s['bracket']} | Sayfa={s['page']}\n")


def console_listener(cmd_queue: queue.Queue, stop_event: threading.Event) -> None:
    """
    Arka planda stdin'i dinler, komutları kuyruğa ekler.

    Scraper sona erince stop_event set edilir ve thread durur.
    """
    while not stop_event.is_set():
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            break

        cmd = line.strip().lower()
        if not cmd:
            continue

        if cmd == "help":
            print(HELP_TEXT)
        elif cmd == "status":
            print_status()
        elif cmd in ("skip", "next", "stop"):
            cmd_queue.put(cmd)
            logger.info("⚡ Komut kuyruğa eklendi: '%s'", cmd)
        else:
            logger.warning("❓ Bilinmeyen komut: '%s' — 'help' yazın.", cmd)


# ============================================================
# ANA ÇALIŞTIRICI
# ============================================================

async def run(args: argparse.Namespace) -> None:
    checkpoint = load_checkpoint() if args.resume else {}

    # --city filtresi
    cities_to_scrape = config.CITIES
    if args.city:
        target = args.city.lower()
        cities_to_scrape = [c for c in config.CITIES if c["url_slug"] == target]
        if not cities_to_scrape:
            valid = ", ".join(c["url_slug"] for c in config.CITIES)
            logger.error("Şehir '%s' bulunamadı. Geçerli: %s", args.city, valid)
            sys.exit(1)

    # Taze çalışmada bugünkü CSV'leri temizle
    if not args.resume:
        for city_cfg in cities_to_scrape:
            csv_path = config.get_city_csv_path(city_cfg["name"])
            import os
            if os.path.exists(csv_path):
                os.remove(csv_path)
                logger.info("Eski CSV temizlendi: %s", csv_path)

    # Checkpoint'teki şehirden başla
    start_city = checkpoint.get("city")
    start_idx  = 0
    if start_city and args.resume:
        for i, c in enumerate(cities_to_scrape):
            if c["url_slug"] == start_city:
                start_idx = i
                break

    # Konsol müdahale sistemi
    cmd_queue   = queue.Queue()
    stop_event  = threading.Event()
    console_thread = threading.Thread(
        target=console_listener,
        args=(cmd_queue, stop_event),
        daemon=True,    # Ana thread bitince otomatik ölür
        name="ConsoleListener",
    )
    console_thread.start()

    print(HELP_TEXT)
    logger.info(
        "🚀 %d şehir için scrape başlıyor (%d checkpoint tamamlandı)...",
        len(cities_to_scrape) - start_idx,
        len(checkpoint.get("done_cities", [])),
    )

    grand_total = 0

    try:
        for city_cfg in cities_to_scrape[start_idx:]:
            update_status(city=city_cfg["name"], bracket="-", page="-")
            try:
                await scrape_city(
                    city=city_cfg,
                    checkpoint=checkpoint,
                    cmd_queue=cmd_queue,
                )
                grand_total += 0   # scrape_city kendi logluyor
                checkpoint = {}    # Sonraki şehir checkpoint sıfırla

            except SkipCitySignal:
                logger.warning("⏭️ %s atlandı.", city_cfg["name"])
                checkpoint = {}
                continue

            except StopSignal:
                logger.warning("🛑 Stop komutu alındı — scraper durduruluyor.")
                break

    except KeyboardInterrupt:
        logger.warning("⛔ Ctrl+C algılandı — scraper durduruluyor.")

    finally:
        stop_event.set()    # Konsol thread'ini durdur

    clear_checkpoint()
    logger.info("\n✅ Tüm şehirler tamamlandı.")


# ============================================================
# CLI
# ============================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kayseri-sivas-tokat-scraper",
        description="Kayseri, Sivas, Tokat kiralık konut ilanlarını çeker.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Checkpoint'ten devam et.",
    )
    parser.add_argument(
        "--city",
        type=str,
        default=None,
        metavar="ŞEHİR",
        help="Sadece bir şehri çek (kayseri / sivas / tokat).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Debug log.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
