# Version Bump Process

**Last Updated**: 2025-10-28  
**Current Process Version**: 1.0

---

## Overview

This document describes the standardized process for bumping version numbers in the ShadowRealms AI project. Following this process ensures consistency across all configuration files and documentation.

---

## Quick Reference (TL;DR)

**For users who just need the essentials:**

### Version Bump in 3 Steps

**1. Run Script**
```bash
./version-bump.sh 0.7.6 0.7.7
```

**2. Update 3 Files Manually**
```
docs/CHANGELOG.md       → Add new entry at top
README.md               → Add new status section
SHADOWREALMS_AI_COMPLETE.md → Add new version section + update TOC
```

**3. Verify & Commit**
```bash
# Verify
grep -r "OLD_VERSION" --include="*.md" .

# Commit
git add -A
git commit -m "chore: bump version to X.Y.Z"
```

### Automated Updates (11 files)
✅ `.env`, `env.template`, `frontend/package.json`  
✅ `README.md` (badge + preview)  
✅ `SHADOWREALMS_AI_COMPLETE.md` (current refs)  
✅ 6 other docs files

### Common Issues
- **Footer shows wrong version?** → `docker compose restart backend`
- **Script failed?** → Check backups in `backups/version-bump-*/`

---

## Version Numbering

ShadowRealms AI follows [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH
```

- **MAJOR**: Incompatible API changes, major feature overhauls
- **MINOR**: New features, backwards-compatible changes
- **PATCH**: Bug fixes, documentation updates, small improvements

### Examples

- `0.7.6` → `0.7.7`: Bug fix or small improvement (PATCH)
- `0.7.6` → `0.8.0`: New feature or Phase completion (MINOR)
- `0.7.6` → `1.0.0`: Major milestone, production ready (MAJOR)

---

## When to Bump Version

### Patch Version (0.0.X)
- Bug fixes
- Documentation updates
- Small UI improvements
- Performance optimizations
- Security patches

### Minor Version (0.X.0)
- New features
- Phase completions
- Significant enhancements
- New system integrations
- Major documentation additions

### Major Version (X.0.0)
- Production release
- Complete platform overhaul
- Breaking API changes
- Major architecture changes

---

## Automated Version Bump Process

### Step 1: Run the Version Bump Script

```bash
./version-bump.sh <old_version> <new_version>
```

**Example:**
```bash
./version-bump.sh 0.7.6 0.7.7
```

### What the Script Does Automatically

The script will:

1. **Create Backups**
   - All modified files are backed up to `backups/version-bump-YYYYMMDD-HHMMSS/`

2. **Update Configuration Files**
   - `.env` → `VERSION=X.Y.Z`
   - `env.template` → `VERSION=X.Y.Z`
   - `frontend/package.json` → `"version": "X.Y.Z"`

3. **Update Documentation Files**
   - `README.md` → Badge and preview text
   - `SHADOWREALMS_AI_COMPLETE.md` → Current version references
   - `docs/README.md` → Documentation version
   - `docs/PROJECT_STATUS_ARCHIVED.md` → Version header
   - `docs/PHASE3B_IMPLEMENTATION.md` → Version header
   - `docs/PHASE3B_SUMMARY.md` → All version references
   - `docs/OOC_MONITORING.md` → Version footer
   - `demo/README.md` → Demo version note

4. **Verify Changes**
   - Searches for remaining references to old version
   - Reports any unexpected occurrences

### Step 2: Manual Documentation Updates

After running the script, you **MUST** manually update these sections:

#### A. `docs/CHANGELOG.md`

Add a new entry at the **top** of the file:

```markdown
## [X.Y.Z] - YYYY-MM-DD - Title 🎯

### Added
- New feature descriptions

### Changed
- Modified functionality

### Fixed
- Bug fixes

### Documentation
- Updated version references
```

**Template sections:**
- `Added`: New features, capabilities, endpoints
- `Changed`: Modified behavior, improvements
- `Fixed`: Bug fixes, corrections
- `Removed`: Deprecated features
- `Security`: Security fixes
- `Documentation`: Doc updates

#### B. `README.md`

Add a new section under "Current Development Status":

```markdown
### Version X.Y.Z - Title 🎯

**Latest Updates:**
- Feature 1
- Feature 2
- Feature 3
```

Keep the previous version section below it for history.

#### C. `SHADOWREALMS_AI_COMPLETE.md`

1. **Add New Version Section:**

```markdown
## Version X.Y.Z - Title 🎯

### What We Accomplished

Detailed description of changes...

### 🆕 New Features
...

### 🐛 Fixes
...

### 📊 Technical Details
...
```

2. **Update Table of Contents:**

Add link to new version section in the TOC:
```markdown
### **📊 Current Status & Versions**
- [Version X.Y.Z - Title](#version-xyz---title-)
- [Version A.B.C - Previous](#version-abc---previous-)
```

3. **Update Status Indicators:**

Update sections that reference "Current Version":
- Phase 3B Overview
- Quick Start Guide
- Current Status section

---

## Files Updated by Script

### Configuration Files (3 files)
✅ **Automatically updated by script**

```
.env
env.template
frontend/package.json
```

### Documentation Files (8 files)
✅ **Automatically updated by script**

```
README.md (badge + preview text)
SHADOWREALMS_AI_COMPLETE.md (current version refs)
docs/README.md
docs/PROJECT_STATUS_ARCHIVED.md
docs/PHASE3B_IMPLEMENTATION.md
docs/PHASE3B_SUMMARY.md
docs/OOC_MONITORING.md
demo/README.md
```

### Manual Update Required (3 files)
⚠️ **Must be updated manually**

```
docs/CHANGELOG.md (add new entry)
README.md (add new status section)
SHADOWREALMS_AI_COMPLETE.md (add new version section + update TOC)
```

---

## Complete Checklist

Use this checklist for every version bump:

### Pre-Bump
- [ ] All changes committed and tested
- [ ] Decide on version number (MAJOR.MINOR.PATCH)
- [ ] Draft changelog entry content

### Automated Script
- [ ] Run `./version-bump.sh X.Y.Z A.B.C`
- [ ] Verify backups created
- [ ] Review script output for errors
- [ ] Check verification results

### Manual Updates
- [ ] Update `docs/CHANGELOG.md` (new entry at top)
- [ ] Update `README.md` (new status section)
- [ ] Update `SHADOWREALMS_AI_COMPLETE.md` (new version section)
- [ ] Update `SHADOWREALMS_AI_COMPLETE.md` (TOC links)
- [ ] Update `SHADOWREALMS_AI_COMPLETE.md` (current status indicators)

### Verification
- [ ] Search for old version: `grep -r "OLD_VERSION" --include="*.md" .`
- [ ] Verify badge in README.md
- [ ] Check frontend/package.json
- [ ] Check .env and env.template
- [ ] Test footer version display (if backend running)

### Testing
- [ ] Restart backend (loads new VERSION from .env)
- [ ] Check frontend footer displays new version
- [ ] Verify all documentation links work
- [ ] Test basic functionality

### Finalize
- [ ] Review all changes: `git diff`
- [ ] Stage changes: `git add -A`
- [ ] Commit: `git commit -m "chore: bump version to X.Y.Z"`
- [ ] Push (when instructed by user)

---

## Version History Examples

### Good Changelog Entry

```markdown
## [0.7.7] - 2025-10-29 - Chat Improvements 💬

### Added
- Typing indicators for active users
- Message read receipts

### Fixed
- Chat scroll position on new messages
- Markdown rendering in chat

### Documentation
- Updated version references from 0.7.6 to 0.7.7
```

### Good README Status Section

```markdown
### Version 0.7.7 - Chat Improvements 💬

**Latest Updates:**
- 💬 **Typing Indicators**: See when other users are typing
- ✓ **Read Receipts**: Track message delivery status
- 🎯 **Chat Scroll Fix**: Messages auto-scroll correctly
- 📝 **Markdown Rendering**: Improved formatting in chat
```

---

## Troubleshooting

### Script Reports Old Version References

**Problem**: Script finds remaining references after update.

**Solution**:
1. Check if they're historical (changelog, version sections) → OK
2. Check if they're current version refs → Update manually
3. Exclude package dependencies (loguru>=0.7.0) → OK

### Badge Not Updating in README

**Problem**: GitHub badge still shows old version.

**Solution**:
- Check exact format: `version-X.Y.Z-blue`
- Script should update this automatically
- Verify with: `grep "version-" README.md`

### Footer Shows Wrong Version

**Problem**: Frontend footer doesn't show new version.

**Solution**:
1. Verify `.env` updated: `grep "^VERSION=" .env`
2. Restart backend: `docker compose restart backend`
3. Clear browser cache
4. Check `/api/version` endpoint

### Forgot to Run Script

**Problem**: Manually updated some files but not others.

**Solution**:
1. Restore from backups (if available)
2. Run script with correct versions
3. Or manually update all files following this doc

---

## Script Internals

### What Gets Backed Up

All modified files are backed up before changes:
```
backups/version-bump-YYYYMMDD-HHMMSS/
├── .env
├── env.template
├── package.json
├── README.md
├── SHADOWREALMS_AI_COMPLETE.md
└── ... (all documentation files)
```

### Search Patterns

The script uses these patterns to find/update versions:

**Configuration Files:**
- `VERSION=X.Y.Z` (in .env files)
- `"version": "X.Y.Z"` (in package.json)

**Documentation:**
- `version-X.Y.Z-blue` (README badge)
- `Version X.Y.Z Preview` (demo text)
- `**Current Version**: X.Y.Z`
- `**Version:** X.Y.Z`
- `(vX.Y.Z)` (inline version refs)

**Exclusions:**
- Package dependencies (loguru>=0.7.0)
- Historical changelog entries (`## [X.Y.Z]`)
- Version section headers (`## Version X.Y.Z`)

---

## Advanced Usage

### Dry Run (Preview Changes)

To see what would be changed without modifying files:

```bash
# Search for current version
grep -rn "0.7.6" --include="*.md" --include="*.json" --include=".env" . | grep -v node_modules
```

### Restore from Backup

If you need to undo a version bump:

```bash
# List available backups
ls -lt backups/

# Restore from specific backup
BACKUP_DIR="backups/version-bump-20251028-143022"
cp $BACKUP_DIR/* .
cp $BACKUP_DIR/package.json frontend/
```

### Custom Version Updates

For files not covered by the script:

```bash
# Find all references to old version
grep -rn "OLD_VERSION" --include="*.md" .

# Update specific file
sed -i 's/OLD_VERSION/NEW_VERSION/g' path/to/file.md
```

---

## Related Documentation

- [Semantic Versioning 2.0.0](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [Git Workflow](../git_workflow.sh)
- [Backup Script](../backup.sh)

---

## Version History of This Process

- **1.0** (2025-10-28): Initial automated version bump process created

---

**Maintained by**: ShadowRealms AI Development Team  
**Questions?**: Check the script output or review recent version bumps in git history

