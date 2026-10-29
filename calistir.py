"""Bütün senaryoları çalıştırır, tablo yazar, CSV ve grafik kaydeder.

Kullanım:  python calistir.py            (sonuçlar 'cikti' klasörüne)
"""
import time
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from trafo_ges import yukle, Model, Ayarlar
from trafo_ges.sebeke import KABLO

CIKTI = Path(__file__).parent / "cikti"; CIKTI.mkdir(exist_ok=True)
SENARYOLAR = {"Bugün": "bugun", "2030": "2030", "2035": "2035", "2035 + akıllı şarj": "2035_akilli", "Hızlı dönüşüm (stres)": "stres"}


def main():
    v = yukle(); m = Model(v)
    print(f"{len(v.binalar)} bina, {len(v.trafolar)} trafo noktası yüklendi.\n")
    ozet, detay = [], []
    for ad, kod in SENARYOLAR.items():
        S = Ayarlar.senaryo(kod); t0 = time.time()
        r = m.simule(S); dt = time.time() - t0
        sl = r["siteler"]
        lp = sum(x["lp"]["kwp"] for x in r["tahsis"].values()); gr = sum(x["sezgisel"]["kwp"] for x in r["tahsis"].values())
        lpk = sum(x["lp"]["kwh"] for x in r["tahsis"].values()); grk = sum(x["sezgisel"]["kwh"] for x in r["tahsis"].values())
        ozet.append(dict(senaryo=ad, ges_payi=S.ges, ev_payi=S.ev, isi_pompasi=S.isi, akilli_sarj=S.akilli,
                         asan_trafo=r["asan"], trafo=len(sl), gerilim_asan=sum((s["vmax"] > 1 + S.gerilim_bandi) or (s["vmin"] < 1 - S.gerilim_bandi) for s in sl),
                         kalan_ges_kwp=round(sum(s["hc"] for s in sl)), dp_kwp=round(lp), sezgisel_kwp=round(gr),
                         dp_mwh=round(lpk / 1e3), sezgisel_mwh=round(grk / 1e3), sure_s=round(dt, 1)))
        for s in sl:
            detay.append(dict(senaryo=ad, trafo=s["id"], kva=s["kva"], bina=len(s["b"]), hane=round(s["hane"]), durum=s["durum"],
                              tepe_yuk_yuzde=round(100 * s["ileri"]), ters_akis_yuzde=round(100 * s["ters"]),
                              gerilim_min=round(100 * s["vmin"], 1), gerilim_max=round(100 * s["vmax"], 1),
                              kalan_ges_termik=round(s["hcT"]), kalan_ges_gerilim=round(min(s["hcV"], 99999)),
                              dp_kwp=round(r["tahsis"][s["id"]]["lp"]["kwp"]), sezgisel_kwp=round(r["tahsis"][s["id"]]["sezgisel"]["kwp"])))
            if s["ileri"] > 1 or s["ters"] > S.lim:
                c = m.cozum_ara(s, S); detay[-1].update(gereken_batarya_kwh=c["batarya_kwh"], yeni_kva=c["yeni_kva"])
        if kod == "2035":
            ciz_gun(sl, S, m)
    oz = pd.DataFrame(ozet); dt_ = pd.DataFrame(detay)
    oz.to_csv(CIKTI / "senaryo_ozeti.csv", index=False); dt_.to_csv(CIKTI / "trafo_sonuclari.csv", index=False)
    pd.set_option("display.width", 200)
    print(oz[["senaryo", "asan_trafo", "trafo", "gerilim_asan", "kalan_ges_kwp", "dp_kwp", "sezgisel_kwp", "sure_s"]].to_string(index=False))
    print(f"\nCSV ve grafikler: {CIKTI}")


def ciz_gun(siteler, S, m):
    """2035 senaryosunda bölgenin yaz ve kış günü: tüketim bileşenleri ve GES."""
    L = sum(s["LB"] for s in siteler); EV = sum(s["LEV"] for s in siteler); HP = sum(s["LHP"] for s in siteler); PV = sum(s["PV"] for s in siteler)
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6), sharey=True)
    for a, (bas, ad) in zip(ax, [(195 * 24, "15 Temmuz"), (14 * 24, "15 Ocak")]):
        h = np.arange(24); sl = slice(bas, bas + 24)
        a.stackplot(h, L[sl], EV[sl], HP[sl], labels=["Bina", "Araç şarjı", "Isı pompası"], alpha=.8)
        a.plot(h, PV[sl], color="#d99a06", lw=2, label="Çatı GES"); a.set_title(f"2035 · {ad}"); a.set_xlabel("saat")
    ax[0].set_ylabel("kW"); ax[1].legend(loc="upper left", fontsize=8); fig.tight_layout(); fig.savefig(CIKTI / "2035_gunluk_profil.png", dpi=150)
    worst = max(siteler, key=lambda s: 1 - s["vmin"])
    t = worst["tmin"]; A = worst["agac"]
    fig, a = plt.subplots(figsize=(6, 3.4))
    for i, b in enumerate(A["dugum"]):
        p = A["par"][i]; x0 = A["Lp"][p] * 1000 if p >= 0 else 0; y0 = worst["V"][p, t] * 100 if p >= 0 else S.trafo_gerilim * 100
        a.plot([x0, A["Lp"][i] * 1000], [y0, worst["V"][i, t] * 100], color=f"C{A['f'][i]}", lw=1)
    a.axhline(100 * (1 - S.gerilim_bandi), color="r", ls="--"); a.set_xlabel("trafodan kablo uzunluğu (m)"); a.set_ylabel("gerilim (%)")
    a.set_title(f"{worst['id']} besleyici gerilim profili (en düşük saat)"); fig.tight_layout(); fig.savefig(CIKTI / "2035_gerilim_profili.png", dpi=150)


if __name__ == "__main__":
    main()
