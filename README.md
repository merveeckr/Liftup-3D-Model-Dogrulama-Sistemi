# LIFT UP — Yapay Zeka Destekli 3D Model Doğrulama Sistemi

> **Ankara Yıldırım Beyazıt Üniversitesi** — Elektrik-Elektronik Mühendisliği  
> Sanayi Ortağı: **TUSAŞ** | Program: **TÜBİTAK 2209-B / LIFT UP Bitirme Projesi**

---

## Proje Hakkında

Bu sistem, üretimden çıkan fiziksel bir parçanın dijital referans modeline (CAD) ne kadar uygun olduğunu **gerçek zamanlı olarak** analiz eder. Mesafe sensörü ve döner tabla ile elde edilen nokta bulutu verisi, yapay zeka algoritmaları kullanılarak referans CAD modeli ile karşılaştırılır; tolerans dışı bölgeler ve imalat hataları otomatik olarak tespit edilerek renkli 3D görselleştirme ile operatöre sunulur.

Gerçek sensör donanımı olmadan da çalışır: sistem, referans STL dosyasından kontrollü bir tarama simüle ederek algoritmayı test etmenize olanak tanır.

---

## Ekip

| İsim | Rol |
|------|-----|
| Necla Zencirci | Proje Yürütücüsü |
| Sedef Sarı | 3D Model & CAD |
| Merve Çakır | Yazılım Geliştirme |
| Hatice Süheyla Eser | Algoritma & Test |

**Akademik Danışman:** Hüseyin Canbolat  
**Sanayi Danışmanı:** Kadir Durdu (TUSAŞ)

---

## Sistem Gereksinimleri

- **Python 3.11** (önerilen) veya 3.9+
- İnternet bağlantısı (ilk kurulum için)
- Modern tarayıcı (Chrome, Firefox, Edge)

---

## Kurulum

**1. Depoyu klonlayın veya dosyaları indirin:**
```
Liftup-3D-Model-Dogrulama-Sistemi/
├── BASLAT.bat
├── requirements.txt
├── README.md
├── models/
│   ├── sedefe1.stl
│   └── sedefe2.stl
├── backend/
│   ├── main.py
│   ├── pipeline.py
│   ├── database.py
│   ├── export.py
│   └── report.py
└── frontend/
    └── index.html
```

**2. Gerekli Python paketlerini yükleyin:**
```bash
pip install -r requirements.txt
```

> İlk kurulum birkaç dakika sürebilir (open3d paketi ~70 MB).

---

## Nasıl Çalıştırılır

### Yöntem 1 — Çift Tıkla (Kolay)
`BASLAT.bat` dosyasına çift tıklayın.

> **Not:** `BASLAT.bat` içindeki Python yolu kendi kullanıcı adınıza ve Python sürümünüze göre ayarlanmış olmalıdır.  
> Örnek (Python 3.11): `"C:\Users\KULLANICI_ADI\AppData\Local\Programs\Python\Python311\python.exe" main.py`  
> Doğru yolu bulmak için terminalde `where python` komutunu çalıştırın.

Sistem başladıktan sonra tarayıcıda `http://localhost:8000` adresini açın.

### Yöntem 2 — Terminal
```bash
cd backend
python main.py
```
Ardından tarayıcıda `http://localhost:8000` adresine gidin.

---

## Kullanım Kılavuzu

### 1. Görüntüleme Modunu Seçin

Sol panelin üstündeki üç butona tıklayarak görünümü değiştirin:

| Mod | Gösterilen | Ne İşe Yarar |
|-----|-----------|--------------|
| **Referans** | Yalnızca CAD mesh (mavi, opak) | "Parça tam olarak nasıl olmalı?" |
| **Tarama** | Yalnızca nokta bulutu (ısı haritası) | "Sensör ne ölçtü?" |
| **Karşılaştır** | İkisi birlikte | "Fark nerede?" |

### 2. Parametreleri Ayarlayın

| Parametre | Açıklama | Önerilen Değer |
|-----------|----------|----------------|
| **STL Dosyası** | Referans alınacak CAD modeli | `sedefe1.stl` |
| **Nokta Sayısı** | Tarama yoğunluğu | 6000 – 10000 |
| **Sensör Gürültüsü (σ)** | Sensör ölçüm hassasiyeti (mm) | 0.20 – 0.50 |
| **Hata Bölgesi Sayısı** | Simüle edilecek imalat hatası adedi | 0 – 8 |

### 3. Analizi Başlatın

**"▶ Analizi Başlat"** butonuna tıklayın. Pipeline şu adımları sırayla çalıştırır:

