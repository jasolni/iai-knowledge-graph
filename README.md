# Grafo de conocimiento de la Biblioteca del Instituto Iberoamericano (IAI), Berlín

Propuesta y prototipo de un grafo de conocimiento que integra los recursos de la biblioteca del
Ibero-Amerikanisches Institut (IAI, Stiftung Preußischer Kulturbesitz) con su entorno
iberoamericanista en Berlín: el Instituto Latinoamericano de la Freie Universität (LAI-FU), las
embajadas y otras instituciones culturales.

**Autor:** Juan Alberto Salazar Rebolledo

> **Estado:** trabajo en construcción. La ontología (TBox) está implementada y probada con una
> micromuestra de individuos (ABox) sobre el "Boom Latinoamericano". La ingesta a gran escala,
> la alineación con Wikidata/DBpedia y la capa de validación SHACL están pendientes.

## 1. Dominio y motivación

El IAI custodia una de las mayores colecciones sobre estudios iberoamericanos del mundo: cerca de
un millón y medio de libros especializados, además de recursos digitales, documentos archivísticos
y hemerográficos, materiales audiovisuales y eventos. A su alrededor hay una red de instituciones
con agendas culturales y de investigación propias.

Hoy esos recursos están desconectados. El buscador del catálogo funciona por palabras clave, que
limitan la conexión entre recursos, y actúa como un silo incluso dentro de la propia institución:
no integra los eventos del IAI ni sus bases de datos, y no indexa lo que ocurre fuera de su
colección (eventos de otras instituciones, películas, música o documentales ligados a temas
iberoamericanos).

El grafo de conocimiento da una visión de conjunto de las actividades y recursos
iberoamericanistas de la ciudad, con la colección del IAI como núcleo. Se conecta además con
recursos externos: películas basadas en obras literarias, agenda y grabaciones de eventos,
proyectos de investigación del LAI-FU, y datos sobre agentes y obras.

El punto de acceso previsto es un buscador mejorado, acompañado de un chatbot **GraphRAG**: un LLM
que traduce preguntas en lenguaje natural a consultas SPARQL y devuelve los resultados también en
lenguaje natural.

Como muestra del modelo se usa un pequeño conjunto sobre el **Boom Latinoamericano** (años 1960 y 1970).

## 2. Fuentes de datos

| Fuente | Formato | Cobertura | Dificultades de integración |
|---|---|---|---|
| Catálogo bibliográfico del IAI (OPAC), vía API SRU | MARC21/XML | Libros, artículos, publicaciones periódicas | Datos estructurados pero en un estándar bibliotecario; hace falta mapear MARC21/XML a RDF (p. ej. reglas RML con Morph-KGC) |
| Calendario de eventos del IAI | HTML | Presentaciones, conferencias, mesas redondas, proyecciones | Semiestructurado; desvinculado del catálogo |
| Newsletters del LAI-FU y de embajadas | PDF, HTML | Congresos, recepciones, premios, promoción cultural | No estructurado; requiere OCR, NER (reconocimiento de entidades) y RE (extracción de relaciones) |
| Proyectos y grupos de investigación del IAI y del LAI-FU | HTML | Proyectos, estancias, coloquios | Fragmentados en varios sitios; scraping (BeautifulSoup) y NLP/NER |
| IMDb Datasets | TSV / API | Películas y series basadas en obras literarias | Muy extenso; conviene filtrar por identificadores obtenidos antes desde Wikidata/DBpedia |
| MusicBrainz | API REST (JSON) | Canciones inspiradas en obras o autores | Buena calidad; se parte de MBID obtenidos vía Wikidata/DBpedia |

## 3. Ontología

La ontología usa **Schema.org** como vocabulario núcleo, por dos razones:

- BIBFRAME y CIDOC-CRM, candidatos naturales para un fondo bibliográfico-patrimonial, resultan
  demasiado rígidos o complejos para integrar eventos, películas, música y proyectos de investigación.
- Schema.org está muy presente en los datos con los que se entrenan los LLM, lo que lo hace
  compatible con arquitecturas RAG y GraphRAG.

Se hibrida con elementos puntuales de otros vocabularios:

| Prefijo | Vocabulario | Uso |
|---|---|---|
| `schema:` | Schema.org | Vocabulario núcleo |
| `bf:` | BIBFRAME | Clasificación bibliotecaria y distinción Work / Instance / Item |
| `foaf:` | FOAF | Relaciones entre personas (`foaf:knows`) |
| `iai:` / `iair:` | Namespace propio | Clases y relaciones propias (TBox) e individuos (ABox) |
| `rdf:`, `rdfs:`, `xsd:`, `owl:` | W3C | Infraestructura, tipos de datos y axiomas |
| `ric:` | ICA RiC-O | Documentos archivísticos (previsto, no implementado) |
| `dbo:`, `dbr:`, `wdt:`, `wd:` | DBpedia, Wikidata | Alineación con Linked Open Data (pendiente) |

