# Version Bump Process

**Last Updated**: 2026-10-04 (v0.9.0)

How to change the version number and cut a release.

---

## Quick reference

```bash
./scripts/version-bump.sh 0.9.0 0.9.1     # bump the version markers
# write the release notes by hand (see below)
./scripts/build-frontend.sh                # footer badge comes from the build
docker compose up -d backend               # /api/version comes from .env VERSION
git commit -am "release 0.9.1"
git tag v0.9.1                             # on main
```

---

## Version numbering

ShadowRealms AI follows [Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).

- **PATCH** (`0.9.0` to `0.9.1`): bug fixes, small improvements, documentation.
- **MINOR** (`0.9.x` to `0.10.0`): new features, a finished roadmap milestone.
- **MAJOR** (`0.x` to `1.0.0`): first stable release, breaking changes.

---

## What the script changes

`scripts/version-bump.sh <old> <new>` only touches the real version markers:

| File | What changes | Used by |
|------|--------------|---------|
| `.env` | `VERSION=X.Y.Z` | backend `/api/version` (passed in by `docker-compose.yml`) |
| `env.template` | `VERSION=X.Y.Z` | new installs |
| `frontend/package.json` | the package's own `"version"` | footer version badge (read at build time) |
| `frontend/package-lock.json` | the top-level `"version"` and `packages[""].version` only | keeps `npm ci` consistent |
| `README.md` | the shields.io version badge | GitHub page |

It backs each file up to `backups/version-bump-YYYYMMDD-HHMMSS/` first (the `backups/` folder is gitignored), then prints the markers so you can check them.

It does **not** edit any other documentation. Earlier versions of the script also rewrote "Version X", "(vX)" and similar strings in several docs. That turned historical labels (for example the v0.7.0 Phase 3B section in `SHADOWREALMS_AI_COMPLETE.md` and the demo video note) into the current version, so it was removed in v0.9.0 and the old labels were restored. Past versions mentioned in docs are on purpose; leave them alone.

---

## Release notes (by hand)

1. **`docs/CHANGELOG.md`**: move the `## [Unreleased]` items into a new entry at the top:

   ```markdown
   ## [X.Y.Z] - YYYY-MM-DD - Short title

   ### Added
   ### Changed
   ### Fixed
   ### Security
   ```

2. **`SHADOWREALMS_AI_COMPLETE.md`**: add a `## Version X.Y.Z - Title` section above the previous one and a matching entry in the table of contents. Keep it short: a summary plus links to the changelog and the relevant docs, without repeating the changelog.

3. **`README.md`**: update anything in the text that describes the current release. The README is also shown inside the app (`/api/readme`, the README dialog), so keep its markdown simple.

4. **Docs**: if the release changed setup, environment variables, or behaviour, update the matching file in `docs/` (see [docs/README.md](README.md)).

---

## Checklist

- [ ] CI is green on `main` (Python checks, backend unit tests, schema + `migrate_db`, frontend tests + build, CodeQL).
- [ ] `./scripts/version-bump.sh OLD NEW` ran, and the printed markers all show `NEW`.
- [ ] `docs/CHANGELOG.md`, `SHADOWREALMS_AI_COMPLETE.md` and `README.md` updated.
- [ ] `./scripts/build-frontend.sh` rebuilt the frontend; the footer shows `vNEW`.
- [ ] `docker compose up -d backend` (or a restart) and `curl -s http://localhost/api/version` shows `NEW`.
- [ ] Committed on `main` and tagged `vNEW`.

---

## Troubleshooting

**Footer shows the old version.** The footer reads `frontend/package.json` at build time. Run `./scripts/build-frontend.sh` again.

**`/api/version` shows the old version.** The backend reads `VERSION` from the environment that `docker-compose.yml` passes in from `.env`. Check `.env`, then recreate the backend container (`docker compose up -d backend`); a plain restart does not pick up a changed `.env`.

**The script warns that `env.template` has a different version.** The `<old>` argument does not match the current version. Check `grep ^VERSION= env.template` and run it again with the right old version.

**Undo a bump.** Copy the files back from the newest `backups/version-bump-*/` folder, or `git checkout -- env.template frontend/package.json frontend/package-lock.json README.md` (`.env` is not tracked, so restore it from the backup).

---

## Related documentation

- [CHANGELOG.md](CHANGELOG.md): version history
- [CONTRIBUTING.md](CONTRIBUTING.md): commit style and pull requests
- [DOCKER_ENV_SETUP.md](DOCKER_ENV_SETUP.md): environment variables, including `VERSION`
