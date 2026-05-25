# LIFT UP — Geliştirme Değişiklik Raporu
**Tarih:** 23 Mayıs 2026  
**Proje:** LIFT UP — Yapay Zeka Destekli 3D Model Doğrulama Sistemi  
**Üniversite:** Ankara Yıldırım Beyazıt Üniversitesi × TUSAŞ

---

## 1. BASLAT.bat Python Yolu Düzeltmesi

**Dosya:** `BASLAT.bat`

**Sorun:** Bilgisayarda iki farklı Python sürümü yüklüydü. `BASLAT.bat` PATH'teki Python 3.14'ü çalıştırıyordu; ancak proje paketleri (FastAPI, Open3D vb.) Python 3.10'a kuruluydu.

**Çözüm:** `python main.py` komutu, Python 3.10'un tam yolu ile değiştirildi.

```
Eski: python main.py
Yeni: "C:\Users\eserh\AppData\Local\Programs\Python\Python310\python.exe" main.py
```

---

## 2. Veri Kaydetme ve Geçmiş Paneli

### 2a. Yeni Dosya: `backend/database.py`

SQLite veritabanı işlemleri için sıfırdan yazıldı. İçerdiği fonksiyonlar:

| Fonksiyon | Görev |
|-----------|-------|
| `init_db()` | `history.db` dosyasını oluşturur, tablo yoksa yaratır |
| `save_analysis()` | Her analiz sonrası sonuçları veritabanına kaydeder |
| `list_analyses()` | Geçmiş analizleri listeler (en yeni önce) |
| `get_analysis()` | Belirli bir analizi tam veriyle döndürür |
| `delete_analysis()` | Tek kayıt siler |
| `clear_all()` | Tüm geçmişi siler |

**Veritabanı konumu:** Proje kök dizininde `history.db`

**Kaydedilen alanlar:** id, timestamp, model, n_points, noise_std, defect_count, conformance, verdict, overall_risk, rms, max_deviation, result_json (tam analiz verisi)

### 2b. Güncellenen Dosya: `backend/main.py`

- Sunucu başlangıcında `init_db()` otomatik çağrısı eklendi
- `/api/analyze` endpoint'i; analiz bitince `save_analysis()` çağırır ve yanıtta `analysis_id` döner
- Yeni endpoint'ler eklendi:

| Endpoint | Metot | Görev |
|----------|-------|-------|
| `/api/history` | GET | Geçmişi listele (max 100 kayıt) |
| `/api/history/{id}` | GET | Tek kaydı tam veriyle getir |
| `/api/history/{id}` | DELETE | Tek kaydı sil |
| `/api/history` | DELETE | Tüm geçmişi temizle |

### 2c. Güncellenen Dosya: `frontend/index.html`

Sidebar'ın altına **"Analiz Geçmişi"** paneli eklendi:
- Sayfa açılınca geçmiş otomatik yüklenir ve **varsayılan açık** gelir
- Her kayıtta: model adı, tarih/saat, uyum %, karar pill, risk badge, nokta/gürültü/hata detayları
- **Tıklayarak** geçmiş analizi sahneye yükleme (3D görünüm + metrikler güncellenir)
- **✕** butonu ile tek kayıt silme
- **"Geçmişi Temizle"** butonu ile tüm geçmişi silme
- Analiz tamamlanınca geçmiş listesi otomatik güncellenir

---

## 3. Sidebar Scrollbar Düzeltmesi

**Dosya:** `frontend/index.html`

**Sorun:** Sidebar içeriği uzadığında (analiz sonuçları + geçmiş listesi) kaydırma çalışmıyordu. Flexbox container'ın yüksekliği kısıtlanmadığı için `overflow-y: scroll` tetiklenmiyordu.

**Çözüm:**
```css
aside {
  height: calc(100vh - 50px);   /* Kesin yükseklik kısıtı */
  overflow-y: scroll;
  scrollbar-width: thin;
  scrollbar-color: #444c56 var(--bg);
}
aside::-webkit-scrollbar { width: 6px; }
aside::-webkit-scrollbar-thumb { background: #444c56; border-radius: 3px; }
```
`display: flex; flex-direction: column` sidebar'dan kaldırıldı (gereksizdi ve scroll'u engelliyordu).

