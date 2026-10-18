"""
marc_to_rdf_converter_v2.py

Versión ampliada de marc_to_rdf_converter.py que añade dos distinciones
que el v1 no hacía:

  1. TIPO/FORMA del recurso (libro, artículo académico, tesis, estudio
     crítico...) a partir de señales MARC explícitas: 502 (nota de tesis),
     773 (indica artículo/capítulo dentro de otra publicación), 655
     (género/forma) y el Leader (nivel bibliográfico).

  2. Eje AUTORÍA vs. "TRATA SOBRE": el campo 600 (materia-nombre de
     persona) ahora genera un nodo de PERSONA (el mismo URI que usarías
     para esa persona como autor en 100/700), enlazado vía schema:about
     -- en vez de tratarlo como una materia genérica más. Esto permite
     preguntar "todo lo relacionado con García Márquez, sea de su autoría
     o sea sobre él" en una sola consulta SPARQL.

Guía de campos MARC 21 usada como referencia:
    https://www.loc.gov/marc/bibliographic/bd600.html  (materia-persona)
    https://www.loc.gov/marc/bibliographic/bd502.html  (nota de tesis)
    https://www.loc.gov/marc/bibliographic/bd773.html  (registro de ítem
                                                          fuente / artículo)
    https://www.loc.gov/marc/bibliographic/bd655.html  (género/forma)
    https://www.loc.gov/marc/bibliographic/bdleader.html

Uso:
    pip install pymarc rdflib lxml
    python marc_to_rdf_converter_v2.py

Nota importante: la clasificación de tipo (classify_resource_type) es una
heurística de mejor esfuerzo, no un clasificador determinista -- el
vocabulario de género/forma (655) varía entre idiomas de catalogación
(español, alemán, portugués en el caso del IAI), así que conviene
documentar esto como supuesto/limitación en la documentación del proyecto, no darlo
por una clasificación perfecta.
"""

from __future__ import annotations

import glob
from io import BytesIO
from pathlib import Path
from typing import Optional

import pymarc
from lxml import etree
from rdflib import RDF, Graph, Literal, Namespace
from rdflib.namespace import RDFS, XSD

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------

FIXTURES_GLOB = "fixtures/iai_marcxml_by_author/*/page_*.xml"
OUTPUT_TTL_PATH = Path("fixtures/iai_graph_v2.ttl")

MARC_NS = {"marc": "http://www.loc.gov/MARC21/slim"}

EX = Namespace("http://example.org/kg/")
SCHEMA = Namespace("http://schema.org/")

RELATOR_TO_SCHEMA_PROPERTY = {
    "trl": SCHEMA.translator, "translator": SCHEMA.translator,
    "ill": SCHEMA.illustrator, "illustrator": SCHEMA.illustrator,
    "edt": SCHEMA.editor, "editor": SCHEMA.editor,
    "aut": SCHEMA.author, "author": SCHEMA.author,
}


# --------------------------------------------------------------------------
# Paso 0: bootstrap de las clases propias (extensión mínima sobre Schema.org)
# Se definen aquí, no como constantes de módulo, para no ejecutar código de
# grafo en tiempo de import.
# --------------------------------------------------------------------------

def bootstrap_ontology(graph: Graph) -> None:
    for cls in (EX.AcademicThesis, EX.CriticalStudy, EX.Biography):
        graph.add((cls, RDF.type, RDFS.Class))
        graph.add((cls, RDFS.subClassOf, SCHEMA.CreativeWork))


# --------------------------------------------------------------------------
# Paso 1: extraer registros pymarc individuales (igual que en v1)
# --------------------------------------------------------------------------

