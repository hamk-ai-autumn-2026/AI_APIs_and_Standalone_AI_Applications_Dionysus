#!/usr/bin/env python3
"""Offline unit tests for llm_sources.py — extractors, chunking, prompt building.

No network access and no API calls are required.

Run from the project root:
    python tests/test_extractors.py -v
or:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Make the project root importable when the tests are run from anywhere.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import fitz      # noqa: E402  (PyMuPDF, used to build a tiny test PDF)
import docx      # noqa: E402  (python-docx, used to build a tiny test DOCX)

import llm_sources as ls  # noqa: E402


class TempFileCase(unittest.TestCase):
    """Base class that provides a scratch directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name: str, content: str, encoding: str = "utf-8") -> Path:
        path = self.dir / name
        path.write_text(content, encoding=encoding)
        return path


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #


class ClassificationTests(TempFileCase):

    def test_url_detected(self):
        src = ls.classify_source("https://example.com/article")
        self.assertEqual(src.kind, "url")
        self.assertEqual(src.spec, "https://example.com/article")

    def test_http_uppercase_scheme(self):
        self.assertEqual(ls.classify_source("HTTP://example.com").kind, "url")

    def test_file_kinds(self):
        for name, kind in [
            ("a.txt", "text"), ("b.md", "text"), ("c.csv", "csv"),
            ("d.docx", "docx"), ("e.pdf", "pdf"), ("f.html", "html"),
            ("g.htm", "html"),
        ]:
            path = self.write(name, "x")
            self.assertEqual(ls.classify_source(str(path)).kind, kind, name)

    def test_missing_file_is_source_error(self):
        with self.assertRaises(ls.SourceError):
            ls.classify_source(str(self.dir / "nope.pdf"))

    def test_unsupported_extension(self):
        path = self.write("archive.zip", "PK\x03\x04not really")
        with self.assertRaises(ls.SourceError) as ctx:
            ls.classify_source(str(path))
        self.assertIn("unsupported format", str(ctx.exception))

    def test_legacy_doc_rejected(self):
        path = self.write("old.doc", "whatever")
        with self.assertRaises(ls.SourceError) as ctx:
            ls.classify_source(str(path))
        self.assertIn(".docx", str(ctx.exception))

    def test_extensionless_pdf_sniffed(self):
        path = self.dir / "mysteryfile"
        path.write_bytes(b"%PDF-1.4 fake pdf body")
        self.assertEqual(ls.classify_source(str(path)).kind, "pdf")


# --------------------------------------------------------------------------- #
# Readers
# --------------------------------------------------------------------------- #


class ReaderTests(TempFileCase):

    def test_text_utf8(self):
        path = self.write("n.txt", "héllo wörld — fancy chars")
        self.assertIn("héllo wörld", ls.read_text_file(path))

    def test_binary_rejected(self):
        path = self.dir / "bin.dat"
        path.write_bytes(b"abc\x00\x00\x00def")
        with self.assertRaises(ls.SourceError):
            ls.read_text_file(path)

    def test_csv_rendering(self):
        path = self.write("t.csv", 'region,units\n"North, inc",12\n\nSouth,9\n')
        out = ls.read_csv_file(path)
        self.assertIn("row 1: region | units", out)
        self.assertIn("row 2: North, inc | 12", out)
        # the blank line is file row 3 -> the data line keeps its true file number
        self.assertIn("row 4: South | 9", out)
        self.assertNotIn("row 3:", out)

    def test_csv_lenient_about_unclosed_quotes(self):
        # Python's csv module is deliberately forgiving; unclosed quotes must not crash
        path = self.write("loose.csv", 'a,b\n"unclosed,9\n')
        out = ls.read_csv_file(path)
        self.assertIn("unclosed", out)

    def test_csv_with_nul_rejected(self):
        path = self.dir / "bad.csv"
        path.write_bytes(b"a,b\n1,\x002\n")
        with self.assertRaises(ls.SourceError):
            ls.read_csv_file(path)

    def test_html_sanitized(self):
        path = self.write(
            "p.html",
            "<html><head><title>My Page</title>"
            "<style>p { color: red; } STYLEJUNK_XYZ</style>"
            "<script>alert('SCRIPTJUNK_XYZ');</script></head>"
            "<body><h1>Hello</h1><p>Real content lives here.</p></body></html>",
        )
        out = ls.html_to_text(ls.read_text_file(path))
        self.assertIn("Page title: My Page", out)
        self.assertIn("Real content lives here.", out)
        self.assertNotIn("SCRIPTJUNK_XYZ", out)
        self.assertNotIn("STYLEJUNK_XYZ", out)

    def test_pdf_extraction(self):
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 90), "The mitochondrial rate is 42 units.", fontsize=11)
        doc.save(self.dir / "t.pdf")
        doc.close()
        out = ls.read_pdf_file(self.dir / "t.pdf")
        self.assertIn("[page 1]", out)
        self.assertIn("42 units", out)

    def test_docx_extraction_with_table(self):
        d = docx.Document()
        d.add_paragraph("Intro paragraph about testing.")
        t = d.add_table(rows=1, cols=2)
        t.rows[0].cells[0].text = "cmd"
        t.rows[0].cells[1].text = "purpose"
        d.save(self.dir / "t.docx")
        out = ls.read_docx_file(self.dir / "t.docx")
        self.assertIn("Intro paragraph about testing.", out)
        self.assertIn("cmd | purpose", out)


# --------------------------------------------------------------------------- #
# Chunking and prompt assembly
# --------------------------------------------------------------------------- #


class ChunkingTests(unittest.TestCase):

    def test_small_text_single_chunk(self):
        self.assertEqual(ls.split_into_chunks("tiny", 1000), ["tiny"])

    def test_chunk_count_and_overlap(self):
        text = "\n".join(f"line {i}" for i in range(1000))   # ~7,900 chars
        chunks = ls.split_into_chunks(text, chunk_chars=1000, overlap=200)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(c) <= 1000 for c in chunks))
        # overlap: the tail of chunk 1 should appear at the start of chunk 2
        self.assertTrue(any(chunks[0][-60:] in chunks[1][:400] for _ in [0]))

    def test_chunk_chars_must_exceed_overlap(self):
        with self.assertRaises(ValueError):
            ls.split_into_chunks("x" * 100, chunk_chars=50, overlap=60)


class PromptTests(unittest.TestCase):

    def test_source_block_labels(self):
        block = ls.source_block(1, "report.pdf", "pdf", "CONTENT", extra="part 1/3")
        self.assertIn("===== SOURCE 1 BEGIN: report.pdf (type: pdf", block)
        self.assertIn("UNTRUSTED DATA", block)
        self.assertIn("part 1/3", block)
        self.assertTrue(block.rstrip().endswith("===== SOURCE 1 END: report.pdf ====="))

    def test_user_prompt_contains_query_and_blocks(self):
        blocks = [ls.source_block(1, "a.txt", "text", "AAA")]
        prompt = ls.build_user_prompt("What is this?", blocks)
        self.assertTrue(prompt.startswith("QUERY: What is this?"))
        self.assertIn("AAA", prompt)
        self.assertIn("1 source block", prompt)

    def test_system_prompt_warns_about_injection(self):
        self.assertIn("UNTRUSTED", ls.SYSTEM_PROMPT)
        self.assertIn("NEVER", ls.SYSTEM_PROMPT)
        self.assertIn("prompt-injection", ls.SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
