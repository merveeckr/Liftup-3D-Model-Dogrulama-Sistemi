import numpy as np
import open3d as o3d
from scipy.spatial import cKDTree
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN


_RISK_SCORE = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
_RISK_LABEL = {'low': 'Düşük', 'medium': 'Orta', 'high': 'Yüksek', 'critical': 'Kritik'}

_THRESHOLDS = {
    'bump':    [(1.2, 'low'), (2.5, 'medium'), (3.8, 'high'),  (float('inf'), 'critical')],
    'hole':    [(0.8, 'low'), (1.8, 'medium'), (3.0, 'high'),  (float('inf'), 'critical')],
    'missing': [(0.0, 'high'), (float('inf'), 'critical')],
}


def calculate_risk(defect: dict) -> dict:
    dtype     = defect['type']
    magnitude = defect['magnitude']
    radius    = defect['radius']

    thresholds = _THRESHOLDS.get(dtype, _THRESHOLDS['bump'])
    level = 'critical'
    for limit, lv in thresholds:
        if magnitude <= limit:
            level = lv
            break

    if radius > 7.0 and _RISK_SCORE[level] < 4:
        levels = ['low', 'medium', 'high', 'critical']
        level  = levels[_RISK_SCORE[level]]

    return {'level': level, 'label': _RISK_LABEL[level], 'score': _RISK_SCORE[level]}


def load_mesh(stl_path: str) -> o3d.geometry.TriangleMesh:
    mesh = o3d.io.read_triangle_mesh(stl_path)
    mesh.compute_vertex_normals()
    # Otomatik birim tespiti: bounding box köşegeni < 1 ise koordinatlar
    # metre cinsinden export edilmiş demektir → 1000x büyüterek mm'ye çevir
    verts = np.asarray(mesh.vertices)
    diag = np.linalg.norm(verts.max(axis=0) - verts.min(axis=0))
    if diag < 1.0 and diag > 1e-9:
        mesh.vertices = o3d.utility.Vector3dVector(verts * 1000.0)
        mesh.compute_vertex_normals()
    return mesh


def simulate_scan(
    mesh: o3d.geometry.TriangleMesh,
    n_points: int = 8000,
    noise_std: float = 0.3,
    defect_count: int = 3,
    seed: int = None,
) -> tuple:
    """
    Yüzey normaline dik gürültü ekleyerek gerçek LiDAR/mesafe sensörü
    davranışını simüle eder. Hata enjeksiyonu: bump, hole, missing.
    """
    if seed is not None:
        np.random.seed(seed)

    # Yüzey normallerini de al (use_triangle_normal=True)
    pcd = mesh.sample_points_uniformly(n_points, use_triangle_normal=True)
    pts     = np.asarray(pcd.points).copy()
    normals = np.asarray(pcd.normals).copy()

    # Normaller yoksa tahmin et
    if normals.shape[0] == 0 or not np.any(normals):
        pcd.estimate_normals()
        normals = np.asarray(pcd.normals).copy()

    # Orijinal mesh pozisyonlarını sakla — defekt merkezi seçimi için
    pts_original = pts.copy()

    keep = np.ones(len(pts), dtype=bool)

    # Gürültüyü yüzey normali yönünde uygula (gerçek sensör modeli)
    noise_mag = np.random.normal(0, noise_std, len(pts))
    pts += noise_mag[:, np.newaxis] * normals

    defect_types   = ['bump', 'hole', 'missing']
    defect_regions = []

    # Model boyutuna orantılı defekt yarıçapı — herhangi bir ölçekte çalışır
    bbox_diag = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0)))
    r_min = bbox_diag * 0.03   # bbox köşegeninin %3'ü
    r_max = bbox_diag * 0.08   # bbox köşegeninin %8'i

    for i in range(defect_count):
        dtype = defect_types[i % len(defect_types)]

        center_idx = np.random.randint(0, len(pts_original))
        center = pts_original[center_idx].copy()
        radius = np.random.uniform(r_min, r_max)
        dists  = np.linalg.norm(pts_original - center, axis=1)
        mask   = (dists < radius) & keep

        if not np.any(mask):
            continue

        if dtype == 'bump':
            magnitude = np.random.uniform(1.5, 4.0)
            # Normal yönünde çıkıntı (daha gerçekçi)
            local_normals = normals[mask]
            falloff = np.exp(-dists[mask] ** 2 / (2 * (radius / 3) ** 2))
            pts[mask] += local_normals * (magnitude * falloff)[:, np.newaxis]

        elif dtype == 'hole':
            magnitude = np.random.uniform(1.5, 3.5)
            local_normals = normals[mask]
            falloff = np.exp(-dists[mask] ** 2 / (2 * (radius / 3) ** 2))
            # Normal'in tersine çukur
            pts[mask] -= local_normals * (magnitude * falloff)[:, np.newaxis]
            magnitude = -magnitude  # işaret için

        elif dtype == 'missing':
            keep[mask] = False
            magnitude = 0.0

        defect_regions.append({
            "center":    center.tolist(),
            "radius":    float(radius),
            "magnitude": float(abs(magnitude)),
            "type":      dtype,
        })

    pts = pts[keep]
    pcd.points = o3d.utility.Vector3dVector(pts)
    return pcd, defect_regions


