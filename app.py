"""GridTwin — masaüstü uygulaması.

Aracı (arac/gridtwin.html) kendi penceresinde açar. PDF rapor butonuna basılınca
"Farklı kaydet" penceresi açılır ve rapor seçilen yere kaydedilir.
Windows'ta .exe, Mac'te .app olarak PyInstaller ile derlenir (bkz. .github/workflows/derle.yml).
"""
import base64
import os
import sys

import webview


def kaynak(yol):
    """Derlenmiş uygulamada dosyalar geçici bir klasöre açılır; onu bulur."""
    taban = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(taban, yol)


class Api:
    def kaydet(self, ad, b64):
        pencere = webview.windows[0]
        tur = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG
        yol = pencere.create_file_dialog(tur, save_filename=ad, file_types=("PDF (*.pdf)",))
        if not yol:
            return "iptal"
        if isinstance(yol, (list, tuple)):
            yol = yol[0]
        if not str(yol).lower().endswith(".pdf"):
            yol = f"{yol}.pdf"
        with open(yol, "wb") as f:
            f.write(base64.b64decode(b64))
        return "ok"


def main():
    webview.create_window(
        "GridTwin",
        url=kaynak(os.path.join("arac", "gridtwin.html")),
        js_api=Api(),
        width=1440, height=900, min_size=(900, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
