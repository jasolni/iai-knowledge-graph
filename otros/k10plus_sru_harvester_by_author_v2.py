"""
k10plus_sru_harvester_by_author.py

Consulta el endpoint SRU de K10plus (catálogo del IAI, ISIL DE-204) por
AUTOR en vez de por obra concreta, con paginación para traer más de un
puñado de registros por autor, y guarda los MARCXML resultantes como
fixtures + un manifiesto de cobertura.

Cambios respecto a la versión anterior (por obra):
  - Query por pica.per (autor) en vez de pica.tit+pica.per (título+autor).
  - Paginación real vía startRecord, con un tope de seguridad por autor
    (MAX_RECORDS_PER_AUTHOR) para no traer cientos de registros de autores
    muy prolíficos.
  - Preview legible (título/autor) extraído del MARCXML tras cada consulta,
    para confirmar de un vistazo que los metadatos sí llegaron.

Uso:
    pip install requests lxml
    python k10plus_sru_harvester_by_author.py
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests
from lxml import etree

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------

SRU_BASE_URL = "http://sru.k10plus.de/opac-de-204"  # ISIL DE-204 = IAI Berlín
OUTPUT_DIR = Path("fixtures/iai_marcxml_by_author")
MANIFEST_PATH = Path("fixtures/iai_manifest_by_author.json")

REQUEST_DELAY_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 15
PAGE_SIZE = 20                 # registros por página SRU
MAX_RECORDS_PER_AUTHOR = 100   # tope de seguridad total por autor
PREVIEW_ITEMS_PER_AUTHOR = 3   # cuántos títulos mostrar como preview en consola

MARC_NS = {"marc": "http://www.loc.gov/MARC21/slim"}
SRU_NS = {"sru": "http://www.loc.gov/zing/srw/"}
DIAG_NS = {"diag": "http://www.loc.gov/zing/srw/diagnostic/"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Semilla de autores — Boom latinoamericano + precursores/relacionados
# directos. Formato "Apellido, Nombre" (forma de autoridad habitual en PICA).
# --------------------------------------------------------------------------

AUTHOR_SEED: list[dict] = [
    {"name": "García Márquez, Gabriel", "country": "Colombia"},
    {"name": "Vargas Llosa, Mario", "country": "Peru"},
    {"name": "Cortázar, Julio", "country": "Argentina"},
    {"name": "Fuentes, Carlos", "country": "México"},
    {"name": "Rulfo, Juan", "country": "México"},          # precursor
    {"name": "Donoso, José", "country": "Chile"},
    {"name": "Puig, Manuel", "country": "Argentina"},
    {"name": "Carpentier, Alejo", "country": "Cuba"},      # precursor
    {"name": "Onetti, Juan Carlos", "country": "Uruguay"}, # precursor
    {"name": "Garro, Elena", "country": "México"},
    {"name": "Castellanos, Rosario", "country": "México"},
    {"name": "Lispector, Clarice", "country": "Brazil"}       
]


# --------------------------------------------------------------------------
# Construcción y ejecución de consultas SRU
# --------------------------------------------------------------------------

def build_cql_query(author: str) -> str:
    return f'pica.per="{author}"'


def fetch_sru_page(cql_query: str, start_record: int, max_records: int) -> tuple[str, str]:
    params = {
        "version": "1.1",
        "operation": "searchRetrieve",
        "query": cql_query,
        "startRecord": str(start_record),
        "maximumRecords": str(max_records),
        "recordSchema": "marcxml",
    }
    response = requests.get(SRU_BASE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    # OJO: NO usar response.text aquí. Cuando el servidor responde con
    # Content-Type: text/xml sin charset explícito, requests asume Latin-1
    # por defecto (RFC 2616) aunque el contenido real sea UTF-8 -- que es
    # el caso de K10plus. Eso produce mojibake silencioso (p.ej. "Carrión"
    # -> "CarriÃ³n") que luego queda grabado en el fixture. Decodificamos
    # los bytes crudos como UTF-8 explícitamente, que es lo que el propio
    # MARCXML declara en su cabecera.
    xml_text = response.content.decode("utf-8")
    return xml_text, response.url


def parse_number_of_records(xml_text: str) -> int:
    root = etree.fromstring(xml_text.encode("utf-8"))
    node = root.find(".//sru:numberOfRecords", SRU_NS)
    return int(node.text) if node is not None and node.text else 0


def parse_diagnostics(xml_text: str) -> Optional[str]:
    root = etree.fromstring(xml_text.encode("utf-8"))
    message = root.find(".//diag:message", DIAG_NS)
    return message.text if message is not None else None


def extract_preview(xml_text: str, limit: int = PREVIEW_ITEMS_PER_AUTHOR) -> list[str]:
    """
    Extrae un preview legible (autor - título) de los registros MARC de la
    página, para confirmar visualmente que los metadatos sí llegan.
    """
    root = etree.fromstring(xml_text.encode("utf-8"))
    records = root.findall(".//marc:record", MARC_NS)
    previews = []

    for record in records[:limit]:
        title_node = record.find('.//marc:datafield[@tag="245"]/marc:subfield[@code="a"]', MARC_NS)
        author_node = record.find('.//marc:datafield[@tag="100"]/marc:subfield[@code="a"]', MARC_NS)

        title = title_node.text.strip() if title_node is not None and title_node.text else "(sin título)"
        author = author_node.text.strip() if author_node is not None and author_node.text else "(sin autor en 100)"
        previews.append(f"{author} — {title}")

    return previews


def slugify(text: str) -> str:
    replacements = {
        " ": "_", ",": "", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "Brazil": "Brasil",
    }
    slug = text.lower()
    for src, dst in replacements.items():
        slug = slug.replace(src, dst)
    return slug.strip("_")


# --------------------------------------------------------------------------
# Proceso principal
# --------------------------------------------------------------------------

def harvest_author(author_entry: dict) -> dict:
    author_name = author_entry["name"]
    cql_query = build_cql_query(author_name)
    author_dir = OUTPUT_DIR / slugify(author_name)

    entry = {
        "author": author_name,
        "country": author_entry.get("country"),
        "cql_query": cql_query,
        "status": None,
        "number_of_records_total": 0,
        "number_of_records_retrieved": 0,
        "fixture_files": [],
        "preview": [],
    }

    start_record = 1
    retrieved = 0

    while retrieved < MAX_RECORDS_PER_AUTHOR:
        try:
            xml_text, full_url = fetch_sru_page(cql_query, start_record, PAGE_SIZE)
        except requests.RequestException as exc:
            entry["status"] = "error"
            entry["error"] = str(exc)
            logger.error("  -> Error de red: %s", exc)
            break

        diagnostic = parse_diagnostics(xml_text)
        if diagnostic:
            entry["status"] = "diagnostic"
            entry["diagnostic_message"] = diagnostic
            logger.warning("  -> Diagnóstico del servidor: %s", diagnostic)
            break

        total = parse_number_of_records(xml_text)
        entry["number_of_records_total"] = total

        if total == 0:
            entry["status"] = "not_found"
            logger.warning("  -> Sin resultados para %s", author_name)
            break

        author_dir.mkdir(parents=True, exist_ok=True)
        page_filename = f"page_{start_record:04d}.xml"
        page_path = author_dir / page_filename
        page_path.write_text(xml_text, encoding="utf-8")
        entry["fixture_files"].append(str(page_path))

        if not entry["preview"]:
            entry["preview"] = extract_preview(xml_text)

        page_count = min(PAGE_SIZE, total - (start_record - 1))
        retrieved += page_count
        entry["number_of_records_retrieved"] = retrieved
        entry["status"] = "found"

        logger.info(
            "  -> página desde registro %d: %d de %d totales guardados en %s",
            start_record, retrieved, total, page_path,
        )

        if start_record + PAGE_SIZE > total:
            break  # ya no hay más páginas

        start_record += PAGE_SIZE
        time.sleep(REQUEST_DELAY_SECONDS)

    return entry


def harvest_seed_authors(authors: list[dict]) -> list[dict]:
    manifest = []
    for i, author_entry in enumerate(authors, start=1):
        logger.info("[%d/%d] Consultando autor: %s", i, len(authors), author_entry["name"])
        entry = harvest_author(author_entry)
        manifest.append(entry)

        if entry["preview"]:
            print(f"\n  Preview — {author_entry['name']}:")
            for line in entry["preview"]:
                print(f"    · {line}")

        time.sleep(REQUEST_DELAY_SECONDS)

    return manifest


def save_manifest(manifest: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Manifiesto guardado en %s", MANIFEST_PATH)


def print_coverage_summary(manifest: list[dict]) -> None:
    found = sum(1 for e in manifest if e["status"] == "found")
    not_found = sum(1 for e in manifest if e["status"] == "not_found")
    errors = sum(1 for e in manifest if e["status"] in ("error", "diagnostic"))
    total_records = sum(e["number_of_records_retrieved"] for e in manifest)

    print("\n--- Resumen de cobertura del catálogo del IAI (por autor) ---")
    print(f"Autores consultados     : {len(manifest)}")
    print(f"Con resultados          : {found}")
    print(f"Sin resultados          : {not_found}")
    print(f"Errores/diagnósticos    : {errors}")
    print(f"Registros MARC totales  : {total_records}")
    print("---------------------------------------------------------------\n")


if __name__ == "__main__":
    results = harvest_seed_authors(AUTHOR_SEED)
    save_manifest(results)
    print_coverage_summary(results)
