"""Trafo modeli: binaları trafolara atar, her trafo için 8.760 saatlik yük ve GES dengesini hesaplar.

Termik sınırlar
- İleri yük:   trafodan çekilen güç ≤ trafo gücü (kVA × 0,95)
- Ters akış:   şebekeye geri verilen güç ≤ lim × trafo gücü (varsayılan %50)
Barındırma kapasitesi (kalan GES):  HC = min_t (lim·P + net_t) / u_t
  net_t: saatlik net tüketim (kW), u_t: o trafodaki çatıların ortalama kWp başına üretimi.
"""
import math
from dataclasses import dataclass, field
import numpy as np
from .veri import N
from .gunes import Gunes

EV_SEKIL = {18: .15, 19: .25, 20: .25, 21: .2, 22: .15}   # akşam şarjının saatlere dağılımı
ISI_KWH = 8000                                           # hane başı yıllık ısı ihtiyacı (kWh_th)
ISI_SAAT = [.5, .4, .4, .4, .5, .8, 1.3, 1.5, 1.2, .9, .8, .8, .8, .8, .8, .9, 1.1, 1.4, 1.6, 1.6, 1.5, 1.3, 1, .7]
OTOBUS_KWH = 335 * 1.3                                   # e-otobüs: 335 km/gün × 1,3 kWh/km
KVA_STD = [250, 400, 630, 800, 1000, 1250, 1600, 2000, 2500]


@dataclass
class Ayarlar:
    # senaryo
    ges: float = .05          # çatı potansiyelinin kurulu payı
    ev: float = .015          # elektrikli araçlı hane payı
    akilli: bool = False      # akıllı şarj (00–06)
    isi: float = 0.0          # ısı pompalı hane payı
    # güneş
    ref_verim: float = 1250   # güneye 30° gölgesiz çatı, kWh/kWp
    cati: str = "egimli"      # egimli / duz
    egim: float = 25
    golge: bool = True
    # batarya
    bina_bat: float = 0.0     # kWh / kWp
    trafo_bat: float = 0.0    # kWh
    # şebeke
    lim: float = .5
    kva: float = 630
    kat_carpan: float = 1.0
    yaricap: float = 120
    hane_kwh: float = 2500
    tarife: str = "tek"       # tek / uc (üç zamanlı)
    otobus: dict = field(default_factory=dict)   # {trafo_indeksi: otobüs sayısı}
    otobus_mod: str = "gunduz"
    # AG hat
    kablo: str = "y150"
    gerilim_bandi: float = .10
    trafo_gerilim: float = 1.0
    inv_pf: float = 1.0
    tahsis: str = "lp"        # lp / sezgisel

    @staticmethod
    def senaryo(ad):
        S = {"bugun": dict(ges=.05, ev=.015, isi=0, akilli=False),
             "2030": dict(ges=.08, ev=.085, isi=.02, akilli=False),
             "2035": dict(ges=.12, ev=.21, isi=.05, akilli=False),
             "2035_akilli": dict(ges=.12, ev=.21, isi=.05, akilli=True),
             "stres": dict(ges=.6, ev=.35, isi=.3, akilli=False)}[ad]
        return Ayarlar(**S)


def yuvarla(x):
    return int(math.floor(x + 0.5))


def kat(b, S):
    return b.kat if b.kat_kesin else max(1, yuvarla(b.kat * S.kat_carpan))


def hane(b, S):
    return b.alan * kat(b, S) * 0.85 / 110 if b.tip == "mesken" else 0.0


def yillik_kwh(b, S):
    f = kat(b, S)
    if b.tip == "mesken": return b.alan * f * 0.85 / 110 * S.hane_kwh
    if b.tip == "ticari": return b.alan * f * 80
    if b.tip == "okul": return b.alan * f * 25
    return b.alan * 15


