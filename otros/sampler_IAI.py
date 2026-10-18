import json
import os
import time
import requests
import xml.etree.ElementTree as ET

BASE_URL = "https://sru.k10plus.de/opac-de-627"

TARGET = 10000
SCAN_SIZE = 100

OUTPUT = "k10plus_sample.jsonl"

NS = {
    "zs": "http://www.loc.gov/zing/srw/",
    "px": "info:srw/schema/5/picaXML-v1.0",
}


# -----------------------------------------------------
# SCAN
# -----------------------------------------------------

def scan_ppns(start):

    params = {
        "version": "1.1",
        "operation": "scan",
        "scanClause": f"pica.ppn={start}",
        "maximumTerms": SCAN_SIZE,
    }

    r = requests.get(BASE_URL, params=params, timeout=60)
    r.raise_for_status()

    root = ET.fromstring(r.text)

    ppns = []

    for term in root.findall(".//zs:term", NS):
        value = term.find("zs:value", NS)

        if value is not None:
            ppns.append(value.text)

    return ppns


# -----------------------------------------------------
# DOWNLOAD
# -----------------------------------------------------

def download_record(ppn):

    params = {
        "version": "1.1",
        "operation": "searchRetrieve",
        "query": f"pica.ppn={ppn}",
        "maximumRecords": 1,
        "recordSchema": "picaxml",
    }

    r = requests.get(BASE_URL, params=params, timeout=60)

    if "<recordData>" not in r.text:
        return None

    return r.text


# -----------------------------------------------------
# XML -> DICT
# -----------------------------------------------------

def parse_record(xml_text):

    root = ET.fromstring(xml_text)

    result = {}

    for field in root.iter():

        if not field.tag.endswith("datafield"):
            continue

        tag = field.attrib["tag"]

        values = {}

        for sf in field:

            if not sf.tag.endswith("subfield"):
                continue

            code = sf.attrib["code"]

            values.setdefault(code, []).append(sf.text)

        result.setdefault(tag, []).append(values)

    return result if result else None

# -----------------------------------------------------
# MAIN
# -----------------------------------------------------

last = "0"
saved = 0

with open(OUTPUT, "w", encoding="utf8") as out:

    while saved < TARGET:

        print(f"\nSCAN desde {last}")

        ppns = scan_ppns(last)

        print("PPNs encontrados:", len(ppns))
        print(ppns[:10])

        if len(ppns) <= 1:
            print("Fin del índice.")
            break

        for ppn in ppns[1:]:

            xml = download_record(ppn)

            if xml is None:
                continue

            record = parse_record(xml)

            if record is None:
                continue

            record["_ppn"] = ppn

            out.write(json.dumps(record, ensure_ascii=False))
            out.write("\n")

            saved += 1
            last = ppn

            if saved % 100 == 0:
                print(saved)

            if saved >= TARGET:
                break

            time.sleep(0.1)

print(f"\nTerminados: {saved}")