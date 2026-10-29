# GridTwin

Trafo bazında GES ve elektrikli araç kapasite planlaması için dijital şebeke ikizi — masaüstü uygulaması.

Atakum pilot bölgesinde dağıtım trafolarının çatı GES'i, elektrikli araç şarjı ve ısı pompası yüklerini
kaldırıp kaldıramayacağını gösteren aracın masaüstü sürümü. Windows'ta **.exe**, Mac'te **.app** olarak çalışır.

| Klasör / dosya | İçerik |
|---|---|
| `arac/gridtwin.html` | Aracın kendisi (harita, senaryolar, grafikler, PDF rapor) |
| `app.py` | Aracı kendi penceresinde açan masaüstü uygulaması (pywebview); PDF'i "Farklı kaydet" ile kaydeder |
| `python_model/` | Hesapların Python sürümü (simülasyon, gerilim, doğrusal programlama, ekonomi) |
| `.github/workflows/derle.yml` | GitHub'ın .exe ve .app dosyalarını otomatik üretmesi için tarif |

## Uygulamayı GitHub'da derleme (bir kez yapılır)

1. **github.com**'da ücretsiz hesap aç.
2. Sağ üstte **+ → New repository**. Ad: `gridtwin`. Public ya da Private seç. Başka bir şey işaretleme, **Create repository**.
3. Açılan sayfada **uploading an existing file** bağlantısına tıkla. Bu klasördeki `app.py`, `requirements.txt`,
   `README.md`, `arac` ve `python_model` klasörlerini sürükleyip bırak. Altta **Commit changes**.
4. Derleme tarifini ekle (Mac'te `.github` klasörü gizli olduğu için elle ekliyoruz):
   **Add file → Create new file**. Dosya adı kutusuna tam olarak `.github/workflows/derle.yml` yaz.
   `KOPYALA_derle.yml` dosyasını bir metin düzenleyiciyle aç, içeriğin tamamını kopyalayıp yapıştır. **Commit changes**.
5. Üstteki **Actions** sekmesine geç. "Uygulamayı derle" çalışmaya başlar (5–10 dakika). Yeşil tik çıkınca üzerine tıkla.
6. Sayfanın altındaki **Artifacts** bölümünden indir:
   - `GridTwin-windows` → içinde **GridTwin.exe**
   - `GridTwin-mac` → içinde **GridTwin.app** (zip)

Aracı güncellemek için `arac/gridtwin.html` dosyasını yenisiyle değiştir (dosyaya tıkla → kalem simgesi ya da
**Add file → Upload files**); GitHub uygulamaları otomatik olarak yeniden üretir.

## Açarken çıkan uyarılar

Uygulama imzasız olduğu için ilk açılışta işletim sistemi uyarır; bu normaldir.
- **Windows:** "Windows bilgisayarınızı korudu" → **Ek bilgi** → **Yine de çalıştır**.
  Pencere boş açılırsa Microsoft Edge WebView2 Runtime'ı kur (Windows 10/11'de genelde yüklüdür).
- **Mac:** zip'i aç, **GridTwin**'e sağ tıkla → **Aç** → **Aç**. "Hasarlı" uyarısı çıkarsa Terminal'de:
  `xattr -cr ~/Downloads/GridTwin.app`

## Bilgisayarında derlemeden çalıştırmak

```bash
pip install -r requirements.txt
python app.py
```

## Geliştirme notu

Problem tanımı, pilot bölge, senaryolar ve yöntem seçimleri proje sahibine aittir; kodlamada yapay zekâ
destekli geliştirme araçları kullanılmıştır.
