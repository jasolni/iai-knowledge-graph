# Knowledge Graph for the Library of the Ibero-Amerikanisches Institut (IAI), Berlin

Proposal and working prototype of a knowledge graph that integrates the resources of the library of the
Ibero-Amerikanisches Institut (IAI, Stiftung Preußischer Kulturbesitz) with its Ibero-American
studies environment in Berlin: the Latin American Institute of the Freie Universität (LAI-FU),
embassies and other cultural institutions.

**Author:** Juan Alberto Salazar Rebolledo ([@jasolni](https://github.com/jasolni))

> **Status:** work in progress. The ontology (TBox) is implemented and reasons correctly over a tiny
> hand-built sample (ABox) on the "Latin American Boom", in Protégé (Pellet) and GraphDB. A separate data
> pipeline downloads real catalog records from the IAI collection and converts them to RDF using the
> **same Schema.org vocabulary** as the TBox, so the ontology's axioms already apply to that data
> (see [section 5](#reasoning-over-the-generated-graph)). What is still missing is the full mapping of
> that data onto the ontology's own namespaces and BIBFRAME layers (see
> [Known limitations](#known-limitations)). Large-scale ingestion, alignment with Wikidata/DBpedia and a
> SHACL validation layer are also pending.

## Table of contents

1. [What is in this repository](#what-is-in-this-repository)
2. [Domain and motivation](#1-domain-and-motivation)
3. [Data sources](#2-data-sources)
4. [The ontology](#3-the-ontology)
5. [The ABox sample](#4-the-abox-sample)
6. [The data pipeline (MARC21 → RDF)](#5-the-data-pipeline-marc21--rdf)
7. [Example SPARQL queries](#6-example-sparql-queries)
8. [Curation and enrichment plan](#7-curation-and-enrichment-plan)
9. [Value provided and AI technologies](#8-value-provided-and-ai-technologies)
10. [How to use the repository](#9-how-to-use-the-repository)
11. [Known limitations](#known-limitations)
12. [Next steps](#next-steps)

## What is in this repository

```
.
├── README.md                              This document
├── iai_tbox.ttl                           Ontology (TBox): classes, properties, axioms, SWRL rules
├── iai_abox.ttl                           Hand-built sample of individuals (ABox); imports the TBox
├── grafo_IAI_ontologia_jasrvfinal.xlsx    Design documentation of the ontology (5 tabs)
├── catalog-v001.xml                       Protégé catalog: resolves the TBox import locally
├── iai_tbox.properties, iai_abox.properties   Protégé project files (empty connection placeholders, no credentials)
└── otros/                                 Data-harvesting and conversion pipeline
    ├── k10plus_sru_harvester_by_author_v2.py   Downloads MARC21/XML records by author
    ├── marc_to_rdf_converter_v2.py             Converts those records to RDF (Turtle)
    ├── grafo_iai_graphdb_1.png                 GraphDB visualization of the ABox sample
    └── fixtures/
        ├── iai_marcxml_by_author/              Downloaded records: 12 authors, 59 XML pages
        ├── iai_manifest_by_author.json         Coverage manifest of the download
        └── iai_graph_v2.ttl                    Resulting RDF graph (17,227 triples)
```

| Component | Size | What it is |
|---|---|---|
| TBox (`iai_tbox.ttl`) | 955 triples | 46 named classes, 44 object properties, 21 datatype properties, 3 SWRL rules |
| ABox (`iai_abox.ttl`) | 183 triples | 28 individuals on the Latin American Boom |
| Pipeline output (`iai_graph_v2.ttl`) | 17,227 triples | 1,152 works, 943 persons, 480 organizations, 431 subject terms |

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

As a showcase of the model, a small dataset on the **Latin American Boom** (1960s and 1970s) is used,
both for the hand-built ABox and for the records downloaded by the pipeline.

## 2. Data sources

| Source | Format | Coverage | Integration difficulties |
|---|---|---|---|
| IAI library catalog (OPAC), via SRU API | MARC21/XML | Books, articles, periodicals | Structured data, but in a library standard; MARC21/XML must be mapped to RDF (e.g. RML rules with Morph-KGC) |
| IAI events calendar | HTML | Presentations, lectures, round tables, screenings | Semi-structured; disconnected from the catalog |
| LAI-FU and embassy newsletters | PDF, HTML | Congresses, receptions, prizes, cultural promotion | Unstructured; requires OCR, NER (named-entity recognition) and RE (relation extraction) |
| IAI and LAI-FU research projects and groups | HTML | Projects, stays, colloquia | Fragmented across several sites; scraping (BeautifulSoup) and NLP/NER |
| IMDb Datasets | TSV / API | Films and series based on literary works | Very large; best filtered using identifiers obtained beforehand from Wikidata/DBpedia |
| MusicBrainz | REST API (JSON) | Songs inspired by works or authors | Good quality; start from MBIDs obtained via Wikidata/DBpedia |

**Implemented so far:** only the first row. The IAI catalog is queried through the K10plus union
catalog (see [section 5](#5-the-data-pipeline-marc21--rdf)). The other sources are part of the plan.

## 3. The ontology

### Design decisions

The ontology uses **Schema.org** as its core vocabulary, for two reasons:

- BIBFRAME and CIDOC-CRM, natural candidates for a bibliographic and heritage collection, are too
  rigid or too complex for integrating events, films, music and research projects.
- Schema.org is well represented in the data used to train LLMs, which makes it compatible with RAG
  and GraphRAG architectures.

It is combined with selected elements from other vocabularies:

| Prefix | Vocabulary | Use |
|---|---|---|
| `schema:` | Schema.org (`http://schema.org/`) | Core vocabulary |
| `bf:` | BIBFRAME | Library classification and the Work / Instance / Item distinction |
| `foaf:` | FOAF | Relations between people (`foaf:knows`) |
| `iai:` | `http://www.iai.spk-berlin.de/tbox#` | Own classes and relations (TBox) |
| `iair:` | `http://www.iai.spk-berlin.de/abox/` | Own individuals (ABox) |
| `rdf:`, `rdfs:`, `xsd:`, `owl:` | W3C | Infrastructure, datatypes and axioms |
| `ric:` | ICA RiC-O | Archival documents (planned, not implemented) |
| `dbo:`, `dbr:`, `wdt:`, `wd:` | DBpedia, Wikidata | Alignment with Linked Open Data (pending; `wd:` is only declared in the ABox) |

A key modelling choice: **roles are not asserted as types**. Every human is a `schema:Person`; whether
someone is an author, director or musician is determined by the properties linking them to works. The
classes `iai:Author`, `iai:Director` and `iai:Musician` are defined by restriction (`owl:equivalentClass`),
so the reasoner classifies people automatically, and the same person can hold several roles without
contradiction.

### Classes (46 named classes)

| Group | Classes |
|---|---|
| Works (`schema:CreativeWork`) | `schema:Book`, `schema:ShortStory`, `iai:Poem`, `schema:Article`, `schema:ScholarlyArticle`, `schema:Thesis`, `schema:ArchiveComponent`, `schema:Review`, `schema:CreativeWorkSeries` (`schema:TVSeries`, `schema:Periodical`), `schema:VisualArtwork`, `iai:TheatricalAdaptation`, `schema:Movie`, `schema:MediaObject` (`schema:VideoObject`), `schema:MusicComposition`, `schema:MusicRecording` |
| Library layers (BIBFRAME) | `bf:Work` (abstract work), `bf:Instance` (edition / manifestation), `bf:Item` (physical copy) |
| People | `schema:Person`, plus inferred roles `iai:Author`, `iai:Director`, `iai:Musician`; `iai:FictionalCharacter` |
| Organizations | `schema:Organization` (`schema:Project`, `schema:EducationalOrganization`, `schema:GovernmentOrganization`, `schema:Library`, `schema:PerformingGroup` → `schema:MusicGroup`) |
| Events | `schema:Event` (`schema:LiteraryEvent`, `schema:ScreeningEvent`, `schema:EducationEvent`, `schema:SocialEvent`, `schema:ExhibitionEvent`) |
| Places | `schema:Place`, `schema:AdministrativeArea`, `schema:Country` |
| Other concepts | `iai:LiteraryMovement` (e.g. the Boom), `iai:Award` |

A `schema:Book` individual is also typed `bf:Instance`; a `schema:ArchiveComponent` can be combined
with a concrete type (multi-typing). The full hierarchy, with the rationale for each class, is in the
Excel file (tab *Classes and subclasses*).

### Properties

**Object properties (44)** include:

- *Roles and authorship:* `schema:author` / `iai:authorOf`, `schema:director` / `iai:directorOf`,
  `schema:composer` / `iai:hasComposed`, `schema:byArtist` / `iai:hasInterpreted`, `schema:actor` /
  `iai:actedIn`, `schema:translator` / `iai:hasTranslated`, `schema:illustrator` / `iai:hasIllustrated`,
  `schema:editor` / `iai:hasEdited`, `schema:publisher` / `iai:hasPublished`, `schema:character` /
  `iai:createdBy`.
- *Materiality (BIBFRAME):* `bf:hasInstance` / `bf:instanceOf`, `bf:hasItem` / `bf:itemOf`.
- *Content-to-work references:* `schema:isBasedOn`, `schema:recordingOf`, `schema:about`,
  `schema:isPartOf`, `iai:hasInfluenced` / `iai:influencedBy`.
- *Events:* `schema:attendee`, `schema:performer`, `schema:organizer`, `schema:workPresented`,
  `iai:receivedAward`.
- *People and places:* `schema:memberOf`, `foaf:knows`, `iai:mentorOf`, `iai:collaboratesWith`,
  `schema:birthPlace`, `schema:location`.

**Datatype properties (21)** include: `schema:name`, `schema:description`, `schema:isbn`, `schema:issn`,
`bf:shelfMark`, `schema:identifier` (barcodes, IMDb IDs, MusicBrainz MBIDs), `bf:classification`,
`schema:url`, `schema:datePublished` (`xsd:gYear`), `schema:startDate` / `schema:endDate`,
`schema:birthDate` / `schema:deathDate` (`xsd:date`), `iai:awardYear`, `schema:genre`,
`schema:inLanguage` (ISO 639-1), `schema:numberOfPages`, `schema:lyrics`, `iai:readerCount`,
`schema:maximumAttendeeCapacity`, `iai:attendeeCount`.

> The types `xsd:gYear` and `xsd:date` were tested with Pellet and work, although they differ from those
> suggested by Schema.org and OWL 2. Another reasoner, such as HermiT, might require replacing them with
> `xsd:dateTime`.

### Logical constructs

| Construct | Use in this ontology |
|---|---|
| `rdfs:subClassOf`, `owl:unionOf` | Class taxonomy |
| `owl:AllDisjointClasses` | The 9 root classes (`CreativeWork`, `Person`, `Organization`, `Event`, `Place`, `bf:Item`, `iai:Award`, `iai:FictionalCharacter`, `iai:LiteraryMovement`) are mutually disjoint. It works as an integrity guard: during testing it detected assertions entered backwards (a director assigned with subject and object swapped, which forced a person to also be a work) |
| `owl:inverseOf` | Every contribution relation has an inverse, so each fact is captured once, from the side of the work, and the graph infers the other direction |
| `owl:TransitiveProperty` | `iai:hasInfluenced` / `iai:influencedBy`: if a work is based on another that is based on a third, the reasoner rebuilds the whole genealogy |
| `owl:SymmetricProperty` | `iai:collaboratesWith` |
| `owl:propertyChainAxiom` | Declared on two properties. `iai:influencedBy`: a work based on another (`schema:isBasedOn`) is influenced by that work's author (`schema:author`), with further chains linking the author, director or performer of a derived work to the author of the source work. `iai:createdBy`: a fictional character is created by the author of the work in which it appears (`schema:character` inverse + `schema:author`) |
| `owl:equivalentClass` | `iai:Author`, `iai:Director`, `iai:Musician` defined as the persons who are subject of `schema:author`, `schema:director`, etc. |

### SWRL rules (3)

SWRL is used only where OWL falls short: the rules must check that two variables are not the same
individual (`differentFrom`), which cannot be expressed with property chains or class restrictions.

| Rule | Expression | Purpose |
|---|---|---|
| S1 Collaboration | `CreativeWork(?w) ^ author(?w,?p1) ^ author(?w,?p2) ^ differentFrom(?p1,?p2) → collaboratesWith(?p1,?p2)` | Co-authors of a publication collaborate |
| S2 Mentor affinity | `mentorOf(?a,?b) ^ Person(?a) ^ memberOf(?a,?mov) → influencedBy(?b,?mov)` | Students inherit the influence of their mentor's literary movement |
| S3 Network | `memberOf(?a,?m) ^ memberOf(?b,?m) ^ differentFrom(?a,?b) → knows(?a,?b)` | Members of the same organization or movement know each other |

### Documentation workbook

`grafo_IAI_ontologia_jasrvfinal.xlsx` accompanies the TBox and documents each decision. Tabs:
*Readme* (index and namespaces), *Classes and subclasses*, *Properties - relations*,
*Properties - data* (both with their OWL/RDFS rules and notes) and *Additional rules (SWRL)*.

## 4. The ABox sample

`iai_abox.ttl` is a hand-built sample of 28 individuals (183 triples) used to exercise the ontology.
It declares `owl:imports` of the TBox. Its content:

| Kind | Individuals |
|---|---|
| Authors and people (11) | Gabriel García Márquez, Julio Cortázar, Alejo Carpentier, Juan Rulfo, Elena Garro, Rosario Castellanos, Óscar Chávez, Michelangelo Antonioni, David Hemmings, Vanessa Redgrave, Laura Mora Ortega |
| Books and written works | *Cien años de soledad* (as abstract `bf:Work` and as a book), *Los recuerdos del porvenir*, *El reino de este mundo*, *Mujer que sabe latín*, the collection *Las armas secretas* and the short story *Las babas del diablo* it contains |
| Audiovisual and music | the films *Blow-Up* (based on *Las babas del diablo*) and *Los adioses* (about Rosario Castellanos), the *Cien años de soledad* TV series, the recording *Macondo* (by Óscar Chávez) |
| Movements | Boom Latinoamericano and Realismo mágico (`iai:LiteraryMovement`); *Real maravilloso* appears only as a movement Carpentier belongs to |
| Institutions and events | Ibero-Amerikanisches Institut (`schema:Library`), Lateinamerika-Institut (`schema:EducationalOrganization`), and the exhibition *Surrealismus Lateinamerika*, organized by both and about Carpentier |

Among the facts it asserts: Carpentier is mentor of García Márquez; García Márquez, Cortázar and others
are members of the Boom; *Blow-Up* and the TV series are based on literary works. The ABox ends with an
`owl:AllDifferent` list of all individuals; without it, SWRL rules S1 and S3 could not safely conclude
that two individuals are distinct (OWL has no unique-name assumption). This does not scale: in
production the check would move into the queries (for example SPARQL `CONSTRUCT`).

**What a reasoner adds** (Protégé with Pellet): the inverse relations (e.g. `iai:authorOf`), roles such as
`iai:Author` or `iai:Director`, the chain of influences, `foaf:knows` between members of the same
movement (rule S3) and the influence of Carpentier's movements on García Márquez (rule S2). The file
`otros/grafo_iai_graphdb_1.png` shows the sample explored in GraphDB. As an independent check, an OWL 2 RL
expansion of TBox + ABox produces the inverse `iai:authorOf` statements and the `iai:Author` role
classification (see [section 5](#reasoning-over-the-generated-graph)).

## 5. The data pipeline (MARC21 → RDF)

The `otros/` folder holds a two-step pipeline that works on real catalog records. Run it from inside
`otros/` (the scripts use relative paths).

### Step 1: harvesting (`k10plus_sru_harvester_by_author_v2.py`)

- **Endpoint:** `http://sru.k10plus.de/opac-de-204` (K10plus union catalog; ISIL DE-204 is the IAI Berlin).
- **Protocol:** SRU 1.1 with CQL queries on the PICA index `pica.per` (author), in the authority form
  "Surname, First name".
- **Pagination:** 20 records per page via `startRecord`, with a cap of 100 records per author, and a
  1-second pause between requests out of courtesy to the public service.
- **Encoding fix:** the server answers `text/xml` without a charset, so `requests` would assume Latin-1
  and silently corrupt accents ("Carrión" → "CarriÃ³n"). The script decodes the raw bytes as UTF-8.
- **Outputs:** one XML file per page in `fixtures/iai_marcxml_by_author/<author>/page_NNNN.xml`, and a
  manifest (`fixtures/iai_manifest_by_author.json`) with status, totals and a short preview per author.

Seed authors: the Boom and direct precursors.

| Author | Country | Records in catalog | Downloaded |
|---|---|---|---|
| García Márquez, Gabriel | Colombia | 671 | 100 |
| Vargas Llosa, Mario | Peru | 633 | 100 |
| Fuentes, Carlos | Mexico | 513 | 100 |
| Cortázar, Julio | Argentina | 487 | 100 |
| Carpentier, Alejo (precursor) | Cuba | 349 | 100 |
| Onetti, Juan Carlos (precursor) | Uruguay | 184 | 100 |
| Rulfo, Juan (precursor) | Mexico | 158 | 100 |
| Lispector, Clarice | Brazil | 156 | 100 |
| Donoso, José | Chile | 133 | 100 |
| Castellanos, Rosario | Mexico | 118 | 100 |
| Puig, Manuel | Argentina | 114 | 100 |
| Garro, Elena | Mexico | 67 | 67 |
| **Total** | | **3,583** | **1,167** |

### Step 2: conversion (`marc_to_rdf_converter_v2.py`)

Reads every downloaded page, extracts the MARC records with `pymarc` and writes
`fixtures/iai_graph_v2.ttl`. Field mapping:

| MARC | Meaning | RDF |
|---|---|---|
| 001 | Control number | Work URI `ex:work/<number>` |
| 245 $a / $b | Title / subtitle | `schema:name`, `rdfs:label` / `schema:alternateName` |
| 100 | Main author | `schema:author` → `ex:person/<slug>` |
| 700 | Contributors with relator | `schema:translator`, `schema:illustrator`, `schema:editor`, `schema:author` (codes `trl`, `ill`, `edt`, `aut`); any other role → `schema:contributor` |
| 600 | Person as **subject** | `schema:about` → the **same** person node used for authorship |
| 650 / 651 | Topical / place subject | `schema:DefinedTerm` linked with `schema:about` |
| 655 | Genre / form | `schema:genre` (and a hint for the type heuristic) |
| 020 / 022 | ISBN / ISSN | `schema:isbn` / `schema:issn` |
| 041 | Language | `schema:inLanguage` |
| 250 | Edition | `schema:bookEdition` |
| 264 or 260 | Publisher, date | `schema:publisher` (an organization node), `schema:datePublished` |
| 520 | Summary | `schema:abstract` |
| 773 | Host item (article within a journal or book) | type `schema:ScholarlyArticle`, `schema:isPartOf` → `schema:Periodical`, `ex:citationDetail` |
| 502 | Dissertation note | type `ex:AcademicThesis` |
| Leader pos. 7 = `s` | Serial | type `schema:Periodical` |

The two ideas that distinguish this converter from a plain field-by-field mapping:

1. **Resource type heuristic** (`classify_resource_type`): thesis note (502) → `ex:AcademicThesis`;
   host item (773) → `schema:ScholarlyArticle`; serial leader → `schema:Periodical`; genre containing
   "biograf" → `ex:Biography`; genre containing "kritik", "crítica", "critique" or "estudio" →
   `ex:CriticalStudy`; anything else → `schema:Book`. It is a best-effort heuristic: genre vocabulary
   varies across cataloguing languages (Spanish, German and Portuguese in the IAI), so it is not a
   perfect classifier.
2. **Authorship vs. "is about":** a person who is the *subject* of a book (600) becomes the same node
   as when they are its author, linked with `schema:about` instead of `schema:author`. One query can
   then retrieve everything related to García Márquez, whether authored by him or about him.

Other details: `slugify` builds URI-safe identifiers (Unicode NFKD normalization, ASCII only,
non-alphanumerics replaced by `_`), and `repair_mojibake` repairs text that arrived double-encoded.

**Result** (`iai_graph_v2.ttl`): 17,227 triples describing 1,152 works.

| Type | Count |
|---|---|
| `schema:Book` | 982 |
| `schema:Person` | 943 |
| `schema:Organization` | 480 |
| `schema:DefinedTerm` | 431 |
| `schema:ScholarlyArticle` | 156 |
| `schema:Periodical` | 40 |
| `ex:Biography` | 9 |
| `ex:AcademicThesis` | 5 |

Most frequent properties: `schema:name` (2,631), `rdfs:label` (1,592), `schema:contributor` (1,186),
`schema:author` (1,160), `schema:datePublished` (1,152), `schema:isbn` (1,085), `schema:inLanguage`
(1,067), `schema:publisher` (1,014), `schema:about` (880).

**Namespaces in the generated graph.** The converter writes its own individuals and its three provisional
classes under `http://example.org/kg/` (`ex:work/…`, `ex:person/…`, `ex:AcademicThesis`,
`ex:CriticalStudy`, `ex:Biography`), while all the descriptive terms (`schema:author`, `schema:name`,
`schema:Book`, …) are the standard Schema.org IRIs (`http://schema.org/`), exactly the ones the TBox is
built on. The graph does not use `iai:` / `iair:` or BIBFRAME terms.

### Reasoning over the generated graph

Because both artifacts share the Schema.org vocabulary, the TBox can be loaded together with the
generated graph. As a check, the two were merged and expanded with an OWL 2 RL reasoner (the `owlrl`
Python library; this is a subset of OWL 2 and does not evaluate SWRL, so it is an indicative test, not a
replacement for Pellet in Protégé):

| Loaded together | Triples before → after | Inferred |
|---|---|---|
| TBox + ABox (hand-built sample) | 1,138 → 4,793 | 6 `iai:authorOf` statements; 5 individuals classified as `iai:Author` |
| TBox + generated graph (real records) | 18,182 → 101,372 | 1,160 `iai:authorOf` statements (one per `schema:author` assertion); 252 persons classified as `iai:Author`; 1,192 nodes inferred as `schema:CreativeWork` through the class hierarchy |

So the ontology's inverse properties and role definitions already work over the real data. What the
generated graph lacks is the mapping to the ontology's own layers (see
[Known limitations](#known-limitations)).

## 6. Example SPARQL queries

All of these were run against `otros/fixtures/iai_graph_v2.ttl`. Prefixes used:

```sparql
PREFIX schema: <http://schema.org/>
PREFIX ex:     <http://example.org/kg/>
```

**Authored by vs. about García Márquez** (returns 70 authored works and 14 about him in this sample):

```sparql
SELECT ?rel (COUNT(?w) AS ?n) WHERE {
  VALUES ?rel { schema:author schema:about }
  ?w ?rel <http://example.org/kg/person/garcia_marquez_gabriel> .
} GROUP BY ?rel
```

**Works about García Márquez:**

```sparql
SELECT ?title WHERE {
  ?w schema:about <http://example.org/kg/person/garcia_marquez_gabriel> ;
     schema:name ?title .
}
```

**Academic theses with their authors:**

```sparql
SELECT ?title ?author WHERE {
  ?w a ex:AcademicThesis ; schema:name ?title .
  OPTIONAL { ?w schema:author/schema:name ?author }
}
```

**Most frequent translators:**

```sparql
SELECT ?name (COUNT(?w) AS ?n) WHERE {
  ?w schema:translator ?t . ?t schema:name ?name .
} GROUP BY ?name ORDER BY DESC(?n) LIMIT 5
```

On the hand-built ABox (prefixes `iai:` = `http://www.iai.spk-berlin.de/tbox#`, `iair:` =
`http://www.iai.spk-berlin.de/abox/`), the multi-hop question from the project motivation, *films or
series based on works by members of the Boom*, is:

```sparql
SELECT ?film ?work ?author WHERE {
  ?film   schema:isBasedOn ?work .
  ?work   schema:author    ?author .
  ?author schema:memberOf  iair:boom_latinoamericano .
}
```

It returns *Blow-Up* (from *Las babas del diablo*, Cortázar) and the *Cien años de soledad* TV series
and the *Macondo* recording (García Márquez). With a reasoner enabled, the property chains and inverses extend what
this kind of query can reach without asserting those links by hand.

## 7. Curation and enrichment plan

1. **Normalization.** Convert each source to RDF following the ontology (RML/Morph-KGC for MARC21/XML;
   targeted queries to Wikidata/DBpedia for IMDb and MusicBrainz; NER/RE for unstructured text). Datatypes
   for dates, identifiers and languages are controlled as part of this step (partially implemented).
2. **Cleaning.** Fix name variants (accents, spellings, word order such as *Óscar Chávez / Oscar Chavez /
   Chavez Óscar*) and identifier formats. This is continuous and starts at ingestion.
3. **Entity reconciliation.** Unify individuals described by different sources using keys
   (`owl:hasKey`, ideally the Wikidata QID, assigned to classes such as `schema:Person` or
   `schema:Book`) so the reasoner merges identical entities without hand-written `owl:sameAs`.
   The prototype's `owl:AllDifferent` list is the stopgap; in production it moves to SPARQL.
4. **Validation.** Cardinalities, disjointness and reflexivity in OWL, plus a SHACL layer to require, for
   example, that every work has an author and every person an identifier.
5. **Enrichment.** Rule-based inference, plus links to DBpedia/Wikidata so queries can reach those resources
   without replicating them in the graph.

## 8. Value provided and AI technologies

**Value:**

- Multi-hop queries, for example: *films based on works by authors who knew each other within the same literary movement*.
- A single access point to collection, events and projects that are scattered today.
- Exploratory navigation: from an author to an adaptation, a song, an upcoming event or a related project.
- A living inventory of the connections between the IAI and its environment, useful for spotting gaps or overlaps in the city's cultural programming.
- Greater visibility of the collection in the Linked Open Data ecosystem.

**AI technologies by phase:**

| Phase | Technology | Note |
|---|---|---|
| Ingestion of unstructured sources | OCR + NER/RE | With human supervision |
| Entity reconciliation | Variant dictionaries; semantic embeddings | Traceable and auditable; human review before accepting a match, to avoid merging homonyms |
| Enrichment | Neural networks / embeddings to predict relations | With human supervision |
| Reasoning | Symbolic AI: Pellet, HermiT | Already present in the ontology |
| Exploitation | GraphRAG chatbot (natural language → SPARQL → natural language) | Public-facing interface |

## 9. How to use the repository

**Explore the ontology in Protégé.** Open `iai_abox.ttl`; it imports the TBox, and `catalog-v001.xml`
resolves that import to the local `iai_tbox.ttl` (keep both files in the same folder). Start a reasoner
(Pellet, for the SWRL rules) to see the inferences.

**Explore in GraphDB.** Import `iai_tbox.ttl` and `iai_abox.ttl` into a repository with an OWL 2 RL
ruleset enabled, and use the visual graph to follow relations (inverse, transitive and symmetric
properties and property chains are covered by that ruleset). GraphDB's built-in rulesets do not
evaluate SWRL, so rules S1–S3 are applied only in Protégé with a reasoner such as Pellet. To reason over
the real records, import `otros/fixtures/iai_graph_v2.ttl` into the same repository as well.

**Run the data pipeline.**

```bash
pip install pymarc rdflib lxml requests
cd otros
python k10plus_sru_harvester_by_author_v2.py   # needs internet access; downloads MARC21/XML records
python marc_to_rdf_converter_v2.py             # writes fixtures/iai_graph_v2.ttl
```

The repository already contains the output of both steps, so the converter can be run without
downloading anything. The scripts were developed with Python 3.13.

## Known limitations

- **The generated graph is only partly mapped onto the ontology.** It shares the Schema.org vocabulary
  with the TBox, so the TBox axioms apply to it (see [section 5](#reasoning-over-the-generated-graph)).
  But its individuals live in a placeholder namespace (`http://example.org/kg/`) instead of
  `iair:`, its three provisional classes (`ex:AcademicThesis`, `ex:CriticalStudy`, `ex:Biography`) exist only
  inside the generated graph (as `schema:CreativeWork` subclasses) and not in the TBox, and the BIBFRAME
  `bf:Work` / `bf:Instance` / `bf:Item` layers and the `iai:` relations (influence, mentorship,
  collaboration) are not produced by the pipeline.
- **No entity reconciliation yet.** Persons, publishers and subjects are identified by a slug of their
  name, so spelling variants produce separate nodes, and two different people with the same name would
  be merged. There are no links to Wikidata/DBpedia.
- **Dates are plain text** in the generated graph (`schema:datePublished` is not typed as `xsd:gYear`).
- **Partial downloads.** At most 100 records per author were retrieved (1,167 of 3,583 available).
- **Type heuristic.** `ex:CriticalStudy` is defined but no record in this sample matched it.
- **ABox scale.** The `owl:AllDifferent` list does not scale (see [section 4](#4-the-abox-sample)).
- **Prefix mismatch in the ABox.** `iai_abox.ttl` declares `schema:` as `https://schema.org/` while the
  TBox uses `http://schema.org/`. The ABox triples use the full `http://` IRIs, so nothing breaks today,
  but the prefix declaration should be aligned.
- **Source terms of use.** The bibliographic data comes from the K10plus catalog; check its terms before
  redistributing the downloaded records. No license has been chosen for this repository yet.

## Next steps

1. Finish mapping the pipeline output onto the TBox: move individuals to the `iair:` namespace, declare
   the three provisional classes in the TBox, and generate the `bf:Work` / `bf:Instance` layers.
2. Reconcile entities against Wikidata (QIDs) and add `owl:hasKey`.
3. Add a SHACL shapes layer.
4. Ingest the remaining sources: events calendar, LAI-FU projects and newsletters, IMDb, MusicBrainz.
5. Build the GraphRAG chatbot on top of the graph.
