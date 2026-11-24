"""Importa pedidocentral.sql y ajustes.sql en una base MySQL en la nube (sin necesitar el cliente `mysql`).

Uso (desde la carpeta del proyecto):
    python database\\importar_nube.py --host HOST --port 13474 --user avnadmin --db defaultdb --ca C:\\ruta\\ca.pem

La contraseña se pide por teclado (no se ve al escribirla).
Omite DROP DATABASE / CREATE DATABASE / USE, porque en la nube la base ya existe.
"""
import argparse
import getpass
import re
import sys
from pathlib import Path

import pymysql

ARCHIVOS = ["pedidocentral.sql", "ajustes.sql"]
OMITIR = re.compile(r"^\s*(DROP\s+DATABASE|CREATE\s+DATABASE|USE)\b", re.I)


def dividir(texto):
    """Divide el script en sentencias respetando DELIMITER, comillas y comentarios."""
    sentencias, actual, delim = [], [], ";"
    i, n = 0, len(texto)
    inicio_linea = True
    while i < n:
        c = texto[i]
        # Directiva DELIMITER al comienzo de una linea (y sin sentencia a medias)
        if inicio_linea and not "".join(actual).strip():
            m = re.match(r"[ \t]*DELIMITER[ \t]+(\S+)[ \t]*\r?\n", texto[i:], re.I)
            if m:
                delim = m.group(1)
                i += m.end()
                continue
        inicio_linea = c == "\n"
        # Comentarios
        if texto.startswith("--", i) and (i + 2 >= n or texto[i + 2] in " \t\r\n"):
            j = texto.find("\n", i)
            i = n if j == -1 else j
            continue
        if c == "#":
            j = texto.find("\n", i)
            i = n if j == -1 else j
            continue
        if texto.startswith("/*", i):
            j = texto.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        # Textos entre comillas
        if c in ("'", '"', "`"):
            j = i + 1
            while j < n:
                if texto[j] == "\\" and c != "`":
                    j += 2
                    continue
                if texto[j] == c:
                    if j + 1 < n and texto[j + 1] == c:  # comilla doble escapada
                        j += 2
                        continue
                    break
                j += 1
            actual.append(texto[i:j + 1])
            i = j + 1
            continue
        # Fin de sentencia
        if texto.startswith(delim, i):
            s = "".join(actual).strip()
            if s:
                sentencias.append(s)
            actual = []
            i += len(delim)
            continue
        actual.append(c)
        i += 1
    s = "".join(actual).strip()
    if s:
        sentencias.append(s)
    return sentencias


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, default=3306)
    ap.add_argument("--user", required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--ca", help="ruta al certificado ca.pem")
    ap.add_argument("--solo-contar", action="store_true", help="solo analiza los archivos, no se conecta")
    a = ap.parse_args()

    carpeta = Path(__file__).resolve().parent
    plan = []
    for nombre in ARCHIVOS:
        ruta = carpeta / nombre
        if not ruta.exists():
            sys.exit("No encuentro %s. Este script debe estar junto a los .sql, en la carpeta database." % ruta)
        sents = [s for s in dividir(ruta.read_text(encoding="utf-8")) if not OMITIR.match(s)]
        plan.append((nombre, sents))
        print("%s: %d sentencias" % (nombre, len(sents)))
    if a.solo_contar:
        return

    clave = getpass.getpass("Contraseña de la base: ")
    ssl = {"ca": a.ca} if a.ca else None
    con = pymysql.connect(host=a.host, port=a.port, user=a.user, password=clave, database=a.db,
                          charset="utf8mb4", ssl=ssl, autocommit=True)
    cur = con.cursor()
    for nombre, sents in plan:
        print("Importando %s ..." % nombre)
        for k, s in enumerate(sents, 1):
            try:
                cur.execute(s)
            except Exception as e:
                print("\nERROR en %s, sentencia %d:\n%s\n\n%s" % (nombre, k, s[:300], e))
                sys.exit(1)
    con.close()
    print("Listo: la base quedó importada.")


if __name__ == "__main__":
    main()