def icp_align(
    scan_pcd: o3d.geometry.PointCloud,
    ref_mesh: o3d.geometry.TriangleMesh,
) -> tuple:
    """
    Centroid ön hizalaması + iki aşamalı ICP:
    0. Centroid hizalaması — iki modeli ortak merkeze taşı
    1. Kaba hizalama — Point-to-point, geniş tolerans
    2. İnce hizalama — Point-to-plane, dar tolerans (daha doğru)
    """
    # ── Ölçek normalizasyonu ───────────────────────────────────────
    # Eğer iki model farklı birimde/ölçekte ise (örn. biri mm biri m)
    # ICP hiç hizalayamaz. Bounding box köşegenleri eşitlenerek
    # scan, referansın ölçeğine getirilir.
    ref_pts_arr  = np.asarray(ref_mesh.vertices)
    scan_pts_arr = np.asarray(scan_pcd.points)
    ref_diag  = np.linalg.norm(ref_pts_arr.max(axis=0)  - ref_pts_arr.min(axis=0))
    scan_diag = np.linalg.norm(scan_pts_arr.max(axis=0) - scan_pts_arr.min(axis=0))
    scale_factor = 1.0
    if ref_diag > 1e-6 and scan_diag > 1e-6:
        ratio = ref_diag / scan_diag
        if ratio > 1.5 or ratio < 0.667:   # %50'den fazla fark varsa ölçekle
            scale_factor = ratio
            scan_pcd.points = o3d.utility.Vector3dVector(scan_pts_arr * scale_factor)

    # ── Centroid ön hizalaması ─────────────────────────────────────
    # ICP'nin 20 mm toleransla başlayabilmesi için scan'ı referansın
    # merkezine yakın bir konuma taşı.
    ref_center  = np.asarray(ref_mesh.vertices).mean(axis=0)
    scan_center = np.asarray(scan_pcd.points).mean(axis=0)
    T_pre = np.eye(4)
    T_pre[:3, 3] = ref_center - scan_center
    scan_pcd.transform(T_pre)

    # ── Kaba hizalama ──────────────────────────────────────────────
    ref_coarse = ref_mesh.sample_points_poisson_disk(10000)
    result_coarse = o3d.pipelines.registration.registration_icp(
        scan_pcd,
        ref_coarse,
        max_correspondence_distance=20.0,
        init=np.eye(4),
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(),
        criteria=o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50),
    )

    # ── İnce hizalama (Point-to-Plane) ────────────────────────────
    ref_fine = ref_mesh.sample_points_poisson_disk(30000)
    ref_fine.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=5.0, max_nn=30)
    )
    result_fine = o3d.pipelines.registration.registration_icp(
        scan_pcd,
        ref_fine,
        max_correspondence_distance=5.0,
        init=result_coarse.transformation,
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPlane(),
        criteria=o3d.pipelines.registration.ICPConvergenceCriteria(
            max_iteration=150, relative_fitness=1e-7, relative_rmse=1e-7
        ),
    )

    scan_pcd.transform(result_fine.transformation)
    # Tam dönüşüm: ince ICP ∘ kaba pre-align (simülasyon modunda defect
    # merkezlerini dönüştürmek için gerekli)
    T_combined = result_fine.transformation @ T_pre
    return float(result_fine.inlier_rmse), T_combined


