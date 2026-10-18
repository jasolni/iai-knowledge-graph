import json
import time
import requests
from lxml import etree

BASE_URL = "https://sru.k10plus.de/opac-de-627"

HEADERS = {
    "User-Agent": "Python K10plus crawler"
}

MAX_RECORDS = 100          # máximo permitido por petición
PAUSA = 0.3                # segundos entre peticiones


def record_to_dict(record):

    ns = {"p": "info:srw/schema/5/picaXML-v1.0"}

    salida = {}

    for campo in record.findall("p:datafield", ns):

        tag = campo.attrib["tag"]

        valores = {}

        for sub in campo.findall("p:subfield", ns):

            codigo = sub.attrib["code"]

            texto = sub.text if sub.text else ""

            valores.setdefault(codigo, []).append(texto)

        salida.setdefault(tag, []).append(valores)

    return salida


def descargar_anio(anio):

    print(f"\n========== {anio} ==========")

    registros = []

    start = 1

    while True:

        params = {
            "version": "1.1",
            "operation": "searchRetrieve",
            "query": f"pica.jhr={anio}",
            "recordSchema": "picaxml",
            "maximumRecords": MAX_RECORDS,
            "startRecord": start
        }

        r = requests.get(BASE_URL,
                         params=params,
                         headers=HEADERS,
                         timeout=60)

        r.raise_for_status()

        raiz = etree.fromstring(r.content)

        ns = {
            "zs": "http://www.loc.gov/zing/srw/",
            "p": "info:srw/schema/5/picaXML-v1.0"
        }

        if start == 1:

            total = int(
                raiz.findtext(".//zs:numberOfRecords",
                              namespaces=ns)
            )

            print(f"Total registros: {total}")

            if total == 0:
                return

        records = raiz.findall(".//p:record", ns)

        if not records:
            break

        for rec in records:

            registros.append(record_to_dict(rec))

        print(f"Descargados {len(registros)} registros", end="\r")

        start += MAX_RECORDS

        if start > total:
            break

        time.sleep(PAUSA)

    with open(f"{anio}.json",
              "w",
              encoding="utf8") as f:

        json.dump(registros,
                  f,
                  ensure_ascii=False,
                  indent=2)

    print(f"\nGuardado {anio}.json")


def main():

    for anio in range(1960, 1962):

        try:

            descargar_anio(anio)

        except Exception as e:

            print(f"\nError en {anio}: {e}")


if __name__ == "__main__":
    main()