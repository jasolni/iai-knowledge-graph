"""
k10plus_sru_harvester.py

Queries the K10plus SRU endpoint for the database of the Ibero-Amerikanisches
Institut Berlin (IAI, ISIL DE-204) using a seed list of
literary works, and saves the resulting MARCXML records as local
fixtures, together with a coverage manifest (found / not found /
error) that serves as direct input for the analysis of sources
of the project.

Base endpoint:
    http://sru.k10plus.de/opac-de-204

Protocol:
    SRU 1.1 (Search/Retrieve via URL), with queries in CQL
    (Contextual Query Language) over PICA indexes:
        pica.tit  -> title
        pica.per  -> author / person
        pica.isb  -> ISBN
        pica.all  -> all fields

Usage:
    pip install requests lxml
    python k10plus_sru_harvester.py

Note: this script requires internet access to run; it could not be
tested in the generation environment because it had no network access, so
it should be run and the resulting manifest reviewed on your machine
before being taken as good.
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
# Configuration
# --------------------------------------------------------------------------

SRU_BASE_URL = "http://sru.k10plus.de/opac-de-204"  # ISIL DE-204 = IAI Berlin
OUTPUT_DIR = Path("fixtures/iai_marcxml")
MANIFEST_PATH = Path("fixtures/iai_manifest.json")
REQUEST_DELAY_SECONDS = 1.0  # courtesy toward the public service, avoids overloading it
MAX_RECORDS_PER_QUERY = 5    # margin for variants/editions of the same title
REQUEST_TIMEOUT_SECONDS = 15

SRU_NAMESPACES = {"sru": "http://www.loc.gov/zing/srw/"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Seed of works (title + author, used to disambiguate the search).
# Replace this list with your final set of 10-15 works.
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
# Building and running SRU queries
# --------------------------------------------------------------------------

def build_cql_query(title: str, author: Optional[str] = None) -> str:
    """Builds a CQL query over the K10plus PICA indexes."""
    query = f'pica.tit="{title}"'
    if author:
        query += f' and pica.per="{author}"'
    return query


def fetch_sru_response(cql_query: str, max_records: int = MAX_RECORDS_PER_QUERY) -> tuple[str, str]:
    """
    Runs the SRU query and returns (xml_text, full_url).
    `requests` is left to build and escape the query string, to avoid
    manual encoding errors with quotes and spaces.
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
    """Extracts <numberOfRecords> from the SRU response."""
    root = etree.fromstring(xml_text.encode("utf-8"))
    node = root.find(".//sru:numberOfRecords", SRU_NAMESPACES)
    return int(node.text) if node is not None and node.text else 0


def parse_diagnostics(xml_text: str) -> Optional[str]:
    """
    If the server returns a diagnostic (e.g. invalid CQL) instead of
    results, extracts it so it can be logged in the manifest.
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
# Main process
# --------------------------------------------------------------------------

def harvest_seed_works(seed_works: list[dict]) -> list[dict]:
    """
    Iterates over the seed list, queries K10plus SRU for each work, saves
    the resulting MARCXML as a fixture and returns a manifest with the
    result of each query.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    for i, work in enumerate(seed_works, start=1):
        title = work["title"]
        author = work.get("author")
        cql_query = build_cql_query(title, author)

        logger.info("[%d/%d] Querying: %s (%s)", i, len(seed_works), title, author)

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
                logger.warning("  -> Server diagnostic: %s", diagnostic)
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
                logger.info("  -> %d record(s) saved to %s", number_of_records, filepath)
            else:
                entry["status"] = "not_found"
                logger.warning("  -> No results in the IAI catalog")

        except requests.RequestException as exc:
            entry["status"] = "error"
            entry["error"] = str(exc)
            logger.error("  -> Network error: %s", exc)

        except etree.XMLSyntaxError as exc:
            entry["status"] = "parse_error"
            entry["error"] = str(exc)
            logger.error("  -> Error parsing the XML response: %s", exc)

        manifest.append(entry)
        time.sleep(REQUEST_DELAY_SECONDS)  # courtesy toward the public endpoint

    return manifest


def save_manifest(manifest: list[dict]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Manifest saved to %s", MANIFEST_PATH)


def print_coverage_summary(manifest: list[dict]) -> None:
    found = sum(1 for e in manifest if e["status"] == "found")
    not_found = sum(1 for e in manifest if e["status"] == "not_found")
    errors = sum(1 for e in manifest if e["status"] in ("error", "parse_error", "diagnostic"))

    print("\n--- IAI catalog coverage summary ---")
    print(f"Total queried    : {len(manifest)}")
    print(f"Found            : {found}")
    print(f"Not found        : {not_found}")
    print(f"Errors/diag.     : {errors}")
    print("---------------------------------------------------\n")


if __name__ == "__main__":
    results = harvest_seed_works(SEED_WORKS)
    save_manifest(results)
    print_coverage_summary(results)
