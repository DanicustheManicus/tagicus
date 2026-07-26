# Tagicus — Music Metadata Detective

## Why It Exists

Every music metadata tool trusts one source and hopes for the best. Picard relies on audio fingerprinting. Mp3tag relies on what you type. When their one source is wrong, your tags are wrong, and you don't even know it.

Tagicus was built out of frustration with that approach. Instead of trusting any single source, it cross-references multiple databases, compares their answers, and picks the one with the most agreement. When sources disagree, it shows you both sides and lets you decide. No silent mistakes, no blind trust.

## What It Does

**Identifies music by stacking multiple signals:**
- Reads existing ID3/MP4/FLAC/APE tags from the file
- Parses the filename and folder structure for clues
- Fingerprints the actual audio using Chromaprint/AcoustID
- Searches MusicBrainz, Discogs, Deezer, TheAudioDB, and Wikidata
- Optional genre-specific databases: Open Opus (classical), VGMdb (game/anime), VocaDB (Vocaloid), Encyclopaedia Metallum (metal)
- Fetches and embeds lyrics via LRCLIB

**Cross-references everything:**
- Each source votes on artist, title, album, year, track, and genre
- Fuzzy matching handles variations ("The Beatles" vs "Beatles, The")
- When local tags and online sources disagree, both paths are searched independently
- Confidence scoring shows how sure Tagicus is about each field

**Organizes your library:**
- Writes verified metadata back into files
- Renames and sorts into customizable folder structures
- Cleans up empty folders after moving files
- Catches and flags duplicate songs
- Preserves embedded artwork and lyrics when clearing junk tags

## Privacy-First Design

Sources are organized into three privacy tiers:

**Tier 1 — Full Privacy:** MusicBrainz, Wikidata, TheAudioDB, LRCLIB, Open Opus, VocaDB. Open source, no tracking, no accounts.

**Tier 2 — Semi-Private:** AcoustID, Discogs, VGMdb, Encyclopaedia Metallum. Community-run services that can see your queries but don't sell your data.

**Tier 3 — Less Private:** Deezer. Commercial service with wider coverage but corporate analytics.

All sources are individually toggleable. Users choose their own privacy/accuracy tradeoff.

## Features

- Native desktop app — no browser tab, no terminal, just double-click and go
- Dashboard with library health overview
- Inline audio player for identifying unknown files
- Click-to-edit fields with source-by-source breakdown
- Re-scan individual songs with manual hints
- Batch operations for bulk tag writing
- Duplicate detection and removal
- Configurable filename and folder patterns
- Settings for tag clearing behavior, field selection, and confidence thresholds
- First-run tutorial walkthrough
- Scan progress with stop button
- Supports MP3, M4A, FLAC, OGG, APE, WAV, AAC, Opus, and WMA

## Getting Started

Download the latest release for your platform from the [Releases page](../../releases):

- **Windows:** run the installer, then launch Tagicus from the Start Menu.
- **Linux:** download the `.AppImage`, make it executable, and double-click it — no install step required.

Your music library location, scan results, and settings are remembered between runs regardless of where the app file lives.

## Technical Stack

- **Backend:** Python 3.12 with FastAPI
- **Database:** SQLite with WAL mode
- **Audio Fingerprinting:** Chromaprint (fpcalc) + AcoustID
- **Frontend:** React (single-file, vendored locally — no CDN dependency, works fully offline)
- **Desktop App:** PyWebView + PyInstaller — a native window, not a browser tab, no Docker required
- **Platforms:** Windows and Linux today, macOS planned

## Created By

Danicus — built with the belief that your music deserves correct metadata, and you deserve to know where that metadata came from.