def compute_deviation(
    scan_pcd: o3d.geometry.PointCloud,
    ref_mesh: o3d.geometry.TriangleMesh,
) -> tuple:
    """
    Nokta-yüzey gerçek mesafesi.
    Önce Open3D RaycastingScene (kesin üçgen mesafesi) denenir;
    başarısız olursa KD-tree yaklaşımına düşülür.
    """
    scan_pts = np.asarray(scan_pcd.points)

    try:
        mesh_t  = o3d.t.geometry.TriangleMesh.from_legacy(ref_mesh)
        scene   = o3d.t.geometry.RaycastingScene()
        scene.add_triangles(mesh_t)
        query   = o3d.core.Tensor(scan_pts.astype(np.float32), dtype=o3d.core.float32)
        dists   = np.abs(scene.compute_signed_distance(query).numpy())
        method  = "point-to-mesh (exact)"
    except Exception:
        ref_dense = ref_mesh.sample_points_uniformly(80000)
        ref_pts   = np.asarray(ref_dense.points)
        tree      = cKDTree(ref_pts)
        dists, _  = tree.query(scan_pts, k=1)
        method    = "point-to-point (KD-tree)"

    return dists, method


def detect_anomalies(
    scan_pts: np.ndarray,
    distances: np.ndarray,
    noise_std: float,
    defect_count: int = 0,
    contamination: float = None,
) -> tuple:
    """
    Üç katmanlı anomali tespiti:
    1. Tolerans eşiği (3-sigma) — temel filtre
    2. IsolationForest (uzamsal + sapma özellikleri)
    3. DBSCAN kümeleme — izole gürültü noktalarını filtreler
    """
    threshold         = noise_std * 3 + 0.5
    threshold_anomaly = distances > threshold

    if contamination is None:
        # Simülasyon modu: defekt sayısına göre adaptif
        contamination = float(np.clip(defect_count * 0.015 + 0.005, 0.005, 0.15))

    features = np.column_stack([scan_pts, distances])
    clf = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
        n_jobs=-1,
    )
    iso_anomaly = clf.fit_predict(features) == -1

    # AND: her iki koşul da sağlanmalı — yanlış pozitifi önler.
    # Sadece eşik aşan VE uzamsal olarak izole olan noktalar anomali.
    combined = threshold_anomaly & iso_anomaly

    # DBSCAN: anomali noktalarını kümele, izole noktaları (gürültü) ele
    n_clusters = 0
    if np.sum(combined) > 10:
        anom_pts = scan_pts[combined]

        # Model boyutuna uyarlanmış eps
        bbox_diag = float(np.linalg.norm(scan_pts.max(axis=0) - scan_pts.min(axis=0)))
        eps = max(bbox_diag * 0.025, 2.0)

        db = DBSCAN(eps=eps, min_samples=5, n_jobs=-1).fit(anom_pts)
        labels = db.labels_

        # Label -1 = gürültü noktası → anomali maskesinden çıkar
        noise_in_anom = labels == -1
        anom_idx = np.where(combined)[0]
        combined[anom_idx[noise_in_anom]] = False

        n_clusters = int(len(set(labels[labels >= 0])))
    elif np.any(combined):
        n_clusters = 1

    return combined, n_clusters


def distances_to_colors(distances: np.ndarray) -> np.ndarray:
    """Blue→Cyan→Green→Yellow→Red renk haritası (98. yüzdelik = tam kırmızı)."""
    vmax = np.percentile(distances, 98)
    if vmax < 1e-9:
        vmax = 1.0
    t   = np.clip(distances / vmax, 0.0, 1.0)
    seg = t * 4.0

    colors = np.zeros((len(t), 3), dtype=np.float32)
    for i, s in enumerate(seg):
        if s < 1.0:
            colors[i] = [0.0, s, 1.0]
        elif s < 2.0:
            colors[i] = [0.0, 1.0, 2.0 - s]
        elif s < 3.0:
            colors[i] = [s - 2.0, 1.0, 0.0]
        else:
            colors[i] = [1.0, 4.0 - s, 0.0]
    return colors


def _transform_point(T: np.ndarray, pt: list) -> list:
    h = np.array([pt[0], pt[1], pt[2], 1.0])
    return (T @ h)[:3].tolist()


