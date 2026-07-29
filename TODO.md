# Planned Changes

Running list of things to fix/add in future updates. Add to this whenever an idea comes up, so nothing gets lost.

- [ ] Writing tags to `.wav` files fails with "not a Frame instance" - discovered while testing the batch-apply speedup, not yet fixed. WAV routes through `_write_generic` in tag_writer.py; needs investigation into why it's hitting ID3 Frame-construction code.
