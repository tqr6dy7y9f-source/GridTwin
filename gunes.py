"""Güneş modeli: her çatı için kWp başına saatlik GES üretimi.

Adımlar (her saat için)
1. Güneşin konumu (yükseklik, azimut) → güneşe doğru birim vektör.
2. Çatı yüzeyine düşen ışınım (POA): doğrudan bileşen × geliş açısı kosinüsü
   + dağınık bileşen × gökyüzü görüş faktörü (izotropik model) + yer yansıması (albedo 0,2).
3. Komşu binaların gölgesi: güneş o yöndeki ufuk açısının altındaysa doğrudan ışınım 0.
4. Panel sıcaklığı: Tc = Tdış + POA/800 × 20 ;  verim kaybı %0,4/°C (25 °C üstü).
5. Sistem performans oranı 0,86.
6. Kalibrasyon: güneye 30° bakan gölgesiz çatının yıllık üretimi referans değere (ör. 1.250 kWh/kWp) eşitlenir.
"""
import numpy as np
from .veri import N


class Gunes:
    def __init__(self, v):
        e, a = np.radians(v.el), np.radians(v.az)
        self.v = v
        self.sx, self.sy, self.sz = np.cos(e) * np.sin(a), np.cos(e) * np.cos(a), np.sin(e)
        self.gunduz = v.el > 0
        self._ref0 = self.ham(30, 180, None, 1.0)
        self._cache = {}
        self.ayar = None

    def ham(self, egim, az, ufuk, gok):
        v, bt, ba = self.v, np.radians(egim), np.radians(az)
        nx, ny, nz = np.sin(bt) * np.sin(ba), np.sin(bt) * np.cos(ba), np.cos(bt)
        cos_i = np.maximum(0, self.sx * nx + self.sy * ny + self.sz * nz)
        dogrudan = v.dni * cos_i
        if ufuk is not None:
            yon = (np.floor(v.az / 10).astype(int)) % 36
            dogrudan = np.where(v.el < ufuk[yon], 0, dogrudan)
        poa = dogrudan + v.dhi * (1 + nz) / 2 * gok + v.ghi * 0.2 * (1 - nz) / 2
        tc = v.T + poa / 800 * 20
        out = poa / 1000 * 0.86 * (1 - 0.004 * (tc - 25))
        return np.where(self.gunduz, out, 0.0)

    def kalibre(self, S):
        anahtar = (S.ref_verim, S.cati, S.egim, S.golge)
        if anahtar != self.ayar:
            self.ayar, self._cache = anahtar, {}
            self.k = S.ref_verim / self._ref0.sum()
        self.ref = self._ref0 * self.k

    def bina(self, b, S):
        """Binanın kWp başına saatlik üretimi (kW/kWp)."""
        a = self._cache.get(b.id)
        if a is None:
            duz = S.cati == "duz"
            a = self.ham(15 if duz else S.egim, 180 if duz else b.cati_az,
                         b.ufuk if S.golge else None, b.gok_gorus if S.golge else 1.0) * self.k
            self._cache[b.id] = a
        return a

    def verim(self, b, S):
        """Yıllık kWh/kWp."""
        return float(self.bina(b, S).sum())
