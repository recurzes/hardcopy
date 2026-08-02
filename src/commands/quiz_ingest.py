"""
quiz_ingest.py — Study Notes Ingestion Pipeline

Extracts text from your study documents, chunks it, embeds it locally,
stores it in SQLite, then pre-generates >=50 quiz Q&A pairs using your
configured LLM so the quiz daemon can run without any live LLM calls.

Usage:
    python -m src.commands.quiz_ingest notes.pdf re_notes.txt
    python -m src.commands.quiz_ingest notes.pdf --reset
    python -m src.commands.quiz_ingest --list
    python -m src.commands.quiz_ingest --regen-pool
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from src.config import QUIZ_POOL_MIN, QUIZ_TOPIC
from src.db import (
    bulk_insert_quiz_pool,
    clear_quiz_knowledge,
    count_quiz_pool,
    insert_knowledge_chunks,
    list_knowledge_sources,
)
from src.llm import LLMError, llm_complete

# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_file(path: Path) -> str:
    """Extract plain text from a file based on its extension."""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix in (".txt", ".md", ".rst", ".markdown"):
        return path.read_text(encoding="utf-8", errors="replace")
    elif suffix == ".docx":
        return _extract_docx(path)
    else:
        # Fallback: try to read as text
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise ValueError(f"Cannot read {path.name}: {e}") from e


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError(
            "pypdf not installed. Run: pip install pypdf"
        )
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def _extract_docx(path: Path) -> str:
    try:
        import docx
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        raise RuntimeError(
            "python-docx not installed. Run: pip install python-docx"
        )


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_words: int = 150,
    overlap_words: int = 30,
) -> list[str]:
    """Split text into overlapping word-count windows."""
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunk = " ".join(words[start:end])
        if chunk.strip():
            chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_words - overlap_words

    return chunks


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def load_embedder():
    """Load the sentence-transformers model (cached after first download)."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "sentence-transformers not installed. "
            "Run: pip install sentence-transformers"
        )
    print("Loading embedding model (all-MiniLM-L6-v2)...")
    return SentenceTransformer("all-MiniLM-L6-v2")


def embed_chunks(model, chunks: list[str]) -> list[bytes]:
    """Return a list of embedding byte-blobs (float32 arrays) for each chunk."""
    import numpy as np

    embeddings = model.encode(chunks, show_progress_bar=True, batch_size=32)
    return [e.astype(np.float32).tobytes() for e in embeddings]


# ---------------------------------------------------------------------------
# Q&A generation
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a quiz master generating study questions for someone learning {topic}.

Given the study notes below, generate exactly ONE question and its complete answer.
The question must be specific, factual, and answerable directly from the notes.
Do NOT reference "the notes" or "the text" — phrase it as a standalone question.

