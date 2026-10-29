"""Alçak gerilim (AG) hat modeli: binalardaki gerilim yükselmesi/düşmesi.

Varsayımlar
- Her trafonun binaları 4 besleyiciye (90°'lik dilimler) ayrılır.
- Besleyicide binalar trafoya uzaklık sırasıyla eklenir; her bina kendinden önce eklenmiş en yakın
  binaya ya da trafoya bağlanır → radyal ağaç. Kablo uzunluğu = kuş uçuşu × 1,3.
- Gerilim değişimi (400 V, 3 faz):  ΔV [pu] = (R·P + X·Q) / V²
  P: aşağı akıştaki net çekiş (tüketim − GES), Q: tüketimin reaktif gücü (cosφ 0,95) + inverterin emdiği reaktif güç.
- Hesap 8.760 saat × bina için vektörel yapılır (numpy).
Gerilim barındırma kapasitesi: boş çatılara orantılı dağıtılan ek GES için
  V_i(t) + k · g_i(t) ≤ 1 + bant   →   HC_V = min_{i,t} (1 + bant − V_i) / g_i
"""
import math
import numpy as np
from .veri import N

KABLO = {"y150": dict(r=.206, x=.074, ad="Yeraltı 4×150 mm² Al"),
         "y95": dict(r=.320, x=.075, ad="Yeraltı 4×95 mm² Al"),
         "h70": dict(r=.443, x=.10, ad="Havai 3×70+54,6 mm² Al (ABC)")}
VLL, TQ_YUK, DET = 400.0, math.tan(math.acos(.95)), 1.3
K = 1000 / VLL ** 2


def agac_kur(s, S):
    c = KABLO[S.kablo]
    dil = [[], [], [], []]
    for b in s["b"]:
        dx, dy = b.x - s["x"], b.y - s["y"]
        b._d = math.hypot(dx, dy)
        b._f = int((math.atan2(dy, dx) + math.pi) // (math.pi / 2)) % 4
        dil[b._f].append(b)
    dugum = []
    for d in dil:
        d.sort(key=lambda b: b._d); dugum += d
    n = len(dugum)
    par = np.full(n, -1); R = np.zeros(n); X = np.zeros(n); Rp = np.zeros(n); Xp = np.zeros(n); Lp = np.zeros(n)
    f = np.array([b._f for b in dugum], dtype=int)
    for i, b in enumerate(dugum):
        en, p = b._d, -1
        for q in range(i):
            if f[q] != b._f: continue
            o = dugum[q]; d = math.hypot(b.x - o.x, b.y - o.y)
            if d < en: en, p = d, q
        L = en * DET / 1000
        par[i], R[i], X[i] = p, c["r"] * L, c["x"] * L
        Rp[i] = (Rp[p] if p >= 0 else 0) + R[i]; Xp[i] = (Xp[p] if p >= 0 else 0) + X[i]; Lp[i] = (Lp[p] if p >= 0 else 0) + L
    s["agac"] = dict(dugum=dugum, par=par, R=R, X=X, Rp=Rp, Xp=Xp, Lp=Lp, f=f)


def dugum_verisi(s, model, S):
    """Her binanın saatlik tüketimi ve GES profili (n × 8760)."""
    from .model import yillik_kwh, hane
    A = s["agac"]; g = model.gunes
    ev = s["LEV"] + s["LHP"]
    yuk = np.array([yillik_kwh(b, S) * model.v.prof[b.tip] + (hane(b, S) / s["hane"] if s["hane"] > 0 else 0) * ev for b in A["dugum"]])
    pv1 = np.array([g.bina(b, S) for b in A["dugum"]])                  # kW/kWp
    kwp = np.array([b.potansiyel_kwp * S.ges for b in A["dugum"]])
    bos = np.array([b.potansiyel_kwp * (1 - S.ges) for b in A["dugum"]])
    return yuk, pv1, kwp, bos


def gerilimler(s, S, yuk, pv, ek=None, w=None):
    """Tüm saatler için düğüm gerilimleri V (n × N). w verilirse dağıtılmış ek GES duyarlılığı G de döner."""
    A = s["agac"]; par, n = A["par"], len(A["dugum"])
    ti = math.tan(math.acos(min(1, S.inv_pf)))
    pvk = pv if ek is None else pv + ek
    P = yuk - pvk; Q = yuk * TQ_YUK + pvk * ti
    Gs = None if w is None else w
    P = P.copy(); Q = Q.copy(); Gs = None if w is None else Gs.copy()
    for i in range(n - 1, -1, -1):              # aşağı akış toplamları
        p = par[i]
        if p >= 0:
            P[p] += P[i]; Q[p] += Q[i]
            if Gs is not None: Gs[p] += Gs[i]
    V = np.empty_like(P); G = None if w is None else np.empty_like(P)
    for i in range(n):                          # trafodan uca gerilim
        p = par[i]
        V[i] = (S.trafo_gerilim if p < 0 else V[p]) - (A["R"][i] * P[i] + A["X"][i] * Q[i]) * K
        if G is not None:
            G[i] = (0 if p < 0 else G[p]) + (A["R"][i] - A["X"][i] * ti) * Gs[i] * K
    return V, G


def gerilim_hesapla(s, model, S):
    agac_kur(s, S)
    if not s["b"]:
        s.update(vmin=S.trafo_gerilim, vmax=S.trafo_gerilim, hcV=1e6, kritik_saat=[]); return
    yuk, pv1, kwp, bos = dugum_verisi(s, model, S)
    s["_yuk"], s["_pv1"], s["_kwp"], s["_bos"] = yuk, pv1, kwp, bos
    w = (bos / bos.sum())[:, None] * pv1 if bos.sum() > 0 else np.zeros_like(pv1)
    V, G = gerilimler(s, S, yuk, pv1 * kwp[:, None], w=w)
    ust = 1 + S.gerilim_bandi
    gun = s["pvU"] > .03
    with np.errstate(divide="ignore", invalid="ignore"):
        h = np.where((G > 1e-12) & gun[None, :], (ust - V) / G, np.inf)
    hc_saat = h.min(axis=0)
    kritik = [int(t) for t in np.argsort(hc_saat)[:6] if np.isfinite(hc_saat[t])]
    s.update(V=V, vmin=float(V.min()), vmax=float(V.max()), tmin=int(V.min(axis=0).argmin()), tmax=int(V.max(axis=0).argmax()),
             hcV=float(max(0, hc_saat.min())) if np.isfinite(hc_saat.min()) else 1e6, kritik_saat=kritik,
             sinir_disi=int(((V > ust) | (V < 1 - S.gerilim_bandi)).sum()), en_uzun_hat_m=float(s["agac"]["Lp"].max() * 1000))


def durum(s, S):
    """uygun / sinirda / asim"""
    vb = S.gerilim_bandi
    v_asim = "vmax" in s and (s["vmax"] > 1 + vb or s["vmin"] < 1 - vb)
    v_yakin = "vmax" in s and (s["vmax"] > 1 + vb - .01 or s["vmin"] < 1 - vb + .01)
    if s["ileri"] > 1 or s["ters"] > S.lim or v_asim: return "asim"
    if s["hc"] < 50 or s["ileri"] > .8 or v_yakin: return "sinirda"
    return "uygun"
