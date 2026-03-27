"""
gurmar_inflation.py — Gurmar Daily Inflation Calculator CLI
"""

import argparse
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# gurmar_tuik_config.py'nin aynı dizinde olduğunu varsayıyoruz
try:
    from gurmar_tuik_config import gurmar_category_to_tuik as migros_category_to_tuik, normalised_weights
except ImportError:
    print("HATA: gurmar_tuik_config.py dosyası bulunamadı! Lütfen aynı dizinde olduğundan emin ol.")
    sys.exit(1)

logger = logging.getLogger(__name__)


def load_and_clean_csv(file_path):
    """Verilen dosya yolundan CSV'yi okur ve Gürmar formatını temizler."""
    if not file_path.exists():
        logger.info(f"Veri dosyası bulunamadı: {file_path}")
        return None
    try:
        df = pd.read_csv(file_path)

        # Gürmar kolonlarını standart altyapıya uygun hale getiriyoruz
        df = df.rename(columns={
            'kategori': 'category',
            'product_name': 'id',  # ID olmadığı için ürün ismini ID olarak kullanıyoruz
            'product_price': 'shown_price'
        })

        # Fiyatlardaki virgülü noktaya çevir ve float yap (örn: "64,95" -> 64.95)
        df['shown_price'] = df['shown_price'].astype(str).str.replace('"', '', regex=False).str.replace(',', '.',
                                                                                                        regex=False)
        df['shown_price'] = pd.to_numeric(df['shown_price'], errors='coerce')

        return df
    except Exception as e:
        logger.error(f"Dosya okunamadı {file_path}: {e}")
        return None


def _compute_metrics(df_current, df_past):
    df_current = df_current.copy()
    df_current['tuik_category'] = df_current['category'].apply(migros_category_to_tuik)

    past_subset = df_past[['id', 'shown_price']].rename(columns={'shown_price': 'past_price'})
    merged = df_current.merge(past_subset, on='id', how='left')

    merged['basic_inflation'] = ((merged['shown_price'] - merged['past_price']) / merged['past_price']) * 100
    merged['basic_inflation'] = merged['basic_inflation'].replace([float('inf'), float('-inf')], pd.NA)

    avg_inflation = merged['basic_inflation'].mean()

    valid = merged.dropna(subset=['shown_price', 'past_price'])
    sum_current = valid['shown_price'].sum()
    sum_past = valid['past_price'].sum()
    basic_inflation_index = ((sum_current - sum_past) / sum_past) * 100 if sum_past else None

    cat_avg = merged.groupby('tuik_category')['basic_inflation'].mean()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)
    tuik_weighted = sum(cat_avg[c] * norm_w[c] / 100.0 for c in norm_w if c in cat_avg.index and pd.notna(cat_avg[c]))

    merged = merged.drop(columns=['past_price'], errors='ignore')
    return merged, basic_inflation_index, avg_inflation, tuik_weighted


