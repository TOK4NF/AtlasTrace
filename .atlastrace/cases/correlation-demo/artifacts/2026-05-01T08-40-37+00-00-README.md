# AtlasTrace

AtlasTrace is a massive Python multitool for passive OSINT work, investigation case management, evidence capture, entity graphing, document and media triage, archive workflows, breach checks, and cross-source correlation reporting.

The goal is to combine the best parts of:

- a caseboard
- a public-source collection pipeline
- a lightweight evidence locker
- a graph of people, organizations, domains, handles, files, and URLs
- a correlation engine that cross-references one dataset against others
- a Have I Been Pwned style breach intelligence layer
- a reporting and export layer

AtlasTrace is intentionally scoped for lawful, passive, user-directed research. It does **not** implement intrusive scanning, brute force, credential attacks, exploit automation, stealth, or malware-like behavior.

## What it already includes

- SQLite-backed case management
- entity and relationship graph storage
- notes and evidence artifacts
- public web capture with raw HTML preservation
- document import with observable extraction
- media triage with optional EXIF and OCR
- username mapping across common public platforms
- dataset-on-dataset correlation reports
- HIBP-compatible account and password checks
- archive workflow helpers for Wayback-style preservation
- Markdown and Mermaid report export
- plugin registry for future modules
- optional FastAPI service layer

## Why this shape

AtlasTrace takes inspiration from several public projects and ecosystems:

- Aleph's investigation and dataset model
- OpenCTI's connector and knowledge-graph mindset
- MetaOSINT-style source aggregation
- Cyberbro-style analysis workflow separation
- Trafilatura for clean web text extraction
- ExifTool for rich metadata extraction
- Tesseract for OCR
- Typer/FastAPI/SQLModel style modularity for later growth

More detail and source links are in [docs/SOURCES.md](./docs/SOURCES.md).

## Repository layout

```text
.
|-- README.md
|-- docs/
|   `-- SOURCES.md
|-- src/
|   `-- atlastrace/
|       |-- __init__.py
|       |-- __main__.py
|       |-- analysis.py
|       |-- api.py
|       |-- cli.py
|       |-- settings.py
|       |-- storage.py
|       |-- utils.py
|       |-- plugins/
|       |   |-- __init__.py
|       |   |-- base.py
|       |   `-- registry.py
|       `-- services/
|           |-- __init__.py
|           |-- cases.py
|           |-- common.py
|           |-- entities.py
|           |-- ingest.py
|           |-- media.py
|           `-- reporting.py
```

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
atlastrace init
atlastrace case-create "Example Investigation" --description "Workspace bootstrap"
atlastrace entity-add example-investigation person "Jane Doe" --source manual
atlastrace note-add example-investigation "Lead" "Possible link between the handle and the domain."
atlastrace report-md example-investigation
```

If you do not want to install the package yet:

```powershell
$env:PYTHONPATH = "src"
python -m atlastrace.cli init
python -m atlastrace.cli case-create "Example Investigation"
```

## CLI overview

```text
atlastrace init
atlastrace modules
atlastrace case-create TITLE [--slug ...] [--description ...]
atlastrace case-list
atlastrace note-add CASE TITLE BODY
atlastrace entity-add CASE KIND VALUE [--name ...] [--source ...] [--confidence ...]
atlastrace entity-list CASE
atlastrace link CASE FROM_ID TO_ID LABEL [--source ...]
atlastrace web-capture CASE URL [--label ...]
atlastrace doc-import CASE PATH
atlastrace dataset-import CASE PATH [--label ...]
atlastrace correlate CASE [--min-sources 2] [--output ...]
atlastrace media-inspect CASE PATH
atlastrace identity-map CASE HANDLE [--platforms ...] [--fetch]
atlastrace breach-check CASE ACCOUNT [--full]
atlastrace password-check CASE [--password ...]
atlastrace archive CASE URL [--submit]
atlastrace report-md CASE [--output ...]
atlastrace report-graph CASE [--output ...]
atlastrace serve [--host 127.0.0.1] [--port 8000]
```

## Example workflows

### 1. Build a case

```powershell
atlastrace case-create "Acme Research"
atlastrace entity-add acme-research organization "Acme Corp"
atlastrace entity-add acme-research domain "acme.example"
atlastrace link acme-research 1 2 owns
```

### 2. Capture a public page

```powershell
atlastrace web-capture acme-research https://example.org/article
```

This stores:

- raw capture under `.atlastrace/cases/<slug>/captures/`
- extracted observables such as URLs, domains, emails, and IPv4 values
- an artifact record in SQLite

### 3. Import a file

```powershell
atlastrace doc-import acme-research .\notes.html
atlastrace media-inspect acme-research .\image.jpg
```

### 4. Correlate one source with another

```powershell
atlastrace dataset-import acme-research .\dump_a.txt --label "dump-a"
atlastrace dataset-import acme-research .\dump_b.csv --label "dump-b"
atlastrace correlate acme-research --min-sources 2
```

### 5. Map a public username

```powershell
atlastrace identity-map acme-research nottoka --fetch
```

That builds a candidate list of public profile URLs and, when `--fetch` is enabled, tries a passive HTTP request to collect status and page title information.

## Optional integrations

AtlasTrace runs with no required third-party dependency, but it can grow when extras are installed:

- `pip install -e .[extract]` enables Trafilatura-based HTML text extraction
- `pip install -e .[media]` enables Pillow and pytesseract hooks
- install `exiftool` in your system `PATH` for deep media metadata
- install `pip install -e .[api]` for the FastAPI service layer

### 6. Check breach intelligence

```powershell
atlastrace breach-check acme-research [email protected]
atlastrace password-check acme-research
```

The account lookup requires `HIBP_API_KEY` in your environment. The password check uses the HIBP k-anonymity range model and does not store the cleartext password.

## Safety model

AtlasTrace is designed for:

- public-source investigation
- journaling and evidence preservation
- content extraction from user-supplied files and URLs
- passive enrichment

AtlasTrace is not designed for:

- port scanning
- vulnerability probing
- exploit delivery
- account intrusion
- credential attacks
- stealth or evasion

## Roadmap

- tag system and saved searches
- richer schema types inspired by FollowTheMoney and CTI platforms
- timeline view and event extraction
- browser-rendered capture provider for dynamic pages
- entity resolution and duplicate clustering
- local embeddings and semantic search
- plugin marketplace for source-specific collectors
- PDF parsing and richer report templates
