"""Veri katmanı: OpenStreetMap'ten hazırlanmış Atakum verisini (atakum_data.json) okur.

İçerik
- prof   : 4 bina tipi için 8.760 saatlik normalize tüketim profili (mesken, ticari, okul, cami)
- T      : saatlik dış sıcaklık (°C)
- sun    : güneş yüksekliği/azimutu (pvlib ile hesaplandı) ve ışınım bileşenleri DNI, DHI, GHI (W/m²)
- bina   : her bina için taban alanı, kat, tip, konum (m), çatı azimutu ve 36 yönlü ufuk açısı
- trafo  : trafo noktaları (OSM + Google Haritalar kaydı)
"""
import base64, json
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np

N = 8760
VERI = Path(__file__).resolve().parent.parent / "veri" / "atakum_data.json"


def _coz(s, olcek, ofset=0):
    """base64 içindeki uint16 diziyi ondalık sayıya çevirir: (değer − ofset) / ölçek."""
    a = np.frombuffer(base64.b64decode(s), dtype="<u2").astype(np.float64)
    return (a - ofset) / olcek


@dataclass
class Bina:
    id: int
    tip: str            # mesken / ticari / okul / cami
    kat: int            # OSM'deki ya da tahmin edilen kat sayısı
    kat_kesin: bool     # kat sayısı OSM'de var mı
    alan: float         # taban alanı (m²)
    ad: str
    x: float            # doğu (m)
    y: float            # güney (m)
    cati_az: float      # çatının güneye en yakın yüzünün azimutu (°)
    yukseklik: float    # m
    ufuk: np.ndarray    # 36 yönde (10°'de bir) komşu binaların oluşturduğu ufuk açısı (°)
    trafo: int = -1     # atandığı trafo (-1: bilinmiyor)

    @property
    def potansiyel_kwp(self):
        """Çatıya sığacak GES: kullanılabilir çatı payı / 6 m² kWp başına."""
        return self.alan * (0.4 if self.tip == "mesken" else 0.5) / 6

    @property
    def gok_gorus(self):
        """Gökyüzü görüş faktörü: dağınık ışınımın ufuk tarafından kesilmeyen payı."""
        return 1 - np.mean(np.sin(np.radians(self.ufuk)))


@dataclass
class Trafo:
    id: str
    ad: str
    x: float
    y: float
    adet: int = 1
    kva: float | None = None   # bilinmiyorsa varsayılan kullanılır


@dataclass
class Veri:
    prof: dict
    T: np.ndarray
    el: np.ndarray
    az: np.ndarray
    dni: np.ndarray
    dhi: np.ndarray
    ghi: np.ndarray
    binalar: list
    trafolar: list
    meta: dict = field(default_factory=dict)


def yukle(yol=VERI) -> Veri:
    D = json.loads(Path(yol).read_text(encoding="utf-8"))
    prof = {k: _coz(v, 2000) / N for k, v in D["prof"].items()}
    s = D["sun"]
    binalar = []
    for b in D["bina"]:
        ufuk = np.frombuffer(base64.b64decode(b["hz"]), dtype=np.uint8).astype(float) / 2
        binalar.append(Bina(b["id"], b["k"], b["lv"], b["lvk"], b["A"], b.get("ad") or "",
                            b["c"][0], b["c"][1], b["raz"], b["h"], ufuk))
    trafolar = [Trafo(t["id"], t["ad"], t["p"][0], t["p"][1], t.get("n", 1)) for t in D["trafo"]]
    return Veri(prof, _coz(D["T"], 100, 3000), _coz(s["el"], 100, 1000), _coz(s["az"], 100),
                _coz(s["dni"], 10), _coz(s["dhi"], 10), _coz(s["ghi"], 10), binalar, trafolar, D["meta"])