**Razonamiento.** Estas son las construcciones lógicas que usa la ontología:

- **Jerarquías y uniones de clases** (`rdfs:subClassOf`, `owl:unionOf`).
- **Clases raíz disjuntas** (`owl:AllDisjointClasses`). Actúa como guardia de integridad: durante las
  pruebas detectó aserciones capturadas al revés (un director asignado con sujeto y objeto invertidos).
- **Propiedades inversas** (`owl:inverseOf`): el dato se captura una vez, del lado de la obra.
- **Transitividad** en `iai:hasInfluenced` / `iai:influencedBy`: el razonador reconstruye genealogías de influencias.
- **Simetría** en `iai:collaboratesWith`.
- **Cadenas de propiedades** (`owl:propertyChainAxiom`) a partir de `schema:isBasedOn`: conectan obras derivadas con sus autores originales.
- **Clases definidas por restricción** (`owl:equivalentClass`): los roles (autor, director, intérprete) se
  infieren de lo que la persona hace, no de una etiqueta fija.
- **Reglas SWRL**, solo donde OWL no alcanza: colaboración por coautoría, influencia por mentoría y
  `foaf:knows` por pertenencia común.

Se ha probado en **Protégé** con el razonador **Pellet**, y las inferencias se han inspeccionado
visualmente en **GraphDB** (captura en `otros/grafo_iai_graphdb_1.png`).

## 4. Curación y enriquecimiento (plan)

1. **Normalización.** Convertir cada fuente a RDF conforme a la ontología (RML/Morph-KGC para MARC21/XML;
   consultas dirigidas a Wikidata/DBpedia para IMDb y MusicBrainz; NER/RE para texto no estructurado).
2. **Limpieza.** Corregir variantes de nombres (acentos, grafías, orden) y formatos de identificadores.
3. **Reconciliación de entidades.** Unificar individuos descritos desde fuentes distintas con claves
   (`owl:hasKey`, idealmente el QID de Wikidata). El prototipo usa `owl:AllDifferent` para distinguir
   individuos, solución que no escala: en producción esa comprobación pasaría a consultas SPARQL.
4. **Validación.** Cardinalidades y disyunciones en OWL, más una capa SHACL para exigir, por ejemplo,
   que cada obra tenga autor.
5. **Enriquecimiento.** Inferencia por reglas y enlaces a DBpedia/Wikidata.

## 5. Valor aportado

- Consultas multi-salto, por ejemplo: *películas basadas en obras de autores que se conocían entre sí dentro del mismo movimiento literario*.
- Un acceso único a colección, eventos y proyectos que hoy están dispersos.
- Navegación exploratoria: de un autor a una adaptación, una canción, un evento próximo o un proyecto afín.
- Un inventario vivo de conexiones entre el IAI y su entorno, útil para detectar vacíos o duplicados en la programación cultural.
- Más visibilidad de la colección en el ecosistema Linked Open Data.

## 6. Tecnologías de IA por fase

| Fase | Tecnología | Nota |
|---|---|---|
| Ingesta de fuentes no estructuradas | OCR + NER/RE | Con supervisión humana |
| Reconciliación de entidades | Diccionarios de variantes; embeddings semánticos | Trazable y auditable; revisión humana |
| Enriquecimiento | Redes neuronales / embeddings para predecir relaciones | Con supervisión humana |
| Razonamiento | IA simbólica: Pellet, HermiT | Ya presente en la ontología |
| Explotación | Chatbot GraphRAG (lenguaje natural → SPARQL → lenguaje natural) | Interfaz para el público |

## Contenido del repositorio

| Archivo | Descripción |
|---|---|
| `iai_tbox.ttl` | Ontología (TBox) |
| `iai_abox.ttl` | Muestra de individuos (ABox) |
| `grafo_IAI_ontologia_jasrvfinal.xlsx` | Documentación de la ontología: namespaces, clases, propiedades, reglas OWL/RDFS y SWRL |
| `catalog-v001.xml`, `*.properties` | Configuración de Protégé / GraphDB |
| `otros/` | Material de trabajo: scripts de recolección y conversión, datos de prueba y versiones previas |

Scripts en `otros/`:

- `crawler_k10plus.py`, `k10plus_sru_harvester*.py`: recolección de registros MARC21/XML desde la API SRU de K10plus.
- `marc_to_rdf_converter*.py`: conversión de MARC21/XML a RDF.
- `sampler_IAI.py`: muestreo de registros de K10plus (resultado en `k10plus_sample.jsonl`).
- `rastreador.py`: pruebas de los índices de búsqueda de la API SRU.

Dependencias de los scripts: `pip install pymarc rdflib lxml requests`.
