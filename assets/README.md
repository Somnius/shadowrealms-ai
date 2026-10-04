# Assets

Images used by the repository's documentation (the README, the wiki). The app's own images (favicons, header and login logos) live in `frontend/public/`.

## Structure

```
assets/
├── logos/          # Project logo variations
│   ├── logo-1.png
│   ├── logo-2.png
│   ├── logo-3.png  # used at the top of the main README
│   └── logo-4.png
├── screenshots/    # App screenshots for the README and the wiki, one folder per release (e.g. v0.9/)
└── README.md       # This file
```

## Notes

- The logo PNGs are 1.6 to 1.9 MB each and are kept in version control; consider Git LFS if more large images are added.
- Screenshots are WebP to keep the repository small. Take them from a test instance with made-up accounts and chronicles, never real player data.