def run_pipeline_real_scan(
    ref_stl_path: str,
    scan_stl_path: str,
    n_points: int = 8000,
) -> dict:
    """
    Gerçek LiDAR tarama modu — simülasyon yok.
    ref_stl_path  : Orijinal/ideal CAD (referans dikdörtgen kutu)
    scan_stl_path : Gerçek tarama mesh'i (örn. lidarmesh1.stl)
    """
    ref_mesh  = load_mesh(ref_stl_path)
    scan_mesh = load_mesh(scan_stl_path)

    # Tarama mesh'ini nokta bulutuna dönüştür (uniform örnekleme)
    scan_pcd = scan_mesh.sample_points_uniformly(n_points, use_triangle_normal=True)

    icp_rmse, T = icp_align(scan_pcd, ref_mesh)

    distances, deviation_method = compute_deviation(scan_pcd, ref_mesh)

    scan_pts = np.asarray(scan_pcd.points)

    # Mesh-to-mesh karşılaştırma: sensör gürültüsü yok → eşik = 0.5 mm (tolerans)
    # Contamination: tolerans dışındaki nokta oranından adaptif hesapla
    noise_std_est = 0.0
    frac_above = float(np.sum(distances > 0.5) / len(distances))
    adaptive_contamination = float(np.clip(frac_above, 0.01, 0.40))
    anomalies, n_clusters = detect_anomalies(
        scan_pts, distances, noise_std_est, contamination=adaptive_contamination
    )
    colors = distances_to_colors(distances)

    # Anomali noktalarını DBSCAN ile kümelere ayırarak defekt bölgesi oluştur
    defect_regions = []
    if np.any(anomalies):
        anom_pts   = scan_pts[anomalies]
        anom_dists = distances[anomalies]

        bbox_diag = float(np.linalg.norm(scan_pts.max(axis=0) - scan_pts.min(axis=0)))
        eps = max(bbox_diag * 0.03, 2.0)

        db     = DBSCAN(eps=eps, min_samples=5, n_jobs=-1).fit(anom_pts)
        labels = db.labels_

        for cid in sorted(set(labels[labels >= 0])):
            mask         = labels == cid
            cluster_pts  = anom_pts[mask]
            cluster_dist = anom_dists[mask]

            center    = cluster_pts.mean(axis=0)
            radius    = float(np.linalg.norm(cluster_pts - center, axis=1).max())
            magnitude = float(cluster_dist.mean())
            dtype     = 'bump' if magnitude > 1.0 else 'hole'

            defect = {
                'center':    center.tolist(),
                'radius':    radius,
                'magnitude': magnitude,
                'type':      dtype,
            }
            defect['risk'] = calculate_risk(defect)
            defect_regions.append(defect)

    _CONF_PENALTY = {'low': 4, 'medium': 9, 'high': 15, 'critical': 25}
    penalty = sum(_CONF_PENALTY.get(d['risk']['level'], 9) for d in defect_regions)

    tolerance        = 0.5
    base_conformance = float(np.sum(distances < tolerance) / len(distances) * 100)
    conformance      = float(max(0.0, min(100.0, base_conformance - penalty)))

    if defect_regions:
        max_score    = max(d['risk']['score'] for d in defect_regions)
        overall_risk = {v: k for k, v in _RISK_SCORE.items()}[max_score]
    else:
        overall_risk = 'low'

    if conformance >= 90 and overall_risk not in ('critical', 'high'):
        verdict = 'accept'
    elif conformance >= 65:
        verdict = 'conditional'
    else:
        verdict = 'reject'

    point_defect_types = [None] * len(scan_pts)
    for defect in defect_regions:
        c  = np.array(defect['center'])
        r  = defect['radius']
        d2 = np.linalg.norm(scan_pts - c, axis=1)
        for i in np.where(d2 < r)[0]:
            if point_defect_types[i] is None:
                point_defect_types[i] = defect['type']

    rms       = float(np.sqrt(np.mean(distances ** 2)))
    hausdorff = float(np.max(distances))
    mean_dev  = float(np.mean(distances))

    return {
        "points":             scan_pts.tolist(),
        "colors":             colors.tolist(),
        "distances":          distances.tolist(),
        "anomalies":          anomalies.tolist(),
        "point_defect_types": point_defect_types,
        "defect_regions":     defect_regions,
        "mode":               "real_scan",
        "stats": {
            "rms":              round(rms, 4),
            "max_deviation":    round(hausdorff, 4),
            "mean_deviation":   round(mean_dev, 4),
            "icp_rmse":         round(icp_rmse, 4),
            "anomaly_count":    int(np.sum(anomalies)),
            "anomaly_clusters": n_clusters,
            "total_points":     int(len(scan_pts)),
            "defect_count":     len(defect_regions),
            "conformance":      round(conformance, 2),
            "tolerance_mm":     round(tolerance, 3),
            "overall_risk":     overall_risk,
            "verdict":          verdict,
            "icp_method":       "point-to-plane (coarse+fine)",
            "deviation_method": deviation_method,
        },
    }


def run_pipeline(
    stl_path: str,
    n_points: int = 8000,
    noise_std: float = 0.3,
    defect_count: int = 3,
    seed: int = None,
) -> dict:
    ref_mesh = load_mesh(stl_path)

    scan_pcd, defect_regions = simulate_scan(
        ref_mesh, n_points, noise_std, defect_count, seed
    )

    icp_rmse, T = icp_align(scan_pcd, ref_mesh)

    # Merkezleri referans mesh yüzeyine projeksiyon yap.
    # ICP sapkın T üretse de merkezler her zaman model yüzeyinde kalır.
    # pts_original zaten mesh yüzeyinden örneklenmiş → T ≈ identity ise
    # mesafe sıfır; T büyük saparsa KD-tree en yakın yüzey noktasını bulur.
    ref_snap = ref_mesh.sample_points_uniformly(40000)
    ref_snap_pts = np.asarray(ref_snap.points)
    snap_tree = cKDTree(ref_snap_pts)

    for d in defect_regions:
        transformed = np.array(_transform_point(T, d['center']))
        _, idx = snap_tree.query(transformed)
        d['center'] = ref_snap_pts[idx].tolist()

    distances, deviation_method = compute_deviation(scan_pcd, ref_mesh)

    scan_pts = np.asarray(scan_pcd.points)
    anomalies, n_clusters = detect_anomalies(scan_pts, distances, noise_std, defect_count)
    colors = distances_to_colors(distances)

    point_defect_types = [None] * len(scan_pts)
    for defect in defect_regions:
        c  = np.array(defect['center'])
        r  = defect['radius']
        d2 = np.linalg.norm(scan_pts - c, axis=1)
        for i in np.where(d2 < r)[0]:
            if point_defect_types[i] is None:
                point_defect_types[i] = defect['type']

    for d in defect_regions:
        d['risk'] = calculate_risk(d)

    # Sabit mühendislik toleransı — gürültüden bağımsız
    tolerance = 0.5  # mm  (TUSAŞ/havacılık standardı ±0.5 mm)

    # Nokta bazlı temel uyum: kaç nokta tolerans içinde?
    base_conformance = float(np.sum(distances < tolerance) / len(distances) * 100)

    # Risk ağırlıklı hata cezası: her hata bölgesi uyum oranını düşürür
    # (küçük/büyük modellerde nokta sayısı sabit olduğundan ceza daha tutarlı)
    _CONF_PENALTY = {'low': 4, 'medium': 9, 'high': 15, 'critical': 25}
    penalty = sum(_CONF_PENALTY.get(d['risk']['level'], 9) for d in defect_regions)
    conformance = float(max(0.0, min(100.0, base_conformance - penalty)))

    if defect_regions:
        max_score    = max(d['risk']['score'] for d in defect_regions)
        overall_risk = {v: k for k, v in _RISK_SCORE.items()}[max_score]
    else:
        overall_risk = 'low'

    if conformance >= 90 and overall_risk not in ('critical', 'high'):
        verdict = 'accept'
    elif conformance >= 65:
        verdict = 'conditional'
    else:
        verdict = 'reject'

    rms       = float(np.sqrt(np.mean(distances ** 2)))
    hausdorff = float(np.max(distances))
    mean_dev  = float(np.mean(distances))

    return {
        "points":             scan_pts.tolist(),
        "colors":             colors.tolist(),
        "distances":          distances.tolist(),
        "anomalies":          anomalies.tolist(),
        "point_defect_types": point_defect_types,
        "defect_regions":     defect_regions,
        "stats": {
            "rms":              round(rms, 4),
            "max_deviation":    round(hausdorff, 4),
            "mean_deviation":   round(mean_dev, 4),
            "icp_rmse":         round(icp_rmse, 4),
            "anomaly_count":    int(np.sum(anomalies)),
            "anomaly_clusters": n_clusters,
            "total_points":     int(len(scan_pts)),
            "defect_count":     len(defect_regions),
            "conformance":      round(conformance, 2),
            "tolerance_mm":     round(tolerance, 3),
            "overall_risk":     overall_risk,
            "verdict":          verdict,
            "icp_method":       "point-to-plane (coarse+fine)",
            "deviation_method": deviation_method,
        },
    }
