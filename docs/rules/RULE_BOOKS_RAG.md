# Rule books in RAG: data contract

The importer (`books/import_books.py`) writes this; the backend retrieval (`services/rag_service.py`, `services/rules_edition.py`) reads it. Both sides must follow it. Decisions behind it: the research of 2026-10-04 and Lef's answers (official books only; adventures per chronicle, opt-in; Classic = Revised Vampire/Werewolf/Mage with a text layer, no OCR for now).

## Collections (ChromaDB, all embedded with the app's bge-m3 embedding function via `services.vector_store.get_rag_collection`)

| Collection | Contents |
|---|---|
| `rule_books_v5` | Global V5 books (`campaign_id` 0) |
| `rule_books_classic` | Global Classic books (`campaign_id` 0) |
| `rule_books_chronicle` | Books attached to one chronicle on purpose (adventures), `campaign_id` = that chronicle, any edition |

The old `rule_books` collection is no longer written. It is empty on the live install.

## Chunk

- **id:** `"{book_id}:{chunk_index:05d}"` (deterministic, so re-imports `upsert` and a book is removed with `delete(where={"book_id": ...})`). In `rule_books_chronicle` the id is prefixed with the chronicle, `"c{campaign_id}:{book_id}:{chunk_index:05d}"`, because one adventure can be attached to several chronicles.
- **document:** `"{title} › {heading_path}\n\n{text}"`. `text` is about 300 tokens (hard max 512), sentence-aligned, within one section of the book.
- **metadata** (all scalar, no lists):

| Key | Type | Values |
|---|---|---|
| `book_id` | str | slug of the title, e.g. `v5-corebook`, `vtm-revised-core` |
| `title` | str | e.g. `Vampire: The Masquerade Corebook (2019)` |
| `edition` | str | `v5` or `classic` |
| `line` | str | `vampire`, `werewolf`, `mage`, or `all` (applies to every line) |
| `version` | str | `v5`, `revised` (later maybe `v20`, `2nd`) |
| `kind` | str | `rules`, `sidebar`, `example`, `lore`, `fiction`, `adventure` |
| `heading_path` | str | `Chapter › Section › Subsection` |
| `page` | int | printed page number (what the book shows) |
| `page_pdf` | int | 1-based page index in the PDF |
| `chunk_index` | int | order within the book |
| `precedence` | int | lower wins when books disagree (V5: corebook 10, Player's Guide v2 20, Companion 30, other supplements 40, lore 50) |
| `official` | bool | always true for now (official books only) |
| `year` | int | publication year |
| `campaign_id` | int | 0 for global, the chronicle id in `rule_books_chronicle` |
| `content_sha` | str | sha1 of `text`, for de-duplication |

## Retrieval rules (backend)

- Pick the collection by the chronicle's `rules_edition`; also query `rule_books_chronicle` with `campaign_id` = the chronicle.
- Classic: filter `line` to the chronicle's game line or `all` (a Vampire chronicle never gets Werewolf rules). V5 is Vampire only.
- Laya's intent decides whether and what to search: `rules_question`, `dice`, `combat` → `kind` in rules/sidebar/example, k=4; `roleplay` → `kind` in lore/adventure, k=2; `general` → no search.
- A relevance cutoff (cosine distance) drops weak matches; the query is embedded once per message.
- Cite as `Title › heading_path, p. N`.
