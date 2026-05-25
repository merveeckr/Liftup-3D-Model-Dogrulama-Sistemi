import io
import numpy as np
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch

plt.rcParams['font.family'] = 'DejaVu Sans'

_C = {
    'bg':      '#0d1117',
    'surface': '#161b22',
    'border':  '#30363d',
    'accent':  '#58a6ff',
    'green':   '#3fb950',
    'warn':    '#d29922',
    'danger':  '#f85149',
    'text':    '#c9d1d9',
    'muted':   '#8b949e',
    'orange':  '#ff7b00',
    'purple':  '#bb44ff',
}

_VERDICT = {
    'accept':      ('KABUL',    _C['green']),
    'conditional': ('KOŞULLU', _C['warn']),
    'reject':      ('RED',      _C['danger']),
}
_RISK = {
    'low':      ('Düşük',  _C['green']),
    'medium':   ('Orta',   _C['warn']),
    'high':     ('Yüksek', _C['orange']),
    'critical': ('Kritik', _C['danger']),
}
_TYPE = {
    'bump':    ('Çıkıntı',     _C['orange']),
    'hole':    ('Çukur',       _C['purple']),
    'missing': ('Eksik Bölge', _C['muted']),
}


def _conf_color(c: float) -> str:
    if c >= 95: return _C['green']
    if c >= 85: return _C['warn']
    if c >= 70: return _C['orange']
    return _C['danger']


def _card(ax, x, y, w, h, text_lines):
    """Koyu arka planlı metrik kartı çizer."""
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle='round,pad=0.01',
        facecolor=_C['surface'], edgecolor=_C['border'], linewidth=0.8,
        transform=ax.transAxes, clip_on=False,
    ))
    for dy, (txt, size, color, bold) in enumerate(text_lines):
        ax.text(x + 0.012, y + h - 0.018 - dy * (h / len(text_lines)),
                txt, fontsize=size, color=color,
                fontweight='bold' if bold else 'normal',
                va='top', transform=ax.transAxes)