def calculate_inflation(input_file, output_dir=None, compare_file=None):
    input_path = Path(input_file).resolve()

    if not input_path.exists():
        logger.error(f"Girdi dosyası bulunamadı: {input_path}")
        return

    # Dosya isminden YYYY-MM-DD formatındaki tarihi çek
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', input_path.name)
    if date_match:
        today_str = date_match.group(1)
        base_date = datetime.strptime(today_str, "%Y-%m-%d")
    else:
        logger.error("Girdi dosyasının isminde 'YYYY-MM-DD' formatında bir tarih bulunamadı!")
        return

    # Çıktı dizinini ayarla
    out_dir_path = Path(output_dir).resolve() if output_dir else Path.cwd()
    out_dir_path.mkdir(parents=True, exist_ok=True)

    df_today = load_and_clean_csv(input_path)
    if df_today is None:
        logger.warning(f"Enflasyon hesaplanamıyor – {today_str} için veri yok veya bozuk.")
        return

    # Geçmiş dosyaların aranacağı klasör (input dosyasının bulunduğu klasör)
    data_dir = input_path.parent

    if compare_file:
        comp_path = Path(compare_file).resolve()
        comp_date_match = re.search(r'(\d{4}-\d{2}-\d{2})', comp_path.name)
        comp_label = comp_date_match.group(1) if comp_date_match else "custom"
        intervals = {comp_label: comp_path}
    else:
        intervals = {}
        # 1, 7, 15, 30 günlük geçmiş dosyalarını aynı formatta arayacağız
        prefix = input_path.name.split(today_str)[0]  # Örn: "gurmar_"
        suffix = input_path.name.split(today_str)[1]  # Örn: ".csv"

        for days in [1, 7, 15, 30]:
            past_date_str = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            past_file_name = f"{prefix}{past_date_str}{suffix}"
            intervals[f"{days}d"] = data_dir / past_file_name

    summary_row = {'date': today_str}
    detail_base = df_today.copy()
    detail_base['tuik_category'] = detail_base['category'].apply(migros_category_to_tuik)

    for label, past_path in intervals.items():
        df_past = load_and_clean_csv(past_path)

        if df_past is None:
            logger.info(f"Atlanıyor: {label} aralığı için veri bulunamadı ({past_path.name}).")
            detail_base[f'basic_inflation_{label}'] = None
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'tuik_weighted_{label}'] = None
            continue

        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[['id', 'basic_inflation']].rename(columns={'basic_inflation': f'basic_inflation_{label}'}),
            on='id', how='left'
        )

        summary_row[f'avg_inflation_{label}'] = avg_inf
        summary_row[f'tuik_weighted_{label}'] = tuik_w

    # Detaylı veriyi kaydet
    detail_file = out_dir_path / f"gurmar_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding='utf-8')
    logger.info(f"Detaylı enflasyon verisi kaydedildi: {detail_file}")

    # Summary dosyasını güncelle
    summary_file = out_dir_path / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing['date'] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding='utf-8')
            logger.info(f"Özet (summary) verisi güncellendi: {summary_file}")
        else:
            df_summary.to_csv(summary_file, index=False, encoding='utf-8')
            logger.info(f"Özet (summary) dosyası oluşturuldu: {summary_file}")
    except Exception as e:
        logger.error(f"Summary dosyası yazılamadı: {e}")


if __name__ == "__main__":
    epilog_text = """
NASIL KULLANILIR:
-----------------
1. Standart Kullanım (Otomatik olarak 1, 7, 15 ve 30 günlük geçmişi arar):
   python gurmar_inflation.py -i gurmar_2026-02-24.csv

2. Çıktıları Farklı Bir Klasöre Kaydetmek İçin (-o):
   python gurmar_inflation.py -i veri/gurmar_2026-02-24.csv -o sonuclar/

3. Sadece Belirli İki Dosyayı Karşılaştırmak İçin (-c):
   python gurmar_inflation.py -i gurmar_2026-02-24.csv -c gurmar_2026-02-10.csv
"""

    parser = argparse.ArgumentParser(
        description="Gürmar Enflasyon Hesaplayıcı CLI Aracı\nGürmar fiyat verilerini alıp TUIK ağırlıklarına göre enflasyon hesaplar.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=epilog_text
    )

    parser.add_argument("-i", "--input",
                        help="Bugünün fiyatlarını içeren CSV dosyasının yolu (Örn: gurmar_2026-02-24.csv)")
    parser.add_argument("-o", "--out-dir", help="Çıktıların kaydedileceği klasör (Varsayılan: bulunduğun dizin)",
                        default=None)
    parser.add_argument("-c", "--compare",
                        help="(Opsiyonel) Özel bir karşılaştırma için geçmiş tarihli CSV dosyasının yolu.",
                        default=None)

    # Eğer hiçbir argüman verilmeden çalıştırılırsa, direkt yardım menüsünü göster ve çık
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    # Eğer input argümanı verilmediyse uyar (argparse'da required yapmadık ki menü temiz gözüksün)
    if not args.input:
        print("\nHATA: Lütfen işlenecek CSV dosyasını '-i' parametresi ile belirtin.\n")
        parser.print_help(sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    calculate_inflation(args.input, args.out_dir, args.compare)
