"""YouTube transcript extraction via yt-dlp.

Fetches existing captions/subtitles only (manual or auto-generated) — never
downloads audio/video and never transcribes. Audio-only videos with no
captions available raise NoTranscriptAvailable rather than silently failing
or hanging; a real Whisper-based fallback for that case is a deliberately
deferred follow-up (tracked in docs/ARCHITECTURE.md), not an oversight — the
common case (videos with existing captions) is what this project covers for
now, scoped to avoid pulling in a full speech-to-text model/container
before there's a concrete need for one.
"""

from __future__ import annotations

import re

import yt_dlp


class NoTranscriptAvailable(Exception):
    pass


class TranscriptService:
    def fetch_transcript(self, url: str, lang: str = "en") -> str:
        extract_opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [lang],
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(extract_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        subtitles = info.get("subtitles") or {}
        auto_captions = info.get("automatic_captions") or {}
        tracks = subtitles.get(lang) or auto_captions.get(lang)
        if not tracks:
            raise NoTranscriptAvailable(
                f"No '{lang}' transcript/captions available for this video "
                "(audio-only speech-to-text fallback is not implemented yet)."
            )

        vtt_track = next((t for t in tracks if t.get("ext") == "vtt"), tracks[0])
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            vtt_text = ydl.urlopen(vtt_track["url"]).read().decode("utf-8", errors="replace")

        return self._vtt_to_plain_text(vtt_text)

    @staticmethod
    def _vtt_to_plain_text(vtt: str) -> str:
        lines: list[str] = []
        for raw_line in vtt.splitlines():
            line = raw_line.strip()
            if not line or line.startswith(("WEBVTT", "Kind:", "Language:")):
                continue
            if "-->" in line or line.isdigit():
                continue
            line = re.sub(r"<[^>]+>", "", line)  # strip inline VTT timing tags
            if line and (not lines or lines[-1] != line):
                lines.append(line)
        return " ".join(lines)
