# Paper images for the horror look

`paper-a4.jpg` and `paper-letter.jpg` are the stained-paper backgrounds of the chronicle PDFs in the
horror look (`look=horror`, `services/pdf_horror.py`). They are made once on a workstation and
committed; the backend has no browser and never makes them.

How they were made (2026-10-17):

- The paper layer of the `background()` SVG from the builder of the horror print PDFs (paper colour,
  mottle, fibre and grain noise, soft stains, one cup ring, the dark vignette), seed 26, made lighter
  for reading (0.26, after the first samples): the mottle, fibre and grain opacity cut to about a
  third (alpha 0.9 → 0.3, 0.35 → 0.12, 0.55 → 0.2, offsets scaled with them), the stains at half
  opacity and the cup ring at 0.06, and the vignette starting at 72 % instead of 58 % (0.2 at 92 %,
  0.6 at the edge instead of 0.38 at 86 % and 0.92), so the text area is close to clean parchment.
- A4 is 210 × 297 mm, Letter 215.9 × 279.4 mm, both portrait, at 250 dpi
  (2067 × 2923 and 2125 × 2750 px).
- Chromium headless screenshot of the SVG at that size (`--screenshot`, `--hide-scrollbars`),
  then `ffmpeg -q:v 5` to JPEG (about 170 KB each). The PDF holds the file's bytes unchanged, once per file.

The frame, thorned corners, blood and text are not in the images: reportlab draws them as vector
paths on top, from the same builder's geometry.
