import os
import glob
import pandas as pd


def reorder_csv_columns():
    # Scriptin çalıştığı klasördeki tüm .csv dosyalarını bulur
    csv_files = glob.glob("*.csv")

    if not csv_files:
        print("Klasörde hiç CSV dosyası bulunamadı!")
        return

    for file_path in csv_files:
        try:
            # CSV dosyasını oku
            df = pd.read_csv(file_path)
            columns = list(df.columns)

            # name ve price sütunlarının varlığını kontrol et
            if 'Product Name' not in columns or 'Price' not in columns:
                print(f"Atlandı: '{file_path}' (name veya price sütunu eksik)")
                continue

            # Diğer sütunları ayıkla (name ve price hariç)
            other_columns = [col for col in columns if col not in ['Product Name', 'Price']]

            # Yeni sütun sıralamasını oluştur: [name, price, diğerleri...]
            new_column_order = ['Product Name', 'Price'] + other_columns

            # DataFrame'i yeni sıralamaya göre yeniden indeksle
            df = df[new_column_order]

            # Üzerine yaz (indeks numarasını eklememek için index=False)
            df.to_csv(file_path, index=False)
            print(f"Başarıyla düzenlendi: {file_path}")

        except Exception as e:
            print(f"Hata oluştu ({file_path}): {e}")


if __name__ == "__main__":
    reorder_csv_columns()