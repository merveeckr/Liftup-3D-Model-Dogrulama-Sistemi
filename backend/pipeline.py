import numpy as np
import open3d as o3d
from scipy.spatial import cKDTree
from sklearn.ensemble import IsolationForest


_RISK_SCORE = {'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
_RISK_LABEL = {'low': 'Düşük', 'medium': 'Orta', 'high': 'Yüksek', 'critical': 'Kritik'}

# (magnitude_üst_sınır → risk) eşikleri — tip başına
_THRESHOLDS = {
    'bump':    [(1.2, 'low'), (2.5, 'medium'), (3.8, 'high'),  (float('inf'), 'critical')],
    'hole':    [(0.8, 'low'), (1.8, 'medium'), (3.0, 'high'),  (float('inf'), 'critical')],
    'missing': [(0.0, 'high'), (float('inf'), 'critical')],    # eksik → her zaman Yüksek+
}


def calculate_risk(defect: dict) -> dict:
    """Magnitude + tip + alan büyüklüğüne göre risk seviyesi hesapla."""
    dtype     = defect['type']
    magnitude = defect['magnitude']
    radius    = defect['radius']

    thresholds = _THRESHOLDS.get(dtype, _THRESHOLDS['bump'])
    level = 'critical'
    for limit, lv in thresholds:
        if magnitude <= limit:
            level = lv
            break

    # Geniş alan riski bir seviye artırır (radius > 7 mm)
    if radius > 7.0 and _RISK_SCORE[level] < 4:
        levels = ['low', 'medium', 'high', 'critical']
        level  = levels[_RISK_SCORE[level]]   # bir üst seviyeye geç

    return {'level': level, 'label': _RISK_LABEL[level], 'score': _RISK_SCORE[level]}


def load_mesh(stl_path: str) -> o3d.geometry.TriangleMesh:
    mesh = o3d.io.read_triangle_mesh(stl_path)
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
    Referans mesh yüzeyinden nokta örnekler, Gaussian gürültü ekler
    ve üç tipte yapay imalat hatası enjekte eder:
      - bump   : malzeme fazlası / çıkıntı
      - hole   : malzeme eksiği / çukur
      - missing: o bölgede hiç nokta yok (eksik tarama)
    """
    if seed is not None:
        np.random.seed(seed)

    pcd = mesh.sample_points_uniformly(n_points)
    pts = np.asarray(pcd.points).copy()
    keep = np.ones(len(pts), dtype=bool)   # missing bölgeler için maske

    # Sensör gürültüsü (Gaussian)
    pts += np.random.normal(0, noise_std, pts.shape)

    defect_types = ['bump', 'hole', 'missing']
    defect_regions = []

    for i in range(defect_count):
        dtype = defect_types[i % len(defect_types)]   # sırayla: çıkıntı, çukur, eksik

        center_idx = np.random.randint(0, len(pts))
        center = pts[center_idx].copy()
        radius = np.random.uniform(3.0, 8.0)
        dists  = np.linalg.norm(pts - center, axis=1)
        mask   = (dists < radius) & keep

        if not np.any(mask):
            continue

        if dtype == 'bump':
            magnitude = np.random.uniform(1.5, 4.0)
            direction = np.random.randn(3)
            direction /= np.linalg.norm(direction)
            falloff = np.exp(-dists[mask] ** 2 / (2 * (radius / 3) ** 2))
            pts[mask] += direction[np.newaxis, :] * (magnitude * falloff[:, np.newaxis])

        elif dtype == 'hole':
            magnitude = np.random.uniform(-3.5, -1.5)   # içe doğru
            direction = np.random.randn(3)
            direction /= np.linalg.norm(direction)
            falloff = np.exp(-dists[mask] ** 2 / (2 * (radius / 3) ** 2))
            pts[mask] += direction[np.newaxis, :] * (magnitude * falloff[:, np.newaxis])

        elif dtype == 'missing':
            keep[mask] = False   # bu bölgedeki noktaları sil
            magnitude = 0.0

        defect_regions.append({
            "center": center.tolist(),
            "radius": float(radius),
            "magnitude": float(abs(magnitude)) if dtype != 'missing' else 0.0,
            "type": dtype,
        })

    pts = pts[keep]
    pcd.points = o3d.utility.Vector3dVector(pts)
    return pcd, defect_regions


def icp_align(
    scan_pcd: o3d.geometry.PointCloud,
    ref_mesh: o3d.geometry.TriangleMesh,
) -> tuple:
    """
    ICP ile tarama noktalarını referans mesh'e hizalar.
    Döndürür: (ICP RMSE, 4×4 dönüşüm matrisi)
    Matris, defekt merkezlerini de dönüştürmek için kullanılır.
    """
    ref_pcd = ref_mesh.sample_points_poisson_disk(20000)

    result = o3d.pipelines.registration.registration_icp(
        scan_pcd,
        ref_pcd,
        max_correspondence_distance=15.0,
        init=np.eye(4),
        estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(),
        criteria=o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=60),
    )
    scan_pcd.transform(result.transformation)
    return float(result.inlier_rmse), result.transformation


def compute_deviation(
    scan_pcd: o3d.geometry.PointCloud,
    ref_mesh: o3d.geometry.TriangleMesh,
) -> np.ndarray:
    """
    Her tarama noktası için referans yüzeyine olan en yakın mesafeyi hesaplar.
    Point-to-surface distance (nearest-neighbor approximation).
    """
    ref_dense = ref_mesh.sample_points_uniformly(80000)
    ref_pts = np.asarray(ref_dense.points)
    scan_pts = np.asarray(scan_pcd.points)

    tree = cKDTree(ref_pts)
    distances, _ = tree.query(scan_pts, k=1)
    return distances


def detect_anomalies(
    scan_pts: np.ndarray,
    distances: np.ndarray,
    noise_std: float,
    contamination: float = 0.08,
) -> np.ndarray:
    """
    İki katmanlı anomali tespiti:
    1. Tolerans eşiği (3-sigma kural)
    2. IsolationForest (uzamsal+sapma özellikler)
    """
    threshold = noise_std * 3 + 0.5
    threshold_anomaly = distances > threshold

    features = np.column_stack([scan_pts, distances])
    clf = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
        n_jobs=-1,
    )
    iso_anomaly = clf.fit_predict(features) == -1

    return threshold_anomaly | iso_anomaly


def distances_to_colors(distances: np.ndarray) -> np.ndarray:
    """
    Sapmayı Blue→Cyan→Green→Yellow→Red renk haritasıyla görselleştirir.
    98. yüzdelik sapma = tam kırmızı.
    """
    vmax = np.percentile(distances, 98)
    if vmax < 1e-9:
        vmax = 1.0
    t = np.clip(distances / vmax, 0.0, 1.0)
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


def run_pipeline(
    stl_path: str,
    n_points: int = 8000,
    noise_std: float = 0.3,
    defect_count: int = 3,
    seed: int = None,
) -> dict:
    """Ana pipeline: yükle → simüle et → hizala → sapma hesapla → anomali tespit et."""
    ref_mesh = load_mesh(stl_path)

    scan_pcd, defect_regions = simulate_scan(
        ref_mesh, n_points, noise_std, defect_count, seed
    )

    icp_rmse, T = icp_align(scan_pcd, ref_mesh)

    # Defekt merkezlerini ICP dönüşümüyle güncelle
    for d in defect_regions:
        d['center'] = _transform_point(T, d['center'])

    distances = compute_deviation(scan_pcd, ref_mesh)

    scan_pts = np.asarray(scan_pcd.points)
    anomalies = detect_anomalies(scan_pts, distances, noise_std)
    colors = distances_to_colors(distances)

    # Her noktaya hangi defekt bölgesine girdiğini ata (en yakın, ilk eşleşen)
    point_defect_types = [None] * len(scan_pts)
    for defect in defect_regions:
        c = np.array(defect['center'])
        r = defect['radius']
        d2center = np.linalg.norm(scan_pts - c, axis=1)
        for i in np.where(d2center < r)[0]:
            if point_defect_types[i] is None:
                point_defect_types[i] = defect['type']

    # Her defekte risk hesapla
    for d in defect_regions:
        d['risk'] = calculate_risk(d)

    # Uyum yüzdesi: tolerans içindeki nokta oranı (3-sigma + 0.3 mm taban)
    tolerance   = noise_std * 3 + 0.3
    conformance = float(np.sum(distances < tolerance) / len(distances) * 100)

    # Genel risk: en yüksek defekt riski
    if defect_regions:
        max_score    = max(d['risk']['score'] for d in defect_regions)
        overall_risk = {v: k for k, v in _RISK_SCORE.items()}[max_score]
    else:
        overall_risk = 'low'

    # Kalite kararı
    if conformance >= 90 and overall_risk not in ('critical',):
        verdict = 'accept'
    elif conformance >= 70:
        verdict = 'conditional'
    else:
        verdict = 'reject'

    rms       = float(np.sqrt(np.mean(distances ** 2)))
    hausdorff = float(np.max(distances))
    mean_dev  = float(np.mean(distances))

    return {
        "points": scan_pts.tolist(),
        "colors": colors.tolist(),
        "distances": distances.tolist(),
        "anomalies": anomalies.tolist(),
        "point_defect_types": point_defect_types,
        "defect_regions": defect_regions,
        "stats": {
            "rms": round(rms, 4),
            "max_deviation": round(hausdorff, 4),
            "mean_deviation": round(mean_dev, 4),
            "icp_rmse": round(icp_rmse, 4),
            "anomaly_count": int(np.sum(anomalies)),
            "total_points": int(len(scan_pts)),
            "defect_count": len(defect_regions),
            "conformance": round(conformance, 2),
            "tolerance_mm": round(tolerance, 3),
            "overall_risk": overall_risk,
            "verdict": verdict,
        },
    }
