# Tagicus — Music Metadata Detective

**A Picard/Mp3tag alternative that double-checks itself** — cross-references multiple sources instead of trusting just one.

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

## How It Works

**Reading and analyzing tags**
Tagicus starts with whatever's already embedded in the file (ID3 for MP3, similar formats for MP4/FLAC/APE/etc.), plus it parses the filename and folder name for clues. These two "local" signals get extra weight when they agree with each other, since that usually means a real person already verified that data.

**Fingerprinting (optional)**
Turn on AcoustID in Settings and Tagicus fingerprints the actual audio using Chromaprint — identifying the song by what it *sounds like*, independent of whatever tags or filename it currently has. Useful for mislabeled or blank files. Fully optional, toggle it (and every other source) on or off in Settings.

**Checking itself against every source**
Every enabled source — existing tags, filename, AcoustID, MusicBrainz, Discogs, Deezer, TheAudioDB, Wikidata, plus any genre-specific databases you've turned on — casts a vote for each field (artist, title, album, year, track, genre). Tagicus groups similar-sounding answers together (so "The Beatles" and "Beatles, The" count as agreeing, not conflicting) and goes with whatever the most sources agree on. If everything lines up, that field gets marked high-confidence. If sources genuinely disagree, it's flagged for your review — you see exactly what each source said, instead of Tagicus silently guessing.

**Finding duplicates**
After a scan, Tagicus looks for songs that landed on the same verified artist + title (matched after normalizing case/spacing) and flags them — even across different folders or filenames. Because this compares the *cleaned-up, cross-checked* result rather than raw filenames, it catches duplicates a simple filename search would miss.

**Applying changes**
Once you approve a song (or run a batch apply), Tagicus writes the winning values into the file's real tags — you choose exactly which fields it's allowed to touch. Existing artwork and lyrics are protected by default even when old tags get wiped clean first, and it can strip out legacy leftover tag formats along the way (like APEv2 chunks tacked onto MP3s, or stray ID3 tags accidentally embedded in FLAC files).

If you want your library organized too, Tagicus renames and moves each file into a folder structure you define (like `Artist/Album (Year)/Track - Artist - Title`), skips anything that would overwrite an existing file, and cleans up any folders left empty behind it.

It can also fetch and embed matching lyrics from LRCLIB — synced, time-stamped lyrics if available and preferred, otherwise plain text — right into the file alongside everything else.

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
