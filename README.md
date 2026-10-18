# Knowledge Graph for the Library of the Ibero-Amerikanisches Institut (IAI), Berlin

Proposal and prototype of a knowledge graph that integrates the resources of the library of the
Ibero-Amerikanisches Institut (IAI, Stiftung Preußischer Kulturbesitz) with its Ibero-American
studies environment in Berlin: the Latin American Institute of the Freie Universität (LAI-FU),
embassies and other cultural institutions.

**Author:** Juan Alberto Salazar Rebolledo

> **Status:** work in progress. The ontology (TBox) is implemented and tested with a tiny sample of
> individuals (ABox) on the "Latin American Boom". Large-scale ingestion, alignment with
> Wikidata/DBpedia and a SHACL validation layer are still pending.

## 1. Domain and motivation

The IAI holds one of the largest collections on Ibero-American studies in the world: around one and a
half million specialized books, plus digital resources, archival and periodical documents,
audiovisual materials and events. Around it there is a network of institutions with their own
cultural and research agendas.

Today these resources are disconnected. The catalog search works by keywords, which limits the
connections between resources, and it behaves as a silo even within the institution itself: it does
not integrate the IAI's own events or its databases, and it does not index what happens outside its
collection (events at other institutions, films, music or documentaries tied to Ibero-American topics).

The knowledge graph provides an overview of the Ibero-American activities and resources across the
city, with the IAI collection as its core. It also connects to external resources: films based on
literary works, event agendas and recordings, LAI-FU research projects, and data about agents and works.

The planned access point is an improved search interface accompanied by a **GraphRAG** chatbot: an LLM
that translates natural-language questions into SPARQL queries and returns the results, also in natural
language.

As a showcase of the model, a small dataset on the **Latin American Boom** (1960s and 1970s) is used.

## 2. Data sources

| Source | Format | Coverage | Integration difficulties |
|---|---|---|---|
| IAI library catalog (OPAC), via SRU API | MARC21/XML | Books, articles, periodicals | Structured data, but in a library standard; MARC21/XML must be mapped to RDF (e.g. RML rules with Morph-KGC) |
| IAI events calendar | HTML | Presentations, lectures, round tables, screenings | Semi-structured; disconnected from the catalog |
| LAI-FU and embassy newsletters | PDF, HTML | Congresses, receptions, prizes, cultural promotion | Unstructured; requires OCR, NER (named-entity recognition) and RE (relation extraction) |
| IAI and LAI-FU research projects and groups | HTML | Projects, stays, colloquia | Fragmented across several sites; scraping (BeautifulSoup) and NLP/NER |
| IMDb Datasets | TSV / API | Films and series based on literary works | Very large; best filtered using identifiers obtained beforehand from Wikidata/DBpedia |
| MusicBrainz | REST API (JSON) | Songs inspired by works or authors | Good quality; start from MBIDs obtained via Wikidata/DBpedia |

## 3. Ontology

The ontology uses **Schema.org** as its core vocabulary, for two reasons:

- BIBFRAME and CIDOC-CRM, natural candidates for a bibliographic and heritage collection, are too
  rigid or too complex for integrating events, films, music and research projects.
- Schema.org is well represented in the data used to train LLMs, which makes it compatible with RAG
  and GraphRAG architectures.

It is combined with selected elements from other vocabularies:

| Prefix | Vocabulary | Use |
|---|---|---|
| `schema:` | Schema.org | Core vocabulary |
| `bf:` | BIBFRAME | Library classification and the Work / Instance / Item distinction |
| `foaf:` | FOAF | Relations between people (`foaf:knows`) |
| `iai:` / `iair:` | Own namespace | Own classes and relations (TBox) and individuals (ABox) |
| `rdf:`, `rdfs:`, `xsd:`, `owl:` | W3C | Infrastructure, datatypes and axioms |
| `ric:` | ICA RiC-O | Archival documents (planned, not implemented) |
| `dbo:`, `dbr:`, `wdt:`, `wd:` | DBpedia, Wikidata | Alignment with Linked Open Data (pending) |

