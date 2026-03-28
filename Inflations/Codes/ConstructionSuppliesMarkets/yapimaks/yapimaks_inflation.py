import logging
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# ── Dosya Yolları (Kendi klasör yapına göre ayarlı) ──
DATA_DIR = Path(r"C:\Users\arhan\PycharmProjects\inflationstudymirror\InflationItems\Datas\ConstructionSuppliesMarkets\Yapimaks")
OUT_DIR = Path(r"C:\Users\arhan\PycharmProjects\inflationstudymirror\Inflations\Datas\ConstructionSuppliesMarkets\Yapimaks")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def _load_csv(date_str):
    fpath = DATA_DIR / f"yapimaks_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"Veri bulunamadı: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath)
        # "276,00" formatındaki fiyatları float'a çevirme
        df['price'] = df['price'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
        return df
    except Exception as e:
        logger.error(f"Okuma hatası {fpath}: {e}")
        return None

def _compute_metrics(df_current, df_past):
    df_current = df_current.copy()
    past_subset = df_past[['product_id', 'price']].rename(columns={'price': 'past_price'})
    merged = df_current.merge(past_subset, on='product_id', how='left')

    # 1. Ürün Bazlı Enflasyon (Yüzdelik değişim)
    merged['basic_inflation'] = ((merged['price'] - merged['past_price']) / merged['past_price']) * 100
    merged['basic_inflation'] = merged['basic_inflation'].replace([float('inf'), float('-inf')], pd.NA)

    # 2. Ortalama Enflasyon (Tüm ürünlerin değişim ortalaması)
    avg_inflation = merged['basic_inflation'].mean()

    # 3. Sepet Enflasyonu (Toplam güncel fiyat / Toplam geçmiş fiyat)
    valid = merged.dropna(subset=['price', 'past_price'])
    sum_current = valid['price'].sum()
    sum_past = valid['past_price'].sum()
    basket_inflation = ((sum_current - sum_past) / sum_past) * 100 if sum_past else None

    merged = merged.drop(columns=['past_price'], errors='ignore')
    return merged, basket_inflation, avg_inflation

def calculate_inflation(target_date=None):
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
        
    today_str = base_date.strftime("%Y-%m-%d")
    df_today = _load_csv(today_str)
    
    if df_today is None:
        logger.warning(f"Hesaplama yapılamıyor - {today_str} verisi yok.")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    intervals = {f"{d}d": (base_date - timedelta(days=d)).strftime("%Y-%m-%d") for d in [1, 7, 15, 30]}

    summary_row = {'date': today_str}
    detail_base = df_today.copy()

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)

        if df_past is None:
            detail_base[f'inflation_{label}'] = None
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'basket_inflation_{label}'] = None
            continue

        merged, basket_inf, avg_inf = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[['product_id', 'basic_inflation']].rename(columns={'basic_inflation': f'inflation_{label}'}),
            on='product_id', how='left'
        )

        summary_row[f'avg_inflation_{label}'] = avg_inf
        summary_row[f'basket_inflation_{label}'] = basket_inf

    # Detaylı veriyi kaydet
    detail_file = OUT_DIR / f"yapimaks_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding='utf-8')
    logger.info(f"Detaylı rapor kaydedildi: {detail_file}")

    # Özet veriyi güncelle
    summary_file = OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing['date'] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding='utf-8')
        else:
            df_summary.to_csv(summary_file, index=False, encoding='utf-8')
        logger.info(f"Özet rapor güncellendi: {summary_file}")
    except Exception as e:
        logger.error(f"Özet dosyası yazılamadı: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Yapimaks Saf Enflasyon Hesaplayıcı")
    parser.add_argument("--date", help="Hedef tarih (YYYY-MM-DD)", default=None)
    args = parser.parse_args()
    
    calculate_inflation(args.date)
