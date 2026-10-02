"""Generates a structured markdown note from a transcript via the configured
LLM, and saves it to the local notes directory."""

from __future__ import annotations

import re
from pathlib import Path

from openai import OpenAI

NOTE_PROMPT = """You will be given the transcript of a video. Produce a structured \
markdown note with exactly these sections, in this order:

## Executive Summary
A short paragraph summarizing the video's content.

## Key Takeaways & Action Items
A bulleted list of the most important points and any concrete action items.

## Full Reference Notes
A more detailed, organized set of notes covering the transcript's content.

Transcript:
---
{transcript}
---
"""


class NotesService:
    def __init__(
        self,
        llm_api_base: str,
        llm_api_key: str,
        llm_model: str,
        llm_timeout: int,
        notes_dir: str,
    ) -> None:
        self.llm = OpenAI(base_url=llm_api_base, api_key=llm_api_key)
        self.llm_model = llm_model
        self.llm_timeout = llm_timeout
        self.notes_dir = Path(notes_dir)
        self.notes_dir.mkdir(parents=True, exist_ok=True)

    def generate_note(self, task_id: int, source_url: str, transcript: str) -> tuple[Path, int]:
        response = self.llm.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": "You write clear, well-organized markdown notes."},
                {"role": "user", "content": NOTE_PROMPT.format(transcript=transcript)},
            ],
            max_tokens=2048,
            temperature=0.3,
            timeout=self.llm_timeout,
        )
        body = response.choices[0].message.content or "(empty response from LLM)"

        header = f"# Notes: {source_url}\n\nSource: {source_url}\nTask ID: #{task_id}\n\n"
        full_note = header + body

        slug = re.sub(r"[^a-zA-Z0-9]+", "-", source_url).strip("-")[-40:] or "note"
        note_path = self.notes_dir / f"{task_id}-{slug}.md"
        note_path.write_text(full_note, encoding="utf-8")

        word_count = len(full_note.split())
        return note_path, word_count
