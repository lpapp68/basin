#!/usr/bin/env python3
"""
frissit.py — a tanúsítvány-készlet frissítése.

MIÉRT
A www.vizugy.hu és a hydroinfo.hu a magyar Microsec e-Szignó hitelesítőt
használja. A szerver a köztes tanúsítványokat küldi, a gyökeret nem — azt
sosem küldik a láncban. A gyökér a macOS rendszerkészletében megvan, a bot
Linux-futóján nincs, ezért ott a hitelesítés elhasal.

A megoldás egy egyesített készlet: a Mozilla gyökerek (certifi) plusz a
szerverektől letöltött magyar lánc.

MIKOR KELL FUTTATNI
Ha a tanúsítványok lejárnak. Jel: CERTIFICATE_VERIFY_FAILED a naplóban.
2026-09-12-én a data.vizugy.hu tanúsítványa lejárt — az OVF oldalán —, és
a tárolt lánc is elavult volt.

Futtatás:  python tanusitvanyok/frissit.py
"""

import pathlib
import ssl
import subprocess
import sys

HOSZTOK = ("www.vizugy.hu", "hydroinfo.hu", "data.vizugy.hu")
ITT = pathlib.Path(__file__).parent


def lanc(hoszt):
    """A szerver által küldött tanúsítványlánc PEM-ben."""
    p = subprocess.run(
        ["openssl", "s_client", "-connect", f"{hoszt}:443",
         "-servername", hoszt, "-showcerts"],
        input="", capture_output=True, text=True, timeout=30)
    ki, benn = [], False
    for sor in p.stdout.split("\n"):
        if "BEGIN CERTIFICATE" in sor:
            benn = True
        if benn:
            ki.append(sor)
        if "END CERTIFICATE" in sor:
            benn = False
    return "\n".join(ki)


def main():
    darabok = []
    for h in HOSZTOK:
        try:
            l = lanc(h)
            if l.count("BEGIN CERT"):
                darabok.append(f"# {h}\n{l}")
                sys.stdout.write(f"  {h}: {l.count('BEGIN CERT')} tanúsítvány\n")
            else:
                sys.stdout.write(f"  {h}: nem adott láncot\n")
        except Exception as e:
            sys.stdout.write(f"  {h}: {e}\n")

    if not darabok:
        raise SystemExit("Egyetlen szervertől sem jött lánc.")

    try:
        import certifi
        gyokerek = pathlib.Path(certifi.where()).read_text(encoding="utf-8")
    except ImportError:
        raise SystemExit("A certifi csomag kell hozzá: pip install certifi")

    fej = ("# Egyesített tanúsítvány-készlet a basin projekthez.\n"
           "# certifi (Mozilla gyökerek) + a magyar Microsec e-Szignó lánc,\n"
           "# amit a www.vizugy.hu és a hydroinfo.hu használ. A szerver a\n"
           "# köztes elemeket küldi, a gyökeret nem — ezért kell mindkettő.\n"
           "# Frissítés: python tanusitvanyok/frissit.py\n\n")
    cel = ITT / "ca-bundle.pem"
    cel.write_text(fej + gyokerek + "\n" + "\n".join(darabok), encoding="utf-8")

    # Ellenőrzés: tényleg hitelesíthető-e vele a két fő szerver?
    import urllib.request
    ctx = ssl.create_default_context(cafile=str(cel))
    fej_ua = {"User-Agent": "equora-basin/2.6"}
    for h in ("www.vizugy.hu", "hydroinfo.hu"):
        try:
            urllib.request.urlopen(
                urllib.request.Request(f"https://{h}/", headers=fej_ua),
                timeout=20, context=ctx)
            sys.stdout.write(f"  ellenőrzés {h}: OK\n")
        except Exception as e:
            sys.stdout.write(f"  ellenőrzés {h}: HIBA — {str(e)[:60]}\n")

    kb = cel.stat().st_size / 1024
    sys.stdout.write(f"\nca-bundle.pem kész: {kb:.0f} KB\n")


if __name__ == "__main__":
    main()
