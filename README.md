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

- Python 3.9 veya üzeri
- İnternet bağlantısı (ilk kurulum için)
- Modern tarayıcı (Chrome, Firefox, Edge)

---

## Kurulum

**1. Depoyu klonlayın veya dosyaları indirin:**
```
lift-up/
├── BASLAT.bat
├── requirements.txt
├── sedefe1.stl
├── sedefe2.stl
├── backend/
│   ├── main.py
│   └── pipeline.py
└── frontend/
    └── index.html
```

**2. Gerekli Python paketlerini yükleyin:**
```bash
pip install -r requirements.txt
```

> İlk kurulum birkaç dakika sürebilir (open3d paketi ~500 MB).

---

## Nasıl Çalıştırılır

### Yöntem 1 — Çift Tıkla (Kolay)
`BASLAT.bat` dosyasına çift tıklayın. Sistem otomatik başlar, tarayıcıda `http://localhost:8000` adresini açın.

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
| **Hata Bölgesi Sayısı** | Simüle edilecek imalat hatası adedi | 2 – 5 |

### 3. Analizi Başlatın

**"▶ Analizi Başlat"** butonuna tıklayın. Pipeline şu adımları sırayla çalıştırır:

```
STL Yükle → Nokta Örnekle → Gürültü + Hata Ekle
    ↓
ICP Hizalaması (tarama ↔ referans)
    ↓
Point-to-Surface Sapma Hesabı
    ↓
IsolationForest Anomali Tespiti
    ↓
3D Görselleştirme + Kalite Raporu
```

Analiz süresi: **8–15 saniye** (nokta sayısına bağlı).

### 4. Sonuçları Yorumlayın

#### Uyum Halkası
Sol panelde dönen oran göstergesi, tolerans içindeki noktaların yüzdesini gösterir:

| Oran | Renk | Anlam |
|------|------|-------|
| ≥ %95 | Yeşil | Mükemmel |
| %85 – 95 | Sarı | Kabul edilebilir |
| %70 – 85 | Turuncu | Dikkat gerekli |
| < %70 | Kırmızı | Reddedilmeli |

#### Kalite Kararı
| Karar | Koşul |
|-------|-------|
| ✓ **KABUL** | Uyum ≥ %90 ve risk Kritik değil |
| ⚠ **KOŞULLU** | Uyum %70 – 90 |
| ✕ **RED** | Uyum < %70 |

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

| Seviye | Renk | Açıklama |
|--------|------|----------|
| 🟢 **Düşük** | Yeşil | Küçük sapma, tolerans içi |
| 🟡 **Orta** | Sarı | Orta sapma, izlenmeli |
| 🟠 **Yüksek** | Turuncu | Büyük sapma veya geniş bölge |
| 🔴 **Kritik** | Kırmızı | Çok büyük sapma veya eksik malzeme |

### 5. 3D Görünümde Gezinin

| Hareket | Kontrol |
|---------|---------|
| Döndür | Sol tık sürükle |
| Zoom | Fare tekerleği |
| Kaydır | Sağ tık sürükle |

---

## Pipeline Algoritması

### 1. Tarama Simülasyonu
Gerçek sensör verisi yokken, referans STL yüzeyinden rastgele nokta örneklenir. Ardından:
- **Gaussian gürültü** eklenir (sensör ölçüm hatası simülasyonu)
- **Çıkıntı/çukur** bölgeleri: Gaussian bump fonksiyonu ile lokal deformasyonlar
- **Eksik bölge**: Belirli bir kümedeki noktalar silinerek tarama boşluğu oluşturulur

### 2. ICP Hizalaması
*Iterative Closest Point* algoritması ile tarama nokta bulutu, referans CAD modeline hizalanır. 4×4 dönüşüm matrisi hem noktaları hem de hata merkez koordinatlarını dönüştürür.

### 3. Sapma Hesabı
Her tarama noktası için referans yüzeyine olan en kısa mesafe hesaplanır (80.000 noktalı yoğun referans örnekleme + scipy cKDTree).

### 4. Anomali Tespiti (2 Katmanlı)
- **3-Sigma eşiği:** `tolerans = 3 × σ_gürültü + 0.3 mm` — bu değerin üzerindeki noktalar anomali
- **IsolationForest:** Uzamsal konum + sapma büyüklüğü özellikelriyle istatistiksel anomali tespiti  
Her iki yöntemin birleşimi (OR) final anomali maskesini oluşturur.

### 5. Risk Hesabı
Hata tipi ve büyüklüğüne göre 4 seviyeli risk ataması:
- Çıkıntı: < 1.2 mm Düşük → > 3.8 mm Kritik
- Çukur: < 0.8 mm Düşük → > 3.0 mm Kritik
- Eksik bölge: Her zaman en az Yüksek
- Alan çapı > 7 mm: Risk seviyesini bir üst kademeye taşır

---

## Teknik Yığın

| Katman | Teknoloji |
|--------|-----------|
| Backend API | FastAPI + Uvicorn |
| 3D İşleme | Open3D (mesh yükleme, ICP, örnekleme) |
| Uzaklık Hesabı | SciPy cKDTree |
| Anomali Tespiti | Scikit-learn IsolationForest |
| Frontend | Vue.js 3 (CDN) |
| 3D Görselleştirme | Three.js r128 |
| HTML Etiketler | Three.js CSS2DRenderer |

---

## Proje Dosya Yapısı

```
lift-up/
│
├── BASLAT.bat              # Tek tıkla başlatma
├── requirements.txt        # Python bağımlılıkları
│
├── sedefe1.stl             # Referans CAD modeli (24.412 üçgen)
├── sedefe2.stl             # İkinci referans model (96.290 üçgen)
│
├── backend/
│   ├── main.py             # FastAPI sunucu + API endpoint'leri
│   └── pipeline.py         # Tüm analiz algoritması
│
└── frontend/
    └── index.html          # Web arayüzü (Three.js + Vue.js)
```

---

## API Referansı

| Endpoint | Metot | Açıklama |
|----------|-------|----------|
| `/` | GET | Web arayüzü |
| `/api/models` | GET | Mevcut STL dosyaları |
| `/api/analyze` | POST | Analiz pipeline'ını çalıştır |
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
- [ ] PDF rapor çıktısı

---

*LIFT UP Projesi — Ankara Yıldırım Beyazıt Üniversitesi EEE × TUSAŞ*