Respond in EXACTLY this format (nothing else):
QUESTION: <your question here>
ANSWER: <your complete answer here>"""

USER_PROMPT_TEMPLATE = """STUDY NOTES:
{chunk_text}"""


def generate_qa_from_chunk(chunk: str, topic: str) -> tuple[str, str] | None:
    """Call LLM to generate one Q&A pair from a chunk. Returns (question, answer) or None."""
    try:
        system = SYSTEM_PROMPT.format(topic=topic)
        user = USER_PROMPT_TEMPLATE.format(chunk_text=chunk)
        response = llm_complete(system, user, timeout=60.0)
    except LLMError as e:
        print(f"  [LLM error] {e}")
        return None

    # Parse QUESTION: / ANSWER: format
    question, answer = "", ""
    for line in response.splitlines():
        line = line.strip()
        if line.upper().startswith("QUESTION:"):
            question = line[len("QUESTION:"):].strip()
        elif line.upper().startswith("ANSWER:"):
            answer = line[len("ANSWER:"):].strip()
        elif answer:
            # Multi-line answers
            answer += " " + line

    if not question or not answer:
        return None
    return question, answer


def generate_question_pool(
    chunks: list[str],
    chunk_ids: list[int],
    topic: str,
    min_questions: int,
) -> list[dict]:
    """Generate at least min_questions Q&A pairs, cycling chunks if needed."""
    import random

    qa_pairs: list[dict] = []
    total = len(chunks)

    if total == 0:
        print("No chunks available to generate questions from.")
        return []

    # Build a shuffled work queue; cycle through if we need more than total chunks
    indices = list(range(total))
    random.shuffle(indices)
    queue = indices[:]

    attempt = 0
    max_attempts = min_questions * 3  # give up after 3x to avoid infinite loop

    print(f"Generating questions (target: {min_questions})...")
    while len(qa_pairs) < min_questions and attempt < max_attempts:
        if not queue:
            # Re-shuffle and recycle
            queue = indices[:]
            random.shuffle(queue)

        idx = queue.pop(0)
        chunk_text = chunks[idx]
        chunk_db_id = chunk_ids[idx]

        # Progress bar
        done = len(qa_pairs)
        bar_width = 20
        filled = int(bar_width * done / min_questions)
        bar = "=" * filled + ">" + " " * (bar_width - filled - 1)
        print(f"\r  [{bar}] {done}/{min_questions}", end="", flush=True)

        result = generate_qa_from_chunk(chunk_text, topic)
        if result:
            question, answer = result
            qa_pairs.append({
                "question": question,
                "answer": answer,
                "source_chunk": chunk_db_id,
            })

        attempt += 1

    print(f"\r  [{'=' * bar_width}] {len(qa_pairs)}/{min_questions}", flush=True)
    return qa_pairs


# ---------------------------------------------------------------------------
# Pool regeneration (without re-ingesting)
# ---------------------------------------------------------------------------

def regen_pool_from_existing(topic: str, min_questions: int) -> None:
    """Re-generate the question pool from already-ingested chunks."""
    from src.db import get_connection

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, content FROM quiz_knowledge ORDER BY RANDOM()"
    ).fetchall()

    if not rows:
        print("No ingested content found. Run quiz_ingest with file paths first.")
        return

    chunks = [r["content"] for r in rows]
    chunk_ids = [r["id"] for r in rows]

    # Clear existing pool
    conn.executescript("DELETE FROM quiz_pool;")
    conn.commit()
    print(f"Cleared existing pool. Generating {min_questions}+ new questions...")

    qa_pairs = generate_question_pool(chunks, chunk_ids, topic, min_questions)
    if qa_pairs:
        bulk_insert_quiz_pool(qa_pairs)
    print(f"\nDone. Pool now has {len(qa_pairs)} questions.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Ingest study documents and generate a quiz question pool"
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="Path(s) to document(s) to ingest (PDF, TXT, MD, DOCX)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear the knowledge base and question pool before ingesting",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List ingested sources and pool statistics, then exit",
    )
    parser.add_argument(
        "--regen-pool",
        action="store_true",
        dest="regen_pool",
        help="Re-generate the question pool from existing chunks (no re-ingest)",
    )
    parser.add_argument(
        "--topic",
        default=None,
        help=f"Topic label for LLM prompt (default: QUIZ_TOPIC env var = '{QUIZ_TOPIC}')",
    )
    parser.add_argument(
        "--min-questions",
        type=int,
        default=None,
        dest="min_questions",
        help=f"Minimum questions to generate (default: QUIZ_POOL_MIN env var = {QUIZ_POOL_MIN})",
    )
    args = parser.parse_args(argv)

    topic = args.topic or QUIZ_TOPIC
    min_questions = args.min_questions or QUIZ_POOL_MIN

    # -- --list --------------------------------------------------------------
    if args.list:
        sources = list_knowledge_sources()
        pool_count = count_quiz_pool()
        if not sources:
            print("No documents ingested yet.")
        else:
            print(f"{'Source File':<40} {'Chunks':>6}  Last Ingested")
            print("-" * 72)
            for s in sources:
                print(
                    f"{s['source_file']:<40} {s['chunk_count']:>6}  {s['last_ingested']}"
                )
        print(f"\nQuiz pool: {pool_count} pending questions")
        return

    # -- --regen-pool --------------------------------------------------------
    if args.regen_pool:
        regen_pool_from_existing(topic, min_questions)
        return

    # -- Ingest files --------------------------------------------------------
    if not args.files:
        parser.print_help()
        return

    paths = [Path(f) for f in args.files]
    for p in paths:
        if not p.exists():
            print(f"Error: File not found: {p}")
            sys.exit(1)

    if args.reset:
        print("Clearing existing knowledge base and question pool...")
        clear_quiz_knowledge()

    # Load embedder once
    try:
        embedder = load_embedder()
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    all_chunks: list[str] = []
    all_source_files: list[str] = []
    total_files_ok = 0

    for path in paths:
        print(f"Extracting text from {path.name}...")
        try:
            text = extract_text_from_file(path)
        except Exception as e:
            print(f"  Error reading {path.name}: {e}")
            continue

        if not text.strip():
            print(f"  Warning: {path.name} appears empty, skipping.")
            continue

        chunks = chunk_text(text)
        print(f"  -> {len(chunks)} chunks")
        all_chunks.extend(chunks)
        all_source_files.extend([str(path)] * len(chunks))
        total_files_ok += 1

    if not all_chunks:
        print("No content to ingest.")
        return

    print(f"\nEmbedding {len(all_chunks)} total chunks...")
    embeddings = embed_chunks(embedder, all_chunks)

    # Build DB rows
    chunk_rows = [
        {
            "source_file": all_source_files[i],
            "chunk_index": i,
            "content": all_chunks[i],
            "embedding": embeddings[i],
        }
        for i in range(len(all_chunks))
    ]

    print("Saving chunks to knowledge base...")
    insert_knowledge_chunks(chunk_rows)

    # Retrieve the IDs of the just-inserted chunks to link Q&A pairs
    from src.db import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM quiz_knowledge ORDER BY id DESC LIMIT ?",
        (len(all_chunks),),
    ).fetchall()
    chunk_ids = [r["id"] for r in reversed(rows)]

    # Generate question pool
    print()
    qa_pairs = generate_question_pool(all_chunks, chunk_ids, topic, min_questions)

    if qa_pairs:
        print(f"Saving {len(qa_pairs)} questions to quiz pool...")
        bulk_insert_quiz_pool(qa_pairs)
    else:
        print("Warning: No questions were generated. Check your LLM config.")

    pool_total = count_quiz_pool()
    print(
        f"\nDone! Ingested {len(all_chunks)} chunks from {total_files_ok} file(s). "
        f"Quiz pool: {pool_total} pending questions. Ready to quiz!"
    )


if __name__ == "__main__":
    main()