def extract_marc_records_from_sru_file(filepath: Path) -> list[pymarc.Record]:
    tree = etree.parse(str(filepath))
    marc_record_elements = tree.findall(".//marc:record", MARC_NS)

    records: list[pymarc.Record] = []
    for elem in marc_record_elements:
        record_xml = etree.tostring(elem)
        collection_xml = (
            b'<collection xmlns="http://www.loc.gov/MARC21/slim">'
            + record_xml
            + b"</collection>"
        )
        parsed = pymarc.parse_xml_to_array(BytesIO(collection_xml))
        records.extend(parsed)

    return records


def get_subfield(field, code):
    if field is None:
        return None
    values = field.get_subfields(code)
    return values[0].strip() if values else None


def get_field(record, tag):
    """
    Acceso seguro a un campo MARC por etiqueta. En esta versión de pymarc,
    record["TAG"] lanza KeyError si el campo no existe (en vez de devolver
    None), igual que le pasaba a field["code"] con get_subfield(). Usamos
    record.get_fields(tag), que siempre devuelve una lista -- vacía si no
    hay coincidencia, nunca lanza excepción -- y tomamos el primer campo.
    """
    fields = record.get_fields(tag)
    return fields[0] if fields else None


# --------------------------------------------------------------------------
# Paso 2: extracción rica, ahora con 502, 600, 655, 773 añadidos
# --------------------------------------------------------------------------

def marc_record_to_dict(record: pymarc.Record) -> dict:
    data: dict = {}

    control_field = get_field(record, "001")
    data["control_number"] = control_field.data if control_field else None
    data["isbn"] = [get_subfield(f, "a") for f in record.get_fields("020") if get_subfield(f, "a")]
    data["issn"] = [get_subfield(f, "a") for f in record.get_fields("022") if get_subfield(f, "a")]
    data["language"] = get_subfield(get_field(record, "041"), "a")

    main_field = get_field(record, "100")
    data["main_author"] = None
    if main_field:
        data["main_author"] = {
            "name": get_subfield(main_field, "a"),
            "dates": get_subfield(main_field, "d"),
        }

    title_field = get_field(record, "245")
    data["title"] = get_subfield(title_field, "a")
    data["subtitle"] = get_subfield(title_field, "b")

    data["edition"] = get_subfield(get_field(record, "250"), "a")

    pub_field = get_field(record, "264") or get_field(record, "260")
    data["publisher"] = get_subfield(pub_field, "b")
    data["publication_date"] = get_subfield(pub_field, "c")

    data["physical_description"] = get_subfield(get_field(record, "300"), "a")
    data["summary"] = get_subfield(get_field(record, "520"), "a")

    # --- Contribuidores con rol (700) ---
    contributors = []
    for f in record.get_fields("700"):
        name = get_subfield(f, "a")
        if name:
            contributors.append({
                "name": name,
                "dates": get_subfield(f, "d"),
                "relator": get_subfield(f, "4") or get_subfield(f, "e"),
            })
    data["contributors"] = contributors

    # --- Materias NO personales (650 tema, 651 lugar) -> DefinedTerm ---
    topical_subjects = []
    for tag in ("650", "651"):
        for f in record.get_fields(tag):
            label = get_subfield(f, "a")
            if label:
                topical_subjects.append(label)
    data["topical_subjects"] = topical_subjects

    # --- 600: materia-PERSONA -> distinta de las anteriores a propósito.
    # Esto es lo que permite decir "este libro trata SOBRE Fulano", en vez
    # de tratarlo como una materia genérica más.
    subject_persons = []
    for f in record.get_fields("600"):
        name = get_subfield(f, "a")
        if name:
            subject_persons.append({"name": name, "dates": get_subfield(f, "d")})
    data["subject_persons"] = subject_persons

    # --- 655: género/forma (novela, ensayo, biografía...) ---
    # Vocabulario heterogéneo entre idiomas de catalogación -- se guarda
    # tal cual como pista para la clasificación heurística de tipo.
    data["genre_form_terms"] = [
        get_subfield(f, "a") for f in record.get_fields("655") if get_subfield(f, "a")
    ]

    # --- 502: nota de tesis -- señal fuerte y explícita de que es una tesis ---
    data["dissertation_note"] = get_subfield(get_field(record, "502"), "a")

    # --- 773: registro de ítem fuente -- indica que ESTE registro es un
    # artículo/capítulo dentro de una publicación mayor (revista o libro).
    host_field = get_field(record, "773")
    data["host_item"] = None
    if host_field:
        data["host_item"] = {
            "title": get_subfield(host_field, "t"),
            "related_parts": get_subfield(host_field, "g"),  # p.ej. "vol. 12, no. 3, p. 45-60"
        }

    leader = str(record.leader)
    data["is_serial"] = len(leader) > 7 and leader[7] == "s"

    return data