---

## 4. Algoritma İyileştirmeleri

**Dosya:** `backend/pipeline.py` — tamamen yeniden yazıldı

### 4a. Simülasyon Gerçekliği (Gürültü Modeli)

**Eski:** Gürültü rastgele yönde uygulanıyordu.  
**Yeni:** Gürültü **yüzey normaline dik** yönde uygulanır — gerçek LiDAR/mesafe sensörü davranışını simüle eder.

```python
# Eski
pts += np.random.normal(0, noise_std, pts.shape)

# Yeni
pcd = mesh.sample_points_uniformly(n_points, use_triangle_normal=True)
normals = np.asarray(pcd.normals).copy()
noise_mag = np.random.normal(0, noise_std, len(pts))
pts += noise_mag[:, np.newaxis] * normals
```

Hata enjeksiyonu da güncellendi: bump ve hole, artık rastgele yön yerine **lokal yüzey normali yönünde** uygulanır.

### 4b. İki Aşamalı ICP Hizalaması

**Eski:** Tek aşamalı Point-to-Point ICP (60 iterasyon, 15mm tolerans)  
**Yeni:** Coarse + Fine iki aşamalı ICP

| Aşama | Yöntem | Tolerans | İterasyon |
|-------|--------|----------|-----------|
| Kaba (Coarse) | Point-to-Point | 20 mm | 50 |
| İnce (Fine) | **Point-to-Plane** | 5 mm | 150 |

Fine aşamada referans nokta bulutu normal tahmini yapılır (`KDTreeSearchParamHybrid`). Point-to-Plane ICP, yüzey yönünü de dikkate aldığından çok daha hassas hizalama sağlar.

### 4c. Kesin Point-to-Mesh Sapma Hesabı

**Eski:** 80.000 noktalı yoğun örnekleme + KD-tree yaklaşımı (yaklaşık mesafe)  
**Yeni:** Open3D `RaycastingScene` ile **gerçek üçgen yüzeyine kesin imzalı mesafe**

```python
mesh_t = o3d.t.geometry.TriangleMesh.from_legacy(ref_mesh)
scene  = o3d.t.geometry.RaycastingScene()
scene.add_triangles(mesh_t)
query  = o3d.core.Tensor(scan_pts.astype(np.float32), dtype=o3d.core.float32)
dists  = np.abs(scene.compute_signed_distance(query).numpy())
```

Başarısız olursa KD-tree'ye otomatik geri düşüş (`fallback`) uygulanır.

### 4d. DBSCAN Tabanlı Anomali Filtreleme

**Eski:** 3-sigma eşiği + IsolationForest (2 katman)  
**Yeni:** 3-sigma + IsolationForest + **DBSCAN kümeleme** (3 katman)

DBSCAN ile izole anomali noktaları (gürültü) filtrelenir, gerçek hata bölgeleri kümelenir. Model boyutuna uyarlanmış adaptif `eps` değeri kullanılır:

```python
bbox_diag = float(np.linalg.norm(scan_pts.max(axis=0) - scan_pts.min(axis=0)))
eps = max(bbox_diag * 0.025, 2.0)
```

Yeni istatistik alanı eklendi: `anomaly_clusters` (DBSCAN küme sayısı)

---

## 5. PDF Rapor Çıktısı

### 5a. Yeni Dosya: `backend/report.py`

`matplotlib` kütüphanesi ile iki sayfalık koyu temalı PDF raporu üretir.

**Sayfa 1 — Analiz Özeti:**
- Header şeridi (LIFT UP logosu + AYBÜ/TUSAŞ)
- Analiz bilgi kutusu (model, tarih, parametreler)
- Uyum halkası (pasta grafik)
- Karar ve Risk kutuları (renkli)
- 8 metrik kartı (RMS, Maks, Ort. Sapma, ICP RMSE, Anomali, Küme, Tolerans, Nokta Sayısı)
- Hata bölgeleri tablosu (tip, büyüklük, yarıçap, risk)