```
STL Yükle → Nokta Örnekle → Gürültü + Hata Ekle
    ↓
ICP Hizalaması (tarama ↔ referans)
    ↓
Point-to-Surface Sapma Hesabı
    ↓
IsolationForest + Eşik Anomali Tespiti
    ↓
3D Görselleştirme + Kalite Raporu
```

Analiz süresi: **8–20 saniye** (nokta sayısına ve hata adedine bağlı).

### 4. Sonuçları Yorumlayın

#### Uyum Halkası
Sol panelde dönen oran göstergesi, uyum puanını gösterir:

| Oran | Renk | Anlam |
|------|------|-------|
| ≥ %95 | Yeşil | Mükemmel |
| %85 – 95 | Sarı | Kabul edilebilir |
| %65 – 85 | Turuncu | Dikkat gerekli |
| < %65 | Kırmızı | Reddedilmeli |

> Uyum puanı = Tolerans içi nokta yüzdesi − Risk ağırlıklı hata cezası  
> Tolerans eşiği: **±0.5 mm** (TUSAŞ havacılık standardı)

#### Kalite Kararı
| Karar | Koşul |
|-------|-------|
| ✓ **KABUL** | Uyum ≥ %90 ve risk Yüksek/Kritik değil |
| ⚠ **KOŞULLU** | Uyum %65 – 90 |
| ✕ **RED** | Uyum < %65 |

#### 3D Viewport Renk Haritası
Nokta bulutu, her noktanın referans yüzeye olan uzaklığına göre renklenir:

```
Mavi → Camgöbeği → Yeşil → Sarı → Kırmızı
 0mm                               > Maks
(tolerans içi)              (tolerans dışı)
```

#### Hata Tipleri ve İşaretçiler

| Simge | Tip | 3D İşaretçi | Renk | Açıklama |
|-------|-----|-------------|------|----------|
| ▲ | Çıkıntı (Bump) | Tel küre | Turuncu | Malzeme fazlası |
| ▼ | Çukur (Hole) | Tel küre | Mor | Malzeme eksiği / göçme |
| ○ | Eksik Bölge (Missing) | Torus halkası | Açık mavi | Tarama verisi yok |

#### Risk Seviyeleri

| Seviye | Renk | Uyum Cezası | Açıklama |
|--------|------|-------------|----------|
| 🟢 **Düşük** | Yeşil | −4% | Küçük sapma, tolerans içi |
| 🟡 **Orta** | Sarı | −9% | Orta sapma, izlenmeli |
| 🟠 **Yüksek** | Turuncu | −15% | Büyük sapma veya geniş bölge |
| 🔴 **Kritik** | Kırmızı | −25% | Çok büyük sapma veya eksik malzeme |

### 5. 3D Görünümde Gezinin

| Hareket | Kontrol |
|---------|---------|
| Döndür | Sol tık sürükle |
| Zoom | Fare tekerleği |
| Kaydır | Sağ tık sürükle |

### 6. Ek Özellikler

- **PDF Rapor:** Analiz tamamlandıktan sonra "⬇ PDF Rapor Kaydet" ile rapor indirin.
- **Analiz Geçmişi:** Sol panelin altında önceki analizler listelenir; üzerine tıklayarak yeniden yüklenebilir.
- **Karşılaştırma:** Geçmiş listesinden iki analiz seçip "Karşılaştır" ile yan yana metrik karşılaştırması yapın.
- **İstatistikler:** Başlık çubuğundaki "📊 İstatistikler" ile tüm analizlerin trend ve dağılım grafiklerini görün.

---

## Pipeline Algoritması

### 1. Tarama Simülasyonu
Gerçek sensör verisi yokken, referans STL yüzeyinden rastgele nokta örneklenir. Ardından:
- **Gaussian gürültü** yüzey normaline dik yönde eklenir (sensör ölçüm hatası simülasyonu)
- **Çıkıntı/çukur** bölgeleri: Gaussian falloff fonksiyonu ile lokal deformasyonlar (normal yönünde ±1.5–4.0 mm)
- **Eksik bölge:** Belirli bir kümedeki noktalar silinerek tarama boşluğu oluşturulur
- Hata merkezleri her zaman orijinal mesh yüzeyinden seçilir (deformasyondan bağımsız)

### 2. ICP Hizalaması
*Iterative Closest Point* algoritması iki aşamalı çalışır:
1. **Kaba hizalama** — Point-to-point, 20 mm tolerans
2. **İnce hizalama** — Point-to-plane, 5 mm tolerans

Hata merkez koordinatları ICP sonrası referans mesh yüzeyine KD-tree ile projektlenir; böylece ICP sapması ne olursa olsun işaretçiler model üzerinde kalır.

### 3. Sapma Hesabı
Her tarama noktası için referans yüzeyine olan mesafe iki yöntemle hesaplanır:
- **Birincil:** Open3D `RaycastingScene` — kesin point-to-mesh imzalı mesafe
- **Yedek:** SciPy `cKDTree` — 80.000 noktalı yoğun örneklem üzerinden yaklaşık mesafe