# --------------------------------------------------------------------------
# Paso 3: clasificación heurística de tipo de recurso
# --------------------------------------------------------------------------

def classify_resource_type(data: dict) -> object:
    """
    Heurística de mejor esfuerzo basada en señales MARC explícitas.
    Orden de prioridad: señales fuertes y específicas primero (502, 773),
    luego género/forma (655, vocabulario heterogéneo), y por defecto Book.
    """
    if data.get("dissertation_note"):
        return EX.AcademicThesis

    if data.get("host_item"):
        return SCHEMA.ScholarlyArticle  # artículo dentro de revista/colectánea

    if data.get("is_serial"):
        return SCHEMA.Periodical

    genre_terms_lower = [g.lower() for g in data.get("genre_form_terms", [])]

    if any("biograf" in g for g in genre_terms_lower):
        return EX.Biography
    if any(keyword in g for g in genre_terms_lower for keyword in ("kritik", "crítica", "critique", "estudio")):
        return EX.CriticalStudy

    return SCHEMA.Book  # valor por defecto


# --------------------------------------------------------------------------
# Paso 4: mapear el diccionario a triples RDF
# --------------------------------------------------------------------------

def slugify(text: str) -> str:
    replacements = {
        " ": "_", ",": "", ".": "", "á": "a", "é": "e", "í": "i",
        "ó": "o", "ú": "u", "ñ": "n",
    }
    slug = text.lower()
    for src, dst in replacements.items():
        slug = slug.replace(src, dst)
    return slug.strip("_")


def person_node(graph: Graph, name: str, dates: Optional[str] = None) -> object:
    person_uri = EX[f"person/{slugify(name)}"]
    graph.add((person_uri, RDF.type, SCHEMA.Person))
    graph.add((person_uri, SCHEMA.name, Literal(name)))
    if dates:
        graph.add((person_uri, EX.datesNote, Literal(dates)))
    return person_uri


