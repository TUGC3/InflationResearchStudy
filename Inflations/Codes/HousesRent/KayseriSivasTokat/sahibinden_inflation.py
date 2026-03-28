import logging
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup (Görseldeki yapınıza göre) ──────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent.parent  # .../Inflations/Codes
_INFLATIONS_DIR = _CODES_DIR.parent  # .../Inflations
_PROJECT_ROOT = _INFLATIONS_DIR.parent  # .../inflationstudymirror

# Okunacak verilerin ana klasörü
RAW_DATA_DIR = _PROJECT_ROOT / "Datas" / "HousesRent"

# Çıktıların kaydedileceği ana klasör
INFLATION_OUT_DIR_BASE = _INFLATIONS_DIR / "Datas" / "HousesRent"

logger = logging.getLogger(__name__)

# İşlenecek şehirler listesi
CITIES = ["Kayseri", "Sivas", "Tokat"]

# ── TUIK 2026 TÜFE Main-Group Weights ─────────────────────────────────────────
TUIK_WEIGHTS = {
    "01": {"name": "Gıda ve alkolsüz içecekler", "weight": 24.44},
    "02": {"name": "Alkollü içecekler, tütün ve tütün ürünleri", "weight": 2.75},
    "03": {"name": "Giyim ve ayakkabı", "weight": 7.90},
    "04": {"name": "Konut, su, elektrik, gaz ve diğer yakıtlar", "weight": 11.40},
    "05": {"name": "Mobilya, ev aletleri ve ev bakım hizmetleri", "weight": 7.92},
    "06": {"name": "Sağlık", "weight": 2.79},
    "07": {"name": "Ulaştırma", "weight": 16.62},
    "08": {"name": "Bilgi ve iletişim", "weight": 3.10},
    "09": {"name": "Eğlence, dinlence, spor ve kültür", "weight": 4.34},
    "10": {"name": "Eğitim", "weight": 2.02},
    "11": {"name": "Lokantalar ve konaklama hizmetleri", "weight": 11.13},
    "12": {"name": "Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler", "weight": 4.49},
    "13": {"name": "Sigorta ve finansal hizmetler", "weight": 1.07},
}


def normalised_weights(present_codes):
    """Return a dict {code: normalised_weight} for only the TUIK groups in *present_codes*."""
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}


# ── Core Functions ────────────────────────────────────────────────────────────
def _load_and_group(city, date_str):
    """Belirtilen şehir ve tarih için CSV dosyasını okur, fiyatları temizler ve gruplar."""
    fpath = RAW_DATA_DIR / city / f"{date_str}.csv"

    if not fpath.exists():
        return None

    try:
        df = pd.read_csv(fpath, usecols=['District', 'Rooms', 'Price'])

        # Fiyatları vektörize temizleme
        df['Price_Num'] = (
            df['Price']
            .astype(str)
            .str.replace(' TL', '', regex=False)
            .str.replace('.', '', regex=False)
        )
        df['Price_Num'] = pd.to_numeric(df['Price_Num'], errors='coerce')

        # Sadece o şehre ait ilçeler ve odalar üzerinden gruplama
        grouped = df.groupby(['District', 'Rooms'])['Price_Num'].median().reset_index()
        grouped.rename(columns={'Price_Num': 'median_price'}, inplace=True)
        return grouped
    except Exception as e:
        logger.error(f"Failed to read {fpath}: {e}")
        return None


def _compute_metrics(df_current, df_past):
    """İki tarih arasındaki enflasyon metriklerini hesaplar."""
    df_current = df_current.copy()
    df_current['tuik_category'] = "04"

    past_subset = df_past[['District', 'Rooms', 'median_price']].rename(columns={'median_price': 'past_price'})
    merged = df_current.merge(past_subset, on=['District', 'Rooms'], how='left')

    # 1) Segment bazlı enflasyon
    merged['basic_inflation'] = ((merged['median_price'] - merged['past_price']) / merged['past_price']) * 100

    # 2) Ortalama enflasyon
    avg_inflation = merged['basic_inflation'].mean()

    # 3) Sepet geneli enflasyon endeksi
    valid_mask = merged['median_price'].notna() & merged['past_price'].notna()
    sum_current = merged.loc[valid_mask, 'median_price'].sum()
    sum_past = merged.loc[valid_mask, 'past_price'].sum()
    basic_inflation_index = ((sum_current - sum_past) / sum_past) * 100 if sum_past else None

    # 4) TUIK ağırlıklı ortalama
    cat_avg = merged.groupby('tuik_category')['basic_inflation'].mean()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)

    valid_terms = [cat_avg[c] * norm_w[c] / 100.0 for c in norm_w if c in cat_avg.index and pd.notna(cat_avg[c])]
    tuik_weighted = sum(valid_terms) if valid_terms else None

    merged.drop(columns=['past_price'], errors='ignore', inplace=True)
    return merged, basic_inflation_index, avg_inflation, tuik_weighted


def calculate_inflation(city, target_date=None, compare_date=None):
    """Verilen şehir için enflasyon hesaplamalarını yürütür ve kaydeder."""
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_and_group(city, today_str)
    if df_today is None:
        logger.warning(f"Skipping {city} – no target data found for {today_str}.")
        return

    # Her şehir için çıktı klasörünü oluştur
    city_out_dir = INFLATION_OUT_DIR_BASE / city
    city_out_dir.mkdir(parents=True, exist_ok=True)

    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {f"{days}d": (base_date - timedelta(days=days)).strftime("%Y-%m-%d") for days in [1, 7, 15, 30]}

    summary_row = {'date': today_str}
    detail_base = df_today.copy()
    detail_base['tuik_category'] = "04"

    for label, past_str in intervals.items():
        df_past = _load_and_group(city, past_str)

        if df_past is None:
            logger.info(f"[{city}] Skipping interval {label} – no data for {past_str}.")
            detail_base[f'basic_inflation_{label}'] = None
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'tuik_weighted_{label}'] = None
            continue

        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[['District', 'Rooms', 'basic_inflation']].rename(
                columns={'basic_inflation': f'basic_inflation_{label}'}
            ),
            on=['District', 'Rooms'], how='left'
        )

        summary_row[f'avg_inflation_{label}'] = avg_inf
        summary_row[f'tuik_weighted_{label}'] = tuik_w

    # ── Detaylı veriyi kaydet (Günlük) ───────────────────────────────────────
    detail_file = city_out_dir / f"{city}_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding='utf-8')
    logger.info(f"[{city}] Saved detailed inflation data to: {detail_file}")

    # ── Özet veriyi kaydet veya güncelle (Zaman Serisi) ─────────────────────
    summary_file = city_out_dir / f"{city}_inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            # Eğer o güne ait hesaplama daha önce yapıldıysa, eskisini silip güncel olanı yazarız
            df_existing = df_existing[df_existing['date'] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding='utf-8')
            logger.info(f"[{city}] Updated inflation summary in: {summary_file}")
        else:
            df_summary.to_csv(summary_file, index=False, encoding='utf-8')
            logger.info(f"[{city}] Created new inflation summary in: {summary_file}")
    except Exception as e:
        logger.error(f"[{city}] Failed to write summary file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-City rent inflation calculator")
    parser.add_argument("--date", help="Target (current) date in YYYY-MM-DD format", default=None)
    parser.add_argument("--compare", help="Comparison (past) date in YYYY-MM-DD format", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Tüm şehirler için tek tek döngüye girip hesaplama yapıyoruz
    for current_city in CITIES:
        logger.info(f"--- Processing city: {current_city} ---")
        calculate_inflation(current_city, args.date, args.compare)