### 4. Anomali Tespiti (2 Katmanlı, AND mantığı)
- **3-Sigma eşiği:** `eşik = 3 × σ_gürültü + 0.5 mm` — bu değerin üzerindeki noktalar aday
- **IsolationForest:** Uzamsal konum + sapma büyüklüğü özellikleriyle istatistiksel anomali tespiti  
- Her iki koşulun **kesişimi (AND)** final anomali maskesini oluşturur — yanlış pozitif engellenir
- **DBSCAN** ile izole gürültü noktaları filtrelenerek gerçek hata kümeleri ayrıştırılır
- IsolationForest `contamination` parametresi hata sayısına göre otomatik ayarlanır (0 hata → %0.5, 8 hata → %12.5)

### 5. Uyum Puanı ve Risk Hesabı
```
Uyum = (Tolerans içi nokta %) − Σ(risk cezası her hata için)
Tolerans eşiği: ±0.5 mm (sabit, gürültüden bağımsız)
```

Hata riski tipi ve büyüklüğüne göre belirlenir:
- Çıkıntı: < 1.2 mm Düşük → > 3.8 mm Kritik
- Çukur: < 0.8 mm Düşük → > 3.0 mm Kritik
- Eksik bölge: Her zaman en az Yüksek
- Bölge çapı > 7 mm: Risk seviyesini bir üst kademeye taşır

---

## Teknik Yığın

| Katman | Teknoloji |
|--------|-----------|
| Backend API | FastAPI + Uvicorn |
| 3D İşleme | Open3D 0.19 (mesh yükleme, ICP, örnekleme) |
| Uzaklık Hesabı | Open3D RaycastingScene / SciPy cKDTree |
| Anomali Tespiti | Scikit-learn IsolationForest + DBSCAN |
| Veritabanı | SQLite (analiz geçmişi) |
| Raporlama | fpdf2 (PDF), openpyxl (Excel) |
| Frontend | Vue.js 3 (CDN) |
| 3D Görselleştirme | Three.js r128 |
| HTML Etiketler | Three.js CSS2DRenderer |

---

## Proje Dosya Yapısı

```
Liftup-3D-Model-Dogrulama-Sistemi/
│
├── BASLAT.bat              # Tek tıkla başlatma (Python yolu ayarlanmalı)
├── requirements.txt        # Python bağımlılıkları
├── README.md
│
├── models/
│   ├── sedefe1.stl         # Referans CAD modeli
│   └── sedefe2.stl         # İkinci referans model
│
├── backend/
│   ├── main.py             # FastAPI sunucu + tüm API endpoint'leri
│   ├── pipeline.py         # Analiz algoritması (ICP, sapma, anomali, uyum)
│   ├── database.py         # SQLite analiz geçmişi
│   ├── export.py           # Excel dışa aktarma (openpyxl)
│   └── report.py           # PDF rapor üretimi (fpdf2)
│
└── frontend/
    └── index.html          # Web arayüzü (Three.js + Vue.js, tek dosya)
```

---

## API Referansı

| Endpoint | Metot | Açıklama |
|----------|-------|----------|
| `/` | GET | Web arayüzü |
| `/api/models` | GET | Mevcut STL dosyaları |
| `/api/analyze` | POST | Analiz pipeline'ını çalıştır |
| `/api/history` | GET | Analiz geçmişini listele |
| `/api/history/{id}` | GET | Belirli bir analizi yükle |
| `/api/history/{id}` | DELETE | Belirli bir analizi sil |
| `/api/history` | DELETE | Tüm geçmişi temizle |
| `/api/report/{id}` | GET | PDF rapor oluştur ve kaydet |
| `/api/stats` | GET | Geçmiş istatistikleri ve trend |
| `/api/compare` | GET | İki analizi karşılaştır |
| `/api/health` | GET | Sunucu durumu |
| `/models/{dosya.stl}` | GET | STL dosyası servis et |

**`/api/analyze` istek gövdesi:**
```json
{
  "model": "sedefe1.stl",
  "n_points": 8000,
  "noise_std": 0.30,
  "defect_count": 3
}
```

---

## Gelecek Çalışmalar

- [ ] Gerçek mesafe sensörü entegrasyonu (döner tabla + step motor)
- [ ] PCB tasarımı ve mikrodenetleyici senkronizasyonu
- [ ] PointNet / DGCNN tabanlı derin öğrenme hizalaması
- [ ] Gerçek zamanlı video akışı (streaming analiz)

---

*LIFT UP Projesi — Ankara Yıldırım Beyazıt Üniversitesi EEE × TUSAŞ*