class Model:
    def __init__(self, veri):
        self.v = veri
        self.gunes = Gunes(veri)
        T = veri.T
        h = np.arange(N) % 24
        isi = np.maximum(0, 16 - T) * np.array(ISI_SAAT)[h]
        self.ISI = isi / isi.sum()
        self.COP = np.clip(2.2 + 0.09 * (T + 5), 2.2, 4.2)
        self.saat = h
        ay_bas = np.array([0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365]) * 24
        self.ay = np.searchsorted(ay_bas, np.arange(N), side="right") - 1

    def ata(self, S):
        for b in self.v.binalar:
            d = [math.hypot(b.x - t.x, b.y - t.y) for t in self.v.trafolar]
            i = int(np.argmin(d))
            b.trafo = i if d[i] <= S.yaricap else -1

    def trafo_degerlendir(self, s, bat_kwh, kva, S):
        """Bir trafonun yılını saat saat hesaplar (bataryalar sırayla şarj/deşarj eder)."""
        P = kva * .95
        if "L" not in s:
            h = self.saat
            lb = sum(s["E"][k] * self.v.prof[k] for k in s["E"])
            ev_gun = s["hane"] * S.ev * 8
            if S.akilli: lev = np.where(h < 6, ev_gun / 6, 0.0)
            else: lev = np.array([EV_SEKIL.get(x, 0) for x in range(24)])[h] * ev_gun
            lhp = s["hane"] * S.isi * ISI_KWH * self.ISI / self.COP
            nb = S.otobus.get(s["i"], 0)
            if S.otobus_mod == "gunduz": lbus = np.where((h >= 6) & (h < 23), nb * OTOBUS_KWH / 17, 0.0)
            else: lbus = np.where((h >= 22) | (h < 6), nb * OTOBUS_KWH / 8, 0.0)
            s.update(LB=lb, LEV=lev, LHP=lhp, LBUS=lbus, L=lb + lev + lhp + lbus, PV=s["pvU"] * s["kwp"])
        n = s["L"] - s["PV"]
        hb = s["kwp"] * S.bina_bat
        if hb > 0 or bat_kwh > 0:          # bataryalar: saatlik sıralı simülasyon
            n = n.copy(); e = math.sqrt(.92); hs = 0.0; soc = bat_kwh * .5; thr = .7 * P
            for t in range(N):
                x, hr = n[t], t % 24
                if hb > 0:
                    if x < 0: c = min(-x, hb / 2, (hb - hs) / e); hs += c * e; x += c
                    elif S.tarife == "uc" and (hr >= 22 or hr < 6): c = min(hb / 2, (hb - hs) / e); hs += c * e; x += c
                    else: d = min(x, hb / 2, hs * e); hs -= d / e; x -= d
                if bat_kwh > 0:
                    bp = bat_kwh / 2
                    if x < 0: c = min(-x, bp, (bat_kwh - soc) / e); soc += c * e; x += c
                    elif x > thr: d = min(x - thr, bp, soc * e); soc -= d / e; x -= d
                    elif hr < 6:
                        hedef = .4 if 3 <= self.ay[t] <= 8 else .9
                        if soc < hedef * bat_kwh:
                            c = min(max(0, .6 * P - x), bp, (hedef * bat_kwh - soc) / e); soc += c * e; x += c
                n[t] = x
        u = s["pvU"]; m = u > .03
        hc = np.min((S.lim * P + n[m]) / u[m]) if m.any() else 1e12
        return dict(NET=n, P=P, ileri=n.max() / P, ters=max(0, -n.min()) / P, tF=int(n.argmax()), tR=int(n.argmin()),
                    hc=max(0.0, float(hc)), asim=int(((n > P) | (-n > S.lim * P)).sum()))

    def simule(self, S, gerilim=True, tahsis=True):
        from .sebeke import gerilim_hesapla, durum
        from .optimizasyon import tahsis_et
        g = self.gunes; g.kalibre(S); self.ata(S)
        siteler = []
        for i, t in enumerate(self.v.trafolar):
            siteler.append(dict(i=i, id=t.id, ad=t.ad, x=t.x, y=t.y, kva=t.kva or S.kva * t.adet,
                                E={"mesken": 0, "ticari": 0, "okul": 0, "cami": 0}, hane=0.0, pot=0.0, b=[]))
        for b in self.v.binalar:
            if b.trafo < 0: continue
            s = siteler[b.trafo]
            s["E"][b.tip] += yillik_kwh(b, S); s["hane"] += hane(b, S); s["pot"] += b.potansiyel_kwp; s["b"].append(b)
        for s in siteler:
            w = sum(b.potansiyel_kwp for b in s["b"])
            s["pvU"] = sum(g.bina(b, S) * b.potansiyel_kwp for b in s["b"]) / w if w > 0 else g.ref
            s["kwp"] = s["pot"] * S.ges
            s["bat"] = S.trafo_bat
            s.update(self.trafo_degerlendir(s, s["bat"], s["kva"], S))
            s["hcT"] = s["hc"]
            if gerilim:
                gerilim_hesapla(s, self, S); s["hc"] = min(s["hcT"], s["hcV"])
            s["durum"] = durum(s, S)
            s["pv_kwh"], s["yuk_kwh"] = float(s["PV"].sum()), float(s["L"].sum())
        sonuc = dict(siteler=siteler, asan=sum(s["durum"] == "asim" for s in siteler))
        if tahsis and gerilim:
            sonuc["tahsis"] = {s["id"]: tahsis_et(s, self, S) for s in siteler}
        return sonuc

    def cozum_ara(self, s, S):
        """Sınır aşılıyorsa: gereken trafo bataryası (ikili arama) ve yetecek en küçük standart trafo."""
        ok = lambda r: r["ileri"] <= 1 and r["ters"] <= S.lim
        bat = None
        if ok(self.trafo_degerlendir(s, 0, s["kva"], S)): bat = 0
        elif ok(self.trafo_degerlendir(s, 4000, s["kva"], S)):
            lo, hi = 0, 4000
            while hi - lo > 10:
                m = (lo + hi) / 2
                lo, hi = (lo, m) if ok(self.trafo_degerlendir(s, m, s["kva"], S)) else (m, hi)
            bat = math.ceil(hi / 25) * 25
        kva = next((k for k in KVA_STD if k > s["kva"] and ok(self.trafo_degerlendir(s, s["bat"], k, S))), None)
        return dict(batarya_kwh=bat, yeni_kva=kva)