**Sayfa 2 — Sapma Dağılımı:**
- Renk kodlu histogram (yeşil = tolerans içi, kırmızı = tolerans dışı)
- Tolerans sınırı çizgisi
- İstatistik özeti (ort, RMS, maks)
- Algoritma bilgisi kutusu

**Kullanılan kütüphane:** `fpdf2` (kurulum sırasında eklendi), sonra `matplotlib` ile değiştirildi.  
**Font:** DejaVu Sans (Türkçe karakter desteğiyle birlikte gelir)

### 5b. Güncellenen: `backend/main.py`

```
GET /api/report/{analysis_id}
```
PDF'i üretip `LIFTUP PDF` klasörüne kaydeder, dosya adı ve yolunu JSON olarak döner.

### 5c. Güncellenen: `frontend/index.html`

- "Analizi Başlat" butonunun altına **"⬇ PDF Rapor Kaydet"** butonu eklendi (analiz bitmeden gizli)
- Geçmiş panelindeki her kayıtta **⬇** ikonu eklendi (o kaydın PDF'ini kaydeder)
- PDF kaydedilince yeşil toast bildirimi çıkar: `PDF kaydedildi: liftup_analiz_5.pdf`

### 5d. Yeni: `LIFTUP PDF` Klasörü

Masaüstünde `C:\Users\eserh\Desktop\LIFTUP PDF\` klasörü otomatik oluşturulur. Tüm çıktılar buraya kaydedilir.

---

## 6. Karşılaştırmalı Analiz

### 6a. Güncellenen: `backend/main.py`

```
GET /api/compare?id1={id1}&id2={id2}
```

İki analizin tüm metriklerini karşılaştırır ve döndürür:
- Her metrik için delta değeri (`b - a`)
- Her metrikte kazanan (`a`, `b` veya `tie`)
- Genel kazanan (kazanılan metrik sayısına göre)
- Skor (`score.a`, `score.b`)

Karşılaştırılan metrikler: `conformance`, `rms`, `max_deviation`, `mean_deviation`, `anomaly_count`, `icp_rmse`

### 6b. Güncellenen: `frontend/index.html`

**Seçim mekanizması:**
- Geçmiş panelinde her kaydın yanına **⊕** butonu eklendi
- 2 kayıt seçilince mavi seçim barı çıkar → **"Karşılaştır"** butonu aktif
- 3. bir kayıt seçilirse ilki otomatik çıkarılır

**Karşılaştırma modalı:**
- İki sütunlu yan yana görünüm (Analiz A | Analiz B)
- Model adı, tarih, genel kazanan rozeti
- Tüm metrikler listesi; kazanan metrik yeşil ✓ ile işaretlenir, kaybeden kırmızı
- Altta skor kartları: her analizin kaç metrikte kazandığı

---

## 7. Excel Dışa Aktarma (Arka Plan)

### 7a. Yeni Dosya: `backend/export.py`

`openpyxl` kütüphanesi ile koyu temalı, çok sayfalı Excel dosyası üretir.

**Sayfalar:**
1. **Analiz Özeti** — tüm istatistikler, parametreler, karar (renkli hücreler)
2. **Hata Bölgeleri** — defect tablosu (tip, büyüklük, yarıçap, risk, koordinat)
3. **Sapma Verileri** — ilk 2000 noktanın X/Y/Z koordinatı, sapma değeri, OK/ANOMALİ durumu

`generate_history_excel()` fonksiyonu tüm geçmişi tek sayfada özetler.

### 7b. Güncellenen: `backend/main.py`

```
GET /api/excel/{analysis_id}     → Tek analiz Excel'i
GET /api/excel-history           → Tüm geçmiş Excel'i
```

**Not:** Excel butonları arayüzden kaldırıldı. Endpoint'ler arka planda aktif, ihtiyaç halinde `http://localhost:8000/api/excel/{id}` adresinden kullanılabilir.

---

## 8. Analiz İstatistikleri Paneli

### 8a. Güncellenen: `backend/main.py`

```
GET /api/stats
```

Tüm geçmiş üzerinden aggregate istatistikler döndürür:

| Alan | Açıklama |
|------|----------|
| `count` | Toplam analiz sayısı |
| `avg_conformance` | Ortalama uyum oranı |
| `avg_rms` | Ortalama RMS sapma |
| `max/min_conformance` | En yüksek/düşük uyum |
| `best` / `worst` | En iyi ve en kötü analiz (id, model, uyum, tarih) |
| `verdicts` | KABUL/KOŞULLU/RED dağılımı |
| `risks` | Düşük/Orta/Yüksek/Kritik dağılımı |
| `models` | Her modelin kaç kez analiz edildiği |
| `trend` | Son 20 analizin uyum değerleri (grafik verisi) |

### 8b. Güncellenen: `frontend/index.html`

Header çubuğuna **"📊 İstatistikler"** butonu eklendi. Tıklayınca modal açılır:

- **4 özet kart:** Toplam analiz · Ortalama uyum (min/maks) · Ortalama RMS · Kabul oranı %
- **Trend grafiği (SVG):** Son 20 analizin uyum çizgisi, ≥%90 yeşil bölge, %70–90 sarı bölge. Noktalar: yeşil=KABUL, sarı=KOŞULLU, kırmızı=RED
- **Karar dağılımı:** KABUL / KOŞULLU / RED renkli doluluk çubukları
- **Risk dağılımı:** Düşük / Orta / Yüksek / Kritik renkli doluluk çubukları
- **En iyi & En kötü analiz:** Yeşil/kırmızı çerçeveli kartlar (model, id, tarih, uyum %)
- **Model kullanımı:** Birden fazla STL varsa her modelin kullanım çubuğu

---

## 9. Genel `requirements.txt` Güncellemesi

```
fpdf2>=2.7.0    # PDF üretimi
matplotlib>=3.7.0  # PDF grafikleri
openpyxl        # Excel üretimi (arka plan)
```

---

## Dosya Değişiklik Özeti

| Dosya | Durum | Açıklama |
|-------|-------|----------|
| `BASLAT.bat` | Güncellendi | Python 3.10 tam yolu |
| `requirements.txt` | Güncellendi | fpdf2, matplotlib, openpyxl eklendi |
| `backend/database.py` | **Yeni** | SQLite geçmiş yönetimi |
| `backend/report.py` | **Yeni** | matplotlib PDF raporu |
| `backend/export.py` | **Yeni** | openpyxl Excel dışa aktarma |
| `backend/pipeline.py` | Yeniden yazıldı | 4 algoritma iyileştirmesi |
| `backend/main.py` | Güncellendi | 8 yeni API endpoint |
| `frontend/index.html` | Güncellendi | Geçmiş, PDF, karşılaştırma, istatistik panelleri |

---

## API Endpoint Tam Listesi (v1.1)

| Endpoint | Metot | Açıklama |
|----------|-------|----------|
| `/` | GET | Web arayüzü |
| `/api/models` | GET | STL dosyalarını listele |
| `/api/analyze` | POST | Analiz pipeline'ını çalıştır + kaydet |
| `/api/history` | GET | Geçmiş listesi |
| `/api/history/{id}` | GET | Tek kayıt (tam veri) |
| `/api/history/{id}` | DELETE | Tek kaydı sil |
| `/api/history` | DELETE | Tüm geçmişi temizle |
| `/api/stats` | GET | İstatistik özeti |
| `/api/compare?id1=&id2=` | GET | İki analizi karşılaştır |
| `/api/report/{id}` | GET | PDF oluştur → LIFTUP PDF klasörüne kaydet |
| `/api/excel/{id}` | GET | Excel oluştur → LIFTUP PDF klasörüne kaydet |
| `/api/excel-history` | GET | Tüm geçmişi Excel'e aktar |
| `/api/health` | GET | Sunucu durumu |
| `/models/{dosya.stl}` | GET | STL dosyası sun |

---

*LIFT UP Projesi — Ankara Yıldırım Beyazıt Üniversitesi EEE × TUSAŞ*
