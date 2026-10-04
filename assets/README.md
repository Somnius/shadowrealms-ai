# Assets

Images used by the repository's documentation (the README, the wiki). The app's own images (favicons, header and login logos) live in `frontend/public/`.

## Structure

```
assets/
├── logos/          # Project logo variations
│   ├── shadowrealms-banner.png      # 1280x640, top of the README and the GitHub social preview
│   ├── shadowrealms-sigil.svg       # the sigil (original art), same one the app draws
│   ├── shadowrealms-sigil-small.svg # simplified sigil for 16px icons
│   ├── shadowrealms-sigil-512.png
│   ├── shadowrealms-sigil-1024.png
│   ├── logo-1.png
│   ├── logo-2.png
│   ├── logo-3.png  # the pre-0.9 logo (history)
│   └── logo-4.png
├── screenshots/    # App screenshots for the README and the wiki, one folder per release (e.g. v0.9/)
└── README.md       # This file
```

## Notes

- The logo PNGs are 1.6 to 1.9 MB each and are kept in version control; consider Git LFS if more large images are added.
- Screenshots are WebP to keep the repository small. Take them from a test instance with made-up accounts and chronicles, never real player data.

## The sigil

Since 0.9 the logo is the ShadowRealms sigil (thorned ring, crescent moon, inverted triangle, blood drop): the same art the app draws on the login page (`frontend/src/design/atmosphere/SigilReveal.jsx`). The files in `logos/shadowrealms-*` are exports of it. The app's favicons and install icons (`frontend/public/favicon*`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`, `sigil.svg`) are made from the same SVG; the 16px icon uses the simplified version. `logo-1` … `logo-4` are the older logos, kept for history.
