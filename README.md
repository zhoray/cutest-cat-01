# Mochi — cutest-cat-01 entry

A program that draws a kitten. `main.py` (Python 3, standard library only)
paints "Mochi", a cream kitten with a tilted head, big sparkling eyes, a
ginger forehead patch, a curled striped tail and her favourite ball of yarn,
using signed-distance shapes composited onto float planes, and writes the
picture as a PNG to `/output/entry.png` (or to `$MAKEFUN_OUTPUT_DIR` when
that is set, e.g. for local runs).

The drawing is fully deterministic — no randomness, no clock, no network —
so the program's two runs write byte-identical files.

Run it locally:

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
# writes out/entry.png (1024x1024)
```

Licensed under the MIT License (see `LICENSE`).
