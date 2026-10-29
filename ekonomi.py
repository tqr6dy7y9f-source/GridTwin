"""Bina/hane yatırım analizi: panel (ve isteğe bağlı batarya) kuran bir binanın 25 yıllık nakit akışı.

- Saatlik simülasyon: tüketim − üretim; batarya fazlayı depolar (üç zamanlı tarifede gece de dolar).
- Mahsuplaşma: aylık (ay içindeki üretim ve tüketim netleşir) ya da saatlik.
- Finansman: peşin, kredi (eşit taksit) ya da ESCO (firma yatırır, 10 yıl indirimli satar).
- Tablo kurulum yılının parasıyla verilir (enflasyon ayıklanır); NPV reel iskonto ile.
"""
import math
from dataclasses import dataclass
import numpy as np
from .veri import N
from .model import yillik_kwh, hane


@dataclass
class Ekonomi:
    tarife: str = "tek"; el: float = 3.3; p1: float = 4.9; p2: float = 6.9; p3: float = 3.3
    satis: float = 2.0; panel_tl_kwp: float = 25000; bat_tl_kwh: float = 15000; bat_orani: float = 0.0
    mahsup: str = "ay"; kapsam: str = "daire"; boyut: str = "tuketim"
    finans: str = "pesin"; vade: int = 5; faiz: float = .35; esco_indirim: float = .15; hibe: float = 0.0
    kurulum_yili: int = 2026; enflasyon: float = .25; reel_artis: float = 0.0; iskonto: float = .06
    bakim: float = .01; inverter: float = .10; degradasyon: float = .005


def fiyatlar(E):
    h = np.arange(N) % 24
    if E.tarife == "tek": return np.full(N, E.el)
    return np.where((h >= 22) | (h < 6), E.p3, np.where(h < 17, E.p1, E.p2))


def bina_yatirimi(b, model, S, E, kwp=None):
    g = model.gunes; f = g.bina(b, S); prof = model.v.prof.get(b.tip, model.v.prof["mesken"])
    if b.tip == "mesken":
        hn = hane(b, S); yuk = 1500 + 150 * hn if E.kapsam == "ortak" else hn * S.hane_kwh
    else:
        yuk = yillik_kwh(b, S)
    if kwp is None:
        kwp = b.potansiyel_kwp if E.boyut == "cati" else min(b.potansiyel_kwp, yuk / max(1, f.sum()))
    PRC = fiyatlar(E); cap = kwp * E.bat_orani; bp = cap / 2; e = math.sqrt(.9)
    l = yuk * prof; p = kwp * f; n = l - p
    if cap > 0:
        n = n.copy(); soc = 0.0
        for t in range(N):
            x, h = n[t], t % 24
            if x < 0: c = min(-x, bp, (cap - soc) / e); soc += c * e; x += c
            elif E.tarife == "uc" and (h >= 22 or h < 6): c = min(bp, (cap - soc) / e); soc += c * e; x += c
            else: d = min(x, bp, soc * e); soc -= d / e; x -= d
            n[t] = x
    ay = model.ay
    imp = np.where(n >= 0, n, 0); exp = np.where(n < 0, -n, 0)
    impE = np.bincount(ay, imp, 12); impC = np.bincount(ay, imp * PRC, 12); expE = np.bincount(ay, exp, 12)
    once = float((l * PRC).sum())
    if E.mahsup == "saat":
        sonra, gelir = impC.sum(), expE.sum() * E.satis
    else:
        net = impE - expE
        sonra = float(np.where(net >= 0, np.where(impE > 0, impC * net / np.where(impE > 0, impE, 1), 0), 0).sum())
        gelir = float(np.where(net < 0, -net, 0).sum() * E.satis)
    yil1 = once - sonra + gelir
    yat0 = kwp * E.panel_tl_kwp + cap * E.bat_tl_kwh; yat = yat0 * (1 - E.hibe)
    daire = max(1, round(hane(b, S))) if (b.tip == "mesken" and E.kapsam == "daire") else 1
    i, ay_s = E.faiz / 12, E.vade * 12
    taksit = (yat * i / (1 - (1 + i) ** -ay_s) if i > 0 else yat / ay_s) if E.finans == "kredi" else 0
    dn = (1 + E.iskonto) * (1 + E.enflasyon) - 1
    kum = -yat if E.finans == "pesin" else 0.0; npv = kum; geri = None if E.finans in ("pesin", "kredi") else 0.0
    satirlar = []
    for y in range(1, 26):
        enf = (1 + E.enflasyon) ** (y - 1); pf = enf * (1 + E.reel_artis) ** (y - 1); dg = (1 - E.degradasyon) ** (y - 1)
        gider = E.bakim * yat0 * enf; yen = (E.inverter * kwp * E.panel_tl_kwp + .7 * cap * E.bat_tl_kwh) * enf if y == 12 else 0
        if E.finans == "esco" and y <= 10: tas, gider, yen = E.esco_indirim * (once - sonra) * dg * pf, 0, 0
        else: tas = yil1 * dg * pf
        kredi = 12 * taksit if (E.finans == "kredi" and y <= E.vade) else 0
        npv += (tas - gider - yen - kredi) / (1 + dn) ** y
        k = 1 / enf; tas, gider, yen, kredi = tas * k, gider * k, yen * k, kredi * k     # kurulum yılı parasıyla
        cf = tas - gider - yen - kredi; once_k = kum; kum += cf
        if geri is None and kum >= 0: geri = (y - 1 + (-once_k) / cf) if (once_k < 0 and cf > 0) else y - 1
        satirlar.append(dict(yil=E.kurulum_yili + y - 1, tasarruf=tas, gider=gider + yen, taksit=kredi, net=cf, kumulatif=kum))
    return dict(kwp=kwp, batarya_kwh=cap, uretim=float(p.sum()), yatirim=yat, daire=daire, daire_basi_yatirim=yat / daire,
                fatura_once_ay=once / 12 / daire, fatura_sonra_ay=max(0, (sonra - gelir) / 12 / daire),
                ilk_yil_tasarruf=yil1, geri_odeme_yil=geri, net_25_yil=kum, npv=npv, tablo=satirlar)
