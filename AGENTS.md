# AGENTS.md – Rules for Tagicus

## General Rules
- Keep every change small and focused. Do one clear thing at a time.
- Never rewrite or delete working code unless I specifically ask.
- Always explain what you changed and why in plain English.
- If you're unsure about something, ask me before doing it.
- Prefer simple, readable code over clever solutions.

## Project Rules
- Tagicus is a music metadata tagger, similar to MusicBrainz Picard, but improved in usability. It's one shared codebase, built and released for both Windows and Linux.
- Only add OS-specific code when something genuinely requires it (the fingerprinting binary, the app icon, a Windows file-path limit, etc.) - keep those differences small and isolated (an `if` check, not a separate copy of a file), so a fix made for one OS doesn't have to be manually redone for the other.
- When dealing with file paths, don't assume Windows or Linux conventions - use `os.path` so it works correctly on both.
- Do not change the UI or add new features unless I ask.

## Before saying you're done
- Make sure the code runs without errors on whichever OS you tested it on. If you only tested on one, say so explicitly rather than implying both were checked.
- Tell me exactly which files you changed.
- List any new dependencies that need to be installed (and how to install them).
