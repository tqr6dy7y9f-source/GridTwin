"""Kontrol testleri: Python sürümü web aracıyla aynı sonuçları veriyor mu?"""
from trafo_ges import yukle, Model, Ayarlar
from trafo_ges.ekonomi import Ekonomi, bina_yatirimi

v = yukle(); m = Model(v)
beklenen = {"bugun": 0, "2030": 0, "2035": 1, "2035_akilli": 0, "stres": 7}
for kod, asan in beklenen.items():
    r = m.simule(Ayarlar.senaryo(kod))
    assert r["asan"] == asan, (kod, r["asan"])
    print(f"✓ {kod}: sınırı aşan trafo {r['asan']} / {len(r['siteler'])}")

S = Ayarlar.senaryo("bugun"); m.gunes.kalibre(S)
b = next(x for x in v.binalar if x.id == 919744582)
e = bina_yatirimi(b, m, S, Ekonomi())
assert abs(e["geri_odeme_yil"] - 6.7) < 0.05 and abs(e["daire_basi_yatirim"] - 35979) < 50
print(f"✓ örnek bina: geri ödeme {e['geri_odeme_yil']:.1f} yıl, daire başı yatırım {e['daire_basi_yatirim']:,.0f} TL")
print("Bütün kontroller geçti.")
