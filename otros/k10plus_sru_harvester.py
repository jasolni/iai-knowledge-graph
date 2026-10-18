"""
k10plus_sru_harvester.py

Consulta el endpoint SRU de K10plus para la base de datos del Instituto
Ibero-Americano de Berlín (IAI, ISIL DE-204) sobre una lista semilla de
obras literarias, y guarda los registros MARCXML resultantes como fixtures
locales, junto con un manifiesto de cobertura (encontrado / no encontrado /
error) que sirve de insumo directo para el análisis de fuentes
del proyecto.

Endpoint base:
    http://sru.k10plus.de/opac-de-204

Protocolo:
    SRU 1.1 (Search/Retrieve via URL), con consultas en CQL
    (Contextual Query Language) sobre índices PICA:
        pica.tit  -> título
        pica.per  -> autor / persona
        pica.isb  -> ISBN
        pica.all  -> todos los campos

Uso:
    pip install requests lxml
    python k10plus_sru_harvester.py

Nota: este script requiere acceso a internet para ejecutarse; no ha podido
probarse en el entorno de generación por no disponer de salida de red, así
que conviene ejecutarlo y revisar el manifiesto resultante en tu máquina
antes de darlo por bueno.
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
OUTPUT_DIR = Path("fixtures/iai_marcxml")
MANIFEST_PATH = Path("fixtures/iai_manifest.json")
REQUEST_DELAY_SECONDS = 1.0  # cortesía con el servicio público, evita saturarlo
MAX_RECORDS_PER_QUERY = 5    # margen para variantes/ediciones del mismo título
REQUEST_TIMEOUT_SECONDS = 15

SRU_NAMESPACES = {"sru": "http://www.loc.gov/zing/srw/"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Semilla de obras (título + autor, usado para desambiguar la búsqueda).
# Sustituye esta lista por tu conjunto final de 10-15 obras.
# --------------------------------------------------------------------------

SEED_WORKS: list[dict] = [
    {"title": "Cien años de soledad", "author": "García Márquez"},
    {"title": "La ciudad y los perros", "author": "Vargas Llosa"},
    {"title": "La casa de los espíritus", "author": "Isabel Allende"},
    {"title": "Como agua para chocolate", "author": "Laura Esquivel"},
    {"title": "El beso de la mujer araña", "author": "Manuel Puig"},
    {"title": "Doña Flor y sus dos maridos", "author": "Jorge Amado"},
    {"title": "El amor en los tiempos del cólera", "author": "García Márquez"},
    {"title": "Pedro Páramo", "author": "Juan Rulfo"},
    {"title": "La tregua", "author": "Mario Benedetti"},
    {"title": "El túnel", "author": "Ernesto Sabato"},
]


# --------------------------------------------------------------------------
# Construcción y ejecución de consultas SRU
# --------------------------------------------------------------------------

def build_cql_query(title: str, author: Optional[str] = None) -> str:
    """Construye una consulta CQL sobre los índices PICA de K10plus."""
    query = f'pica.tit="{title}"'
    if author:
        query += f' and pica.per="{author}"'
    return query


def fetch_sru_response(cql_query: str, max_records: int = MAX_RECORDS_PER_QUERY) -> tuple[str, str]:
    """
    Ejecuta la consulta SRU y devuelve (texto_xml, url_completa).
    Se deja que `requests` construya y escape la query string, para evitar
    errores manuales de encoding con comillas y espacios.
    """
    params = {
        "version": "1.1",
        "operation": "searchRetrieve",
        "query": cql_query,
        "maximumRecords": str(max_records),
        "recordSchema": "marcxml",
    }
    response = requests.get(SRU_BASE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text, response.url


def parse_number_of_records(xml_text: str) -> int:
    """Extrae <numberOfRecords> de la respuesta SRU."""
    root = etree.fromstring(xml_text.encode("utf-8"))
    node = root.find(".//sru:numberOfRecords", SRU_NAMESPACES)
    return int(node.text) if node is not None and node.text else 0


def parse_diagnostics(xml_text: str) -> Optional[str]:
    """
    Si el servidor devuelve un diagnóstico (p.ej. CQL inválida) en vez de
    resultados, lo extrae para poder loggearlo en el manifiesto.
    """
    ns = {"diag": "http://www.loc.gov/zing/srw/diagnostic/"}
    root = etree.fromstring(xml_text.encode("utf-8"))
    message = root.find(".//diag:message", ns)
    return message.text if message is not None else None


def slugify(text: str) -> str:
    replacements = {
        " ": "_", "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
    }
    slug = text.lower()
    for src, dst in replacements.items():
        slug = slug.replace(src, dst)
    return slug.strip("_")


# --------------------------------------------------------------------------
# Proceso principal
# --------------------------------------------------------------------------

def harvest_seed_works(seed_works: list[dict]) -> list[dict]:
    """
    Recorre la lista semilla, consulta K10plus SRU para cada obra, guarda
    el MARCXML resultante como fixture y devuelve un manifiesto con el
    resultado de cada consulta.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    for i, work in enumerate(seed_works, start=1):
        title = work["title"]
        author = work.get("author")
        cql_query = build_cql_query(title, author)

        logger.info("[%d/%d] Consultando: %s (%s)", i, len(seed_works), title, author)

        entry = {
            "title": title,
            "author": author,
            "cql_query": cql_query,
            "status": None,
            "number_of_records": 0,
            "fixture_file": None,
        }

        try:
            xml_text, full_url = fetch_sru_response(cql_query)
            entry["queried_url"] = full_url

            diagnostic = parse_diagnostics(xml_text)
            if diagnostic:
                entry["status"] = "diagnostic"
                entry["diagnostic_message"] = diagnostic
                logger.warning("  -> Diagnóstico del servidor: %s", diagnostic)
                manifest.append(entry)
                time.sleep(REQUEST_DELAY_SECONDS)
                continue

            number_of_records = parse_number_of_records(xml_text)
            entry["number_of_records"] = number_of_records

            if number_of_records > 0:
                filename = f"{i:02d}_{slugify(title)}.xml"
                filepath = OUTPUT_DIR / filename
                filepath.write_text(xml_text, encoding="utf-8")
                entry["status"] = "found"
                entry["fixture_file"] = str(filepath)
                logger.info("  -> %d registro(s) guardado(s) en %s", number_of_records, filepath)
            else:
                entry["status"] = "not_found"
                logger.warning("  -> Sin resultados en el catálogo del IAI")

        except requests.RequestException as exc:
            entry["status"] = "error"
            entry["error"] = str(exc)
            logger.error("  -> Error de red: %s", exc)

        except etree.XMLSyntaxError as exc:
            entry["status"] = "parse_error"
            entry["error"] = str(exc)
            logger.error("  -> Error al parsear la respuesta XML: %s", exc)

        manifest.append(entry)
        time.sleep(REQUEST_DELAY_SECONDS)  # cortesía con el endpoint público

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
    errors = sum(1 for e in manifest if e["status"] in ("error", "parse_error", "diagnostic"))

    print("\n--- Resumen de cobertura del catálogo del IAI ---")
    print(f"Total consultado : {len(manifest)}")
    print(f"Encontrados      : {found}")
    print(f"No encontrados   : {not_found}")
    print(f"Errores/diag.    : {errors}")
    print("---------------------------------------------------\n")


if __name__ == "__main__":
    results = harvest_seed_works(SEED_WORKS)
    save_manifest(results)
    print_coverage_summary(results)
