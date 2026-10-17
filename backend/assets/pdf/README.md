# Paper images for the horror look

`paper-a4.jpg` and `paper-letter.jpg` are the stained-paper backgrounds of the chronicle PDFs in the
horror look (`look=horror`, `services/pdf_horror.py`). They are made once on a workstation and
committed; the backend has no browser and never makes them.

How they were made (2026-10-17):

- The paper layer of the `background()` SVG from the builder of the horror print PDFs (paper colour,
  mottle, fibre and grain noise, soft stains, one cup ring, the dark vignette), seed 26.
- A4 is 210 × 297 mm, Letter 215.9 × 279.4 mm, both portrait, at 250 dpi
  (2067 × 2923 and 2125 × 2750 px).
- Chromium headless screenshot of the SVG at that size (`--screenshot`, `--hide-scrollbars`),
  then `ffmpeg -q:v 5` to JPEG (about 320 KB each).

The frame, thorned corners, blood and text are not in the images: reportlab draws them as vector
paths on top, from the same builder's geometry.
