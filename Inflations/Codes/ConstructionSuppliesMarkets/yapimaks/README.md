Yapımaks Enflasyon Hesaplayıcı Rehberi

Bu araç, Yapımaks mağazasından çekilen günlük fiyat verilerini (CSV dosyalarını) birbiriyle kıyaslar. Sonuç olarak sana mağazadaki ürünlerin 1, 7, 15 ve 30 günlük süreler içinde ne kadar zamlandığını söyler.
# 1. Bu Kod Ne Yapar?

  Sepet Enflasyonu: Mağazadaki tüm ürünleri bir sepete koyduğumuzu hayal et. Bu sepetin toplam fiyatı geçen haftaya göre yüzde kaç arttı?

  Ortalama Enflasyon: Ürünlerin tek tek değişim oranlarını bulur ve bunların ortalamasını alır.

  Ürün Bazlı Takip: Hangi ürünün fiyatı sabit kalmış, hangisi uçmuş? Bunları tek tek listeler.

# 2. Çalışması İçin Ne Lazım?

Bilgisayarındaki şu klasör yolunda günlük verilerinin olması gerekir:
InflationItems/Datas/ConstructionSuppliesMarkets/Yapimaks/

Dosya isimleri şu formatta olmalı: yapimaks_YYYY-MM-DD.csv (Örnek: yapimaks_2026-03-24.csv)
# 3. Nasıl Kullanılır?

Terminali (veya PyCharm terminalini) aç ve şu komutu yaz:
```
    python inflation.py --date 2026-03-24
```
(Eğer --date yazmazsan, kod otomatik olarak bugünün tarihini arar.)
# 4. Sonuçlar Nerede?

Hesaplama bittiğinde Inflations/Datas/ConstructionSuppliesMarkets/Yapimaks/ klasörüne şu iki dosya gelir:

  yapimaks_inflation_Tarih.csv: Bu dosyada her ürünün satırında 1, 7, 15 ve 30 günlük enflasyon oranlarını görürsün.

  inflation_summary.csv: Bu dosya genel özet tablosudur. Her gün çalıştırdığında altına yeni bir satır ekler; böylece mağazanın genel gidişatını tek bir yerden takip edebilirsin.

# 5. Önemli Notlar

  Fiyatlar: Verilerindeki virgüllü fiyatlar (276,00) kod tarafından otomatik olarak matematiksel işleme uygun hale getirilir.

  Eşleştirme: Kod, ürünleri product_id numaralarına bakarak tanır. Eğer bir ürün eski dosyada yoksa, onun için enflasyon hesaplanamaz.