def generate_pdf(item: dict) -> bytes:
    """
    Analiz kaydından iki sayfalık PDF raporu üretir.
    Sayfa 1: Özet, metrikler, hata tablosu.
    Sayfa 2: Sapma histogramı + algoritma bilgisi.
    """
    stats   = item['result']['stats']
    defects = item['result'].get('defect_regions', [])
    dists   = np.array(item['result'].get('distances', []))
    ts      = datetime.fromisoformat(item['timestamp']).strftime('%Y-%m-%d  %H:%M')

    buf = io.BytesIO()
    with PdfPages(buf) as pdf:

        # ════════════════════════════════════════════════════
        # SAYFA 1 — Özet Rapor
        # ════════════════════════════════════════════════════
        fig = plt.figure(figsize=(11, 8.5), facecolor=_C['bg'])

        # ── Header şeridi ──────────────────────────────────
        hax = fig.add_axes([0, 0.93, 1, 0.07], facecolor=_C['surface'])
        hax.axis('off')
        hax.set_xlim(0, 1); hax.set_ylim(0, 1)
        hax.add_patch(plt.Rectangle((0, 0), 1, 1, color=_C['surface']))
        hax.axhline(0, color=_C['border'], linewidth=1)
        hax.text(0.018, 0.55, 'LIFT', fontsize=20, fontweight='bold',
                 color=_C['accent'], va='center', fontfamily='monospace')
        hax.text(0.072, 0.55, 'UP', fontsize=20, fontweight='bold',
                 color=_C['green'], va='center', fontfamily='monospace')
        hax.text(0.115, 0.55, '— 3D Model Doğrulama Analiz Raporu',
                 fontsize=10, color=_C['muted'], va='center')
        hax.text(0.98, 0.55, 'AYBÜ EEE  ×  TUSAŞ',
                 fontsize=8.5, color=_C['muted'], va='center', ha='right')

        # ── Analiz bilgi kutusu ────────────────────────────
        iax = fig.add_axes([0.03, 0.76, 0.40, 0.155], facecolor=_C['surface'])
        iax.axis('off'); iax.set_xlim(0, 1); iax.set_ylim(0, 1)
        iax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle='round,pad=0.02',
                                     facecolor=_C['surface'], edgecolor=_C['border']))
        iax.text(0.03, 0.92, 'ANALİZ BİLGİSİ', fontsize=7.5, color=_C['muted'],
                 fontweight='bold')
        rows = [
            ('Model',         item['model']),
            ('Tarih',         ts),
            ('Nokta Sayısı',  f"{item['n_points']:,}"),
            ('Gürültü (σ)',   f"{item['noise_std']:.2f} mm"),
            ('Hata Sayısı',   str(item['defect_count'])),
            ('Analiz ID',     f"#{item['id']}"),
        ]
        for k, (lbl, val) in enumerate(rows):
            y = 0.80 - k * 0.135
            iax.text(0.03, y, lbl + ':', fontsize=8, color=_C['muted'])
            iax.text(0.40, y, val,        fontsize=8.5, color=_C['text'], fontweight='bold')

        # ── Uyum halkası ───────────────────────────────────
        cax = fig.add_axes([0.45, 0.73, 0.20, 0.20], facecolor=_C['bg'])
        cax.axis('off')
        conf = stats['conformance']
        cc   = _conf_color(conf)
        cax.pie(
            [conf, 100 - conf],
            colors=[cc, _C['border']],
            startangle=90, counterclock=False,
            wedgeprops={'width': 0.36, 'edgecolor': _C['bg'], 'linewidth': 2},
        )
        cax.text(0, 0.10, f'{conf:.1f}%', ha='center', va='center',
                 fontsize=17, fontweight='bold', color=cc)
        cax.text(0, -0.22, 'uyumlu', ha='center', fontsize=8.5, color=_C['muted'])
        cax.text(0, -1.42, 'UYUM ORANI', ha='center', fontsize=7,
                 color=_C['muted'], fontweight='bold')

        # ── Karar + Risk kutuları ──────────────────────────
        vrax = fig.add_axes([0.67, 0.76, 0.30, 0.155], facecolor=_C['bg'])
        vrax.axis('off'); vrax.set_xlim(0, 1); vrax.set_ylim(0, 1)

        vt, vc = _VERDICT.get(stats['verdict'], ('?', _C['muted']))
        vrax.add_patch(FancyBboxPatch((0.03, 0.52), 0.94, 0.44,
                                      boxstyle='round,pad=0.03',
                                      facecolor=vc + '25', edgecolor=vc, linewidth=1.5))
        vrax.text(0.50, 0.74, vt, ha='center', va='center',
                  fontsize=15, fontweight='bold', color=vc)

        rt, rc = _RISK.get(stats['overall_risk'], ('?', _C['muted']))
        vrax.add_patch(FancyBboxPatch((0.03, 0.04), 0.94, 0.42,
                                      boxstyle='round,pad=0.03',
                                      facecolor=rc + '25', edgecolor=rc, linewidth=1.2))
        vrax.text(0.50, 0.25, rt + ' Risk', ha='center', va='center',
                  fontsize=11, fontweight='bold', color=rc)

        # ── Metrik kartları ────────────────────────────────
        metrics = [
            ('RMS Sapma',   f"{stats['rms']} mm",            'Genel hata büyüklüğü'),
            ('Maks Sapma',  f"{stats['max_deviation']} mm",   'En kötü nokta'),
            ('Ort. Sapma',  f"{stats['mean_deviation']} mm",  'Ortalama hata'),
            ('ICP RMSE',    f"{stats['icp_rmse']} mm",        'Hizalama hatası'),
            ('Anomali',     f"{stats['anomaly_count']} nokta",'Tolerans dışı'),
            ('Küme',        f"{stats.get('anomaly_clusters','—')}","DBSCAN kümeleri"),
            ('Tolerans',    f"±{stats['tolerance_mm']} mm",   '3-sigma sınırı'),
            ('Toplam Nokta',f"{stats['total_points']:,}",     'Tarama yoğunluğu'),
        ]
        max_per_row = 4
        card_h = 0.115
        for idx, (lbl, val, desc) in enumerate(metrics):
            col = idx % max_per_row
            row = idx // max_per_row
            x0  = 0.03 + col * 0.245
            y0  = 0.59 - row * (card_h + 0.015)
            max_x = fig.add_axes([x0, y0, 0.22, card_h], facecolor=_C['bg'])
            max_x.axis('off'); max_x.set_xlim(0, 1); max_x.set_ylim(0, 1)
            max_x.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle='round,pad=0.03',
                                           facecolor=_C['surface'], edgecolor=_C['border']))
            max_x.text(0.06, 0.88, lbl, fontsize=7, color=_C['muted'], va='top')
            max_x.text(0.06, 0.55, val, fontsize=11.5, fontweight='bold',
                       color=_C['accent'], va='top')
            max_x.text(0.06, 0.15, desc, fontsize=6.5, color=_C['muted'], va='top')

        # ── Hata bölgeleri tablosu ─────────────────────────
        if defects:
            tax = fig.add_axes([0.03, 0.04, 0.94, 0.335], facecolor=_C['bg'])
            tax.axis('off'); tax.set_xlim(0, 1); tax.set_ylim(0, 1)
            tax.text(0, 0.97, 'HATA BÖLGELERİ', fontsize=8,
                     color=_C['muted'], fontweight='bold')
            tax.axhline(0.91, color=_C['border'], linewidth=0.8)

            headers = ['#', 'Tip', 'Büyüklük', 'Yarıçap', 'Risk Seviyesi']
            xs      = [0.01, 0.09, 0.30, 0.50, 0.70]
            for i, h in enumerate(headers):
                tax.text(xs[i], 0.87, h, fontsize=8, color=_C['muted'], fontweight='bold')

            for j, d in enumerate(defects[:6]):
                if j >= 6:
                    break
                yr = 0.80 - j * 0.135
                dt, dc = _TYPE.get(d['type'], (d['type'], _C['text']))
                rt2, rc2 = _RISK.get(d.get('risk', {}).get('level', 'high'), ('?', _C['muted']))
                row_vals = [
                    (str(j + 1),          _C['muted']),
                    (dt,                  dc),
                    (f"{d['magnitude']:.2f} mm", _C['text']),
                    (f"{d['radius']:.1f} mm",    _C['text']),
                    (f"{rt2} Risk",        rc2),
                ]
                for i, (txt, clr) in enumerate(row_vals):
                    tax.text(xs[i], yr, txt, fontsize=8.5, color=clr, va='center')
                if j < len(defects) - 1 and j < 5:
                    tax.axhline(yr - 0.06, color=_C['border'], linewidth=0.35,
                                xmin=0.005, xmax=0.995)

        # Footer
        fig.text(0.50, 0.005,
                 f"LIFT UP Projesi  |  Ankara Yıldırım Beyazıt Üniversitesi  |  "
                 f"Sanayi Ortağı: TUSAŞ  |  {datetime.now().year}",
                 ha='center', fontsize=7.5, color=_C['muted'])

        pdf.savefig(fig, facecolor=_C['bg'])
        plt.close(fig)

        # ════════════════════════════════════════════════════
        # SAYFA 2 — Sapma Histogramı + Algoritma Detayları
        # ════════════════════════════════════════════════════
        if len(dists) > 0:
            fig2 = plt.figure(figsize=(11, 8.5), facecolor=_C['bg'])

            # Header
            h2ax = fig2.add_axes([0, 0.93, 1, 0.07], facecolor=_C['surface'])
            h2ax.axis('off'); h2ax.set_xlim(0, 1); h2ax.set_ylim(0, 1)
            h2ax.add_patch(plt.Rectangle((0, 0), 1, 1, color=_C['surface']))
            h2ax.axhline(0, color=_C['border'], linewidth=1)
            h2ax.text(0.018, 0.55, 'Sayfa 2 — Sapma Dağılımı & Algoritma',
                      fontsize=11, color=_C['text'], va='center')
            h2ax.text(0.98, 0.55, f'Analiz #{item["id"]}  |  {item["model"]}',
                      fontsize=8.5, color=_C['muted'], va='center', ha='right')

            # Histogram
            hst = fig2.add_axes([0.08, 0.42, 0.86, 0.46], facecolor=_C['surface'])
            hst.set_facecolor(_C['surface'])
            tol = stats['tolerance_mm']
            n, bins, bars = hst.hist(dists, bins=70, edgecolor=_C['bg'], linewidth=0.3)
            for bar, left in zip(bars, bins[:-1]):
                bar.set_facecolor(_C['green'] if left < tol else _C['danger'])
                bar.set_alpha(0.80)
            hst.axvline(tol, color='white', linewidth=1.8, linestyle='--',
                        label=f'Tolerans sınırı: ±{tol} mm')
            hst.set_xlabel('Sapma (mm)', color=_C['text'], fontsize=11)
            hst.set_ylabel('Nokta Sayısı', color=_C['text'], fontsize=11)
            hst.set_title('Nokta Bulutu — Sapma Dağılım Histogramı',
                          color=_C['text'], fontsize=12, pad=10)
            hst.tick_params(colors=_C['muted'], labelsize=9)
            for spine in hst.spines.values():
                spine.set_color(_C['border'])
            hst.legend(fontsize=9, facecolor=_C['surface'],
                       edgecolor=_C['border'], labelcolor=_C['text'])
            hst.grid(True, color=_C['border'], alpha=0.35, linestyle=':')

            # İstatistik kutusu (histogram üstü)
            hst.text(0.98, 0.97,
                     f"Ort: {stats['mean_deviation']} mm   "
                     f"RMS: {stats['rms']} mm   "
                     f"Maks: {stats['max_deviation']} mm",
                     transform=hst.transAxes, ha='right', va='top',
                     fontsize=8.5, color=_C['muted'],
                     bbox=dict(facecolor=_C['bg'], edgecolor=_C['border'],
                               boxstyle='round,pad=0.4'))

            # Algoritma bilgisi
            alg_ax = fig2.add_axes([0.05, 0.08, 0.90, 0.30], facecolor=_C['bg'])
            alg_ax.axis('off'); alg_ax.set_xlim(0, 1); alg_ax.set_ylim(0, 1)
            alg_ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle='round,pad=0.02',
                                            facecolor=_C['surface'], edgecolor=_C['border']))
            alg_ax.text(0.03, 0.91, 'ALGORİTMA BİLGİSİ', fontsize=8,
                        color=_C['muted'], fontweight='bold')
            alg_rows = [
                ('ICP Yöntemi',       stats.get('icp_method', 'N/A')),
                ('Sapma Yöntemi',     stats.get('deviation_method', 'N/A')),
                ('Anomali Tespiti',   '3-sigma eşiği  +  IsolationForest  +  DBSCAN kümeleme'),
                ('Simülasyon',        'Yüzey normaline dik Gaussian gürültü (LiDAR modeli)'),
                ('Tolerans Formülü',  'tolerans = σ × 3 + 0.3 mm'),
                ('Kalite Kriteri',    'Uyum ≥ %90 ve risk ≠ Kritik → KABUL'),
            ]
            for k, (lbl, val) in enumerate(alg_rows):
                y = 0.80 - k * 0.135
                alg_ax.text(0.02, y, lbl + ':', fontsize=8,
                            color=_C['muted'], va='center')
                alg_ax.text(0.26, y, val, fontsize=8.5,
                            color=_C['text'], va='center')

            fig2.text(0.50, 0.008,
                      f"LIFT UP Projesi  |  Ankara Yıldırım Beyazıt Üniversitesi  |  "
                      f"Sanayi Ortağı: TUSAŞ  |  {datetime.now().year}",
                      ha='center', fontsize=7.5, color=_C['muted'])

            pdf.savefig(fig2, facecolor=_C['bg'])
            plt.close(fig2)

    buf.seek(0)
    return buf.read()