def record_dict_to_graph(data: dict, graph: Graph) -> None:
    if not data.get("control_number") or not data.get("title"):
        return

    work_uri = EX[f"work/{data['control_number']}"]
    resource_type = classify_resource_type(data)
    graph.add((work_uri, RDF.type, resource_type))
    graph.add((work_uri, SCHEMA.name, Literal(data["title"])))

    if data.get("subtitle"):
        graph.add((work_uri, SCHEMA.alternateName, Literal(data["subtitle"])))
    if data.get("edition"):
        graph.add((work_uri, SCHEMA.bookEdition, Literal(data["edition"])))
    if data.get("language"):
        graph.add((work_uri, SCHEMA.inLanguage, Literal(data["language"])))
    if data.get("summary"):
        graph.add((work_uri, SCHEMA.abstract, Literal(data["summary"])))
    if data.get("publication_date"):
        graph.add((work_uri, SCHEMA.datePublished, Literal(data["publication_date"])))
    if data.get("publisher"):
        publisher_uri = EX[f"organization/{slugify(data['publisher'])}"]
        graph.add((publisher_uri, RDF.type, SCHEMA.Organization))
        graph.add((publisher_uri, SCHEMA.name, Literal(data["publisher"])))
        graph.add((work_uri, SCHEMA.publisher, publisher_uri))

    for isbn in data.get("isbn", []):
        graph.add((work_uri, SCHEMA.isbn, Literal(isbn)))
    for issn in data.get("issn", []):
        graph.add((work_uri, SCHEMA.issn, Literal(issn)))

    # Si es un artículo (773 presente), registrar la publicación anfitriona
    host_item = data.get("host_item")
    if host_item and host_item.get("title"):
        host_uri = EX[f"periodical/{slugify(host_item['title'])}"]
        graph.add((host_uri, RDF.type, SCHEMA.Periodical))
        graph.add((host_uri, SCHEMA.name, Literal(host_item["title"])))
        graph.add((work_uri, SCHEMA.isPartOf, host_uri))
        if host_item.get("related_parts"):
            graph.add((work_uri, EX.citationDetail, Literal(host_item["related_parts"])))

    # Autoría (100)
    main_author = data.get("main_author")
    if main_author and main_author.get("name"):
        author_uri = person_node(graph, main_author["name"], main_author.get("dates"))
        graph.add((work_uri, SCHEMA.author, author_uri))

    # Contribuidores con rol diferenciado (700)
    for contributor in data.get("contributors", []):
        contributor_uri = person_node(graph, contributor["name"], contributor.get("dates"))
        relator = (contributor.get("relator") or "").lower().strip(".")
        schema_property = RELATOR_TO_SCHEMA_PROPERTY.get(relator, SCHEMA.contributor)
        graph.add((work_uri, schema_property, contributor_uri))

    # Eje "TRATA SOBRE" (600): mismo nodo de persona que usarías para autoría,
    # pero enlazado con schema:about, no schema:author.
    for subject_person in data.get("subject_persons", []):
        subject_person_uri = person_node(graph, subject_person["name"], subject_person.get("dates"))
        graph.add((work_uri, SCHEMA.about, subject_person_uri))

    # Materias no personales (650/651) como DefinedTerm, igual que antes
    for label in data.get("topical_subjects", []):
        subject_uri = EX[f"subject/{slugify(label)}"]
        graph.add((subject_uri, RDF.type, SCHEMA.DefinedTerm))
        graph.add((subject_uri, RDFS.label, Literal(label)))
        graph.add((work_uri, SCHEMA.about, subject_uri))

    # Género/forma (655) como metadato descriptivo adicional: se conserva
    # aunque la heurística de tipo no lo haya usado directamente, para no
    # perder información.
    for genre_term in data.get("genre_form_terms", []):
        graph.add((work_uri, SCHEMA.genre, Literal(genre_term)))


# --------------------------------------------------------------------------
# Proceso principal
# --------------------------------------------------------------------------

def main() -> None:
    graph = Graph()
    graph.bind("ex", EX)
    graph.bind("schema", SCHEMA)
    bootstrap_ontology(graph)

    fixture_paths = sorted(glob.glob(FIXTURES_GLOB))
    print(f"Ficheros de fixtures encontrados: {len(fixture_paths)}")

    total_records = 0
    type_counts: dict[str, int] = {}

    for fixture_path in fixture_paths:
        marc_records = extract_marc_records_from_sru_file(Path(fixture_path))
        for marc_record in marc_records:
            record_dict = marc_record_to_dict(marc_record)
            resource_type = classify_resource_type(record_dict)
            type_counts[str(resource_type)] = type_counts.get(str(resource_type), 0) + 1
            record_dict_to_graph(record_dict, graph)
            total_records += 1

    OUTPUT_TTL_PATH.parent.mkdir(parents=True, exist_ok=True)
    graph.serialize(destination=str(OUTPUT_TTL_PATH), format="turtle")

    print(f"Registros MARC procesados : {total_records}")
    print(f"Triples RDF generados     : {len(graph)}")
    print("Distribución de tipos detectados:")
    for type_uri, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {type_uri}: {count}")
    print(f"Grafo guardado en         : {OUTPUT_TTL_PATH}")


if __name__ == "__main__":
    main()