**Reasoning.** These are the logical constructs used in the ontology:

- **Class hierarchies and unions** (`rdfs:subClassOf`, `owl:unionOf`).
- **Disjoint root classes** (`owl:AllDisjointClasses`). It acts as an integrity guard: during testing it
  detected assertions entered backwards (a director assigned with subject and object swapped).
- **Inverse properties** (`owl:inverseOf`): each fact is captured once, from the side of the work.
- **Transitivity** on `iai:hasInfluenced` / `iai:influencedBy`: the reasoner reconstructs chains of influence.
- **Symmetry** on `iai:collaboratesWith`.
- **Property chains** (`owl:propertyChainAxiom`) starting from `schema:isBasedOn`: they connect derived works with their original authors.
- **Classes defined by restriction** (`owl:equivalentClass`): roles (author, director, performer) are
  inferred from what a person does, not from a fixed label.
- **SWRL rules**, only where OWL falls short: collaboration through co-authorship, influence through
  mentorship, and `foaf:knows` through shared membership.

It has been tested in **Protégé** with the **Pellet** reasoner, and the inferences were inspected
visually in **GraphDB** (screenshot in `otros/grafo_iai_graphdb_1.png`).

## 4. Curation and enrichment (plan)

1. **Normalization.** Convert each source to RDF following the ontology (RML/Morph-KGC for MARC21/XML;
   targeted queries to Wikidata/DBpedia for IMDb and MusicBrainz; NER/RE for unstructured text).
2. **Cleaning.** Fix name variants (accents, spellings, word order) and identifier formats.
3. **Entity reconciliation.** Unify individuals described by different sources using keys
   (`owl:hasKey`, ideally the Wikidata QID). The prototype uses `owl:AllDifferent` to tell individuals
   apart, a solution that does not scale: in production that check would move to SPARQL queries.
4. **Validation.** Cardinalities and disjointness in OWL, plus a SHACL layer to require, for example,
   that every work has an author.
5. **Enrichment.** Rule-based inference and links to DBpedia/Wikidata.

## 5. Value provided

- Multi-hop queries, for example: *films based on works by authors who knew each other within the same literary movement*.
- A single access point to collection, events and projects that are scattered today.
- Exploratory navigation: from an author to an adaptation, a song, an upcoming event or a related project.
- A living inventory of the connections between the IAI and its environment, useful for spotting gaps or overlaps in the city's cultural programming.
- Greater visibility of the collection in the Linked Open Data ecosystem.

## 6. AI technologies by phase

| Phase | Technology | Note |
|---|---|---|
| Ingestion of unstructured sources | OCR + NER/RE | With human supervision |
| Entity reconciliation | Variant dictionaries; semantic embeddings | Traceable and auditable; human review |
| Enrichment | Neural networks / embeddings to predict relations | With human supervision |
| Reasoning | Symbolic AI: Pellet, HermiT | Already present in the ontology |
| Exploitation | GraphRAG chatbot (natural language → SPARQL → natural language) | Public-facing interface |

## Repository contents

| File | Description |
|---|---|
| `iai_tbox.ttl` | Ontology (TBox) |
| `iai_abox.ttl` | Sample individuals (ABox) |
| `grafo_IAI_ontologia_jasrvfinal.xlsx` | Ontology documentation: namespaces, classes, properties, OWL/RDFS and SWRL rules |
| `catalog-v001.xml`, `*.properties` | Protégé / GraphDB configuration |
| `otros/` | Working material: harvesting and conversion scripts, test data and earlier versions |

Scripts in `otros/`:

- `crawler_k10plus.py`, `k10plus_sru_harvester*.py`: harvesting of MARC21/XML records from the K10plus SRU API.
- `marc_to_rdf_converter*.py`: conversion of MARC21/XML to RDF.
- `sampler_IAI.py`: sampling of K10plus records (output in `k10plus_sample.jsonl`).
- `rastreador.py`: tests of the SRU API search indexes.

Script dependencies: `pip install pymarc rdflib lxml requests`.
