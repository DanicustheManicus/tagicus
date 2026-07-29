# SPEC.md – Tagicus

## Overview
Tagicus is a music metadata tagger, similar to MusicBrainz Picard, but improved in usability. One shared codebase, built and released for both Windows and Linux.

## Main Goals
- Select music files or folders
- Look up correct metadata (artist, album, title, year, genre, cover art, etc.)
- Show current tags vs suggested tags clearly
- Let the user accept, reject, or edit suggestions
- Write the new tags cleanly to the files
- Work correctly on both Windows and Linux

## Supported Formats
MP3, FLAC, M4A, OGG, WAV

## Non-Goals
- Do not turn this into a music player
- Do not add accounts, cloud sync, or complicated plugins

## Definition of Done
A feature is done when it works correctly with real music files on both Windows and Linux, and does not break existing features.
