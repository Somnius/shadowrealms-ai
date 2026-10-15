#!/usr/bin/env python3
"""Compare two renders of the score sample by sample (is the v1 preset still the v1 score?).

    python tools/trailer/music/compare.py a.wav b.wav

Prints the lengths, the number of differing samples, the largest difference (dBFS) and where
it is. Exit 0 when the files are identical, 1 otherwise.
"""
import sys

import numpy as np
import soundfile as sf


def main():
    a, sra = sf.read(sys.argv[1], dtype="float64", always_2d=True)
    b, srb = sf.read(sys.argv[2], dtype="float64", always_2d=True)
    print(f"{sys.argv[1]}: {len(a)} samples @ {sra}; {sys.argv[2]}: {len(b)} samples @ {srb}")
    if sra != srb or a.shape != b.shape:
        print("different length or rate")
        sys.exit(1)
    d = np.abs(a - b)
    n = int(np.sum(d > 0))
    if n == 0:
        print("identical: every sample equal")
        sys.exit(0)
    i = int(np.argmax(d.max(axis=1)))
    print(f"{n} of {d.size} samples differ; largest |diff| {d.max():.3e} ({20 * np.log10(d.max()):.1f} dBFS) at {i / sra:.3f} s; "
          f"rms of the difference {20 * np.log10(np.sqrt(np.mean(d ** 2)) + 1e-30):.1f} dBFS")
    sys.exit(1)


if __name__ == "__main__":
    main()
