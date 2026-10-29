"""Kapasite tahsisi: bir trafonun boş çatılarına ne kadar GES eklenebilir?

Karar değişkeni   x_j : j binasına eklenecek GES (kWp),   0 ≤ x_j ≤ boş çatı_j
Amaç              max Σ_j e_j · x_j            (e_j: binanın yıllık kWh/kWp verimi)
Kısıtlar (seçili kritik saatlerde t)
  Termik:   Σ_j pv_j(t) · x_j ≤ lim·P + net(t)                         (ters akış sınırı)
  Gerilim:  Σ_j Z_ij · pv_j(t) · x_j ≤ (1 + bant) − V_i(t)   her bina i
            Z_ij = trafodan i ile j'nin ortak atasına kadar olan hattın (R − X·tanφ_inv)/V² değeri
Çözüm: doğrusal programlama (scipy HiGHS) + kesme düzlemi: sonuç 8.760 saatte kontrol edilir,
ihlal olan saat kısıtlara eklenip yeniden çözülür.
Karşılaştırma: sezgisel yöntem (en verimli çatıdan başla, kısıtlar dolana kadar ekle).
"""
import math
import numpy as np
from scipy.optimize import linprog
from .sebeke import gerilimler, K


def _satirlar(s, S, aday, saatler):
    A = s["agac"]; par, Rp, Xp, f = A["par"], A["Rp"], A["Xp"], A["f"]
    ti = math.tan(math.acos(min(1, S.inv_pf))); ust = 1 + S.gerilim_bandi
    V = s["V"]; pv1 = s["_pv1"]
    ata = []
    for i in range(len(par)):
        a, z = i, {}
        while a >= 0: z[a] = Rp[a] - Xp[a] * ti; a = par[a]
        ata.append(z)
    satir, sag = [], []
    for t in saatler:
        satir.append(pv1[aday, t]); sag.append(S.lim * s["P"] + s["NET"][t])
        for i in range(len(par)):
            r = []
            for j in aday:
                if f[j] != f[i]: r.append(0.0); continue
                a = j
                while a >= 0 and a not in ata[i]: a = par[a]
                r.append(ata[i][a] * K * pv1[j, t] if a >= 0 else 0.0)
            r = np.array(r)
            if (r > 1e-12).any(): satir.append(r); sag.append(ust - V[i, t])
    return np.array(satir), np.array(sag)


def _en_kotu_saat(s, S, aday, x):
    ek = np.zeros_like(s["_pv1"]); ek[aday] = s["_pv1"][aday] * x[:, None]
    gun = s["pvU"] > .03
    th = (ek.sum(axis=0) - (S.lim * s["P"] + s["NET"])) / s["P"]
    V, _ = gerilimler(s, S, s["_yuk"], s["_pv1"] * s["_kwp"][:, None], ek=ek)
    vg = (V - (1 + S.gerilim_bandi)).max(axis=0)
    ihlal = np.where(gun, np.maximum(th, vg), -1)
    t = int(ihlal.argmax())
    return t if ihlal[t] > 1e-4 else -1


def _sezgisel(e, ust, satir, sag):
    sl = np.maximum(0, sag.copy()); x = np.zeros(len(e))
    for j in np.argsort(-e):
        k = ust[j]
        for r in range(len(satir)):
            if satir[r, j] > 1e-12: k = min(k, sl[r] / satir[r, j])
        x[j] = max(0, k); sl -= satir[:, j] * x[j]
    return x


def tahsis_et(s, model, S):
    if "agac" not in s or not s["b"]:
        return {m: dict(kwp=0.0, kwh=0.0, binalar=[]) for m in ("lp", "sezgisel")}
    dugum = s["agac"]["dugum"]
    aday = np.array([j for j, b in enumerate(dugum) if s["_bos"][j] >= 1], dtype=int)
    if not len(aday):
        return {m: dict(kwp=0.0, kwh=0.0, binalar=[]) for m in ("lp", "sezgisel")}
    ust = s["_bos"][aday]; e = s["_pv1"][aday].sum(axis=1)
    u = s["pvU"]; m = u > .03
    th = np.where(m, (S.lim * s["P"] + s["NET"]) / np.where(m, u, 1), np.inf)
    H0 = list(dict.fromkeys([s["tR"], *np.argsort(th)[:6].tolist(), *s.get("kritik_saat", [])]))
    out = {}
    for yontem in ("lp", "sezgisel"):
        H = list(H0); x = np.zeros(len(aday)); tur = 0
        for tur in range(1, 9):
            satir, sag = _satirlar(s, S, aday, H)
            if (sag < 0).any(): x[:] = 0; break        # taban durumda zaten ihlal: ek GES yok
            if yontem == "lp":
                r = linprog(-e, A_ub=satir, b_ub=sag, bounds=list(zip(np.zeros(len(ust)), ust)), method="highs")
                x = r.x if r.success else np.zeros(len(aday))
            else:
                x = _sezgisel(e, ust, satir, sag)
            t = _en_kotu_saat(s, S, aday, x)
            if t < 0: break
            H.append(t)
        if _en_kotu_saat(s, S, aday, x) >= 0:          # son güvenlik: orantılı küçült
            lo, hi = 0.0, 1.0
            for _ in range(14):
                mid = (lo + hi) / 2
                lo, hi = (mid, hi) if _en_kotu_saat(s, S, aday, x * mid) < 0 else (lo, mid)
            x = x * lo
        out[yontem] = dict(kwp=float(x.sum()), kwh=float((x * e).sum()), tur=tur,
                           binalar=[(dugum[j], float(x[k])) for k, j in enumerate(aday) if x[k] >= 1])
    return out
