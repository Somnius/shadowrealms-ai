# ShadowRealms AI - Documentation Index

Welcome to the ShadowRealms AI documentation! This directory contains all project documentation, guides, and references.

**Last Updated:** October 28, 2025 - 20 files (includes PostgreSQL migration docs)

## 📚 Quick Links

### Getting Started
- **[Main Documentation](../SHADOWREALMS_AI_COMPLETE.md)** - Complete platform documentation
- **[Project README](../README.md)** - Quick start and project overview
- **[Docker Setup Guide](DOCKER_ENV_SETUP.md)** - Environment configuration and setup

### Development
- **[Contributing Guidelines](CONTRIBUTING.md)** - How to contribute to the project
- **[Changelog](CHANGELOG.md)** - Version history and updates
- **[Version Bump Process](VERSION_BUMP_PROCESS.md)** - Automated version update workflow
- **[GitHub Setup](GITHUB_SETUP.md)** - Repository and collaboration setup

### Database Migration
- **[PostgreSQL Migration Guide](POSTGRESQL_MIGRATION_GUIDE.md)** - Complete migration from SQLite to PostgreSQL
- **[PostgreSQL Setup](POSTGRESQL_ENV_SETUP.md)** - Secure credential generation
- **[Migration Checklist](MIGRATION_PACKAGE_CHECKLIST.md)** - Pre-flight verification
- **[Migration Success Report](POSTGRESQL_MIGRATION_SUCCESS.md)** - Post-migration verification
- **[Database Migration Planning](DATABASE_MIGRATION_POSTGRESQL.md)** - Technical details and planning

### Current Phase
- **[Phase 3B Implementation](PHASE3B_IMPLEMENTATION.md)** - Advanced campaign & character systems (IN PROGRESS)
- **[Planning Documentation](PLANNING.md)** - Phase planning and summaries

### AI & Memory Systems
- **[AI Systems](AI_SYSTEMS.md)** - Complete AI and memory system documentation
  - OOC Monitoring
  - AI Memory Cleanup
  - Memory Implementation
  - Context Proposals

### Quality & Testing
- **[Quality & Testing](QUALITY_AND_TESTING.md)** - Quality assurance and testing documentation
  - Quality Audits
  - Testing Guides
  - Audit Findings

### Features
- **[Features](FEATURES.md)** - Feature-specific documentation
  - Gothic Horror Theme
  - Invite Code System

### Bug Fixes & Audits
- **[Bug Fixes & Audits](BUG_FIXES_AND_AUDITS.md)** - Bug fixes and technical audits
  - Location Fixes
  - Message Persistence
  - API Audits

### Historical Archives
- **[Project Status Archive](PROJECT_STATUS_ARCHIVED.md)** - Historical status reports
- **[Phase Completions Archive](PHASE_COMPLETIONS_ARCHIVED.md)** - Phase 4 & 5A completion reports
- **[UI/UX Improvements Archive](UI_UX_IMPROVEMENTS_ARCHIVED.md)** - Historical UI/UX changes

## 📖 Documentation Structure (Updated Oct 28, 2025)

```
shadowrealms-ai/
├── README.md                          # Project overview (root)
├── SHADOWREALMS_AI_COMPLETE.md       # Complete documentation (root)
├── LICENSE                            # MIT License (root)
├── version-bump.sh                    # Version update script (root)
│
├── docs/                              # All documentation files (20 files)
│   ├── README.md                      # This file (index)
│   │
│   ├── CHANGELOG.md                   # Version history ⭐
│   ├── CONTRIBUTING.md                # Contribution guide ⭐
│   ├── VERSION_BUMP_PROCESS.md       # Version workflow ⭐
│   │
│   ├── DOCKER_ENV_SETUP.md           # Docker setup ⭐
│   ├── GITHUB_SETUP.md               # GitHub guide ⭐
│   │
│   ├── PHASE3B_IMPLEMENTATION.md     # Phase 3B (active) ⭐
│   ├── PLANNING.md                   # Phase planning 📦
│   │
│   ├── AI_SYSTEMS.md                 # AI & memory systems 📦
│   ├── QUALITY_AND_TESTING.md        # Quality & testing 📦
│   ├── FEATURES.md                   # Features 📦
│   ├── BUG_FIXES_AND_AUDITS.md       # Bug fixes & audits 📦
│   │
│   ├── DATABASE_MIGRATION_POSTGRESQL.md  # PostgreSQL migration planning ⭐
│   ├── POSTGRESQL_ENV_SETUP.md           # PostgreSQL credentials guide ⭐
│   ├── POSTGRESQL_MIGRATION_GUIDE.md     # PostgreSQL migration steps ⭐
│   ├── POSTGRESQL_MIGRATION_SUCCESS.md   # PostgreSQL migration report ⭐
│   ├── MIGRATION_PACKAGE_CHECKLIST.md    # Migration pre-flight check ⭐
│   │
│   ├── PROJECT_STATUS_ARCHIVED.md    # Historical status 📂
│   ├── PHASE_COMPLETIONS_ARCHIVED.md # Phase 4 & 5A 📂
│   └── UI_UX_IMPROVEMENTS_ARCHIVED.md # UI/UX history 📂
│
├── tests/                             # Test suite and docs
│   └── README.md                      # Test documentation
│
├── books/                             # Rule books and docs
│   └── README.md                      # Books documentation
│
└── assets/                            # Project assets
    └── README.md                      # Assets documentation

Legend:
  ⭐ Standalone vital file
  📦 Consolidated file (multiple files merged)
  📂 Archive file
```

## 🎯 Documentation by Topic

### System Architecture
- **SHADOWREALMS_AI_COMPLETE.md**: Complete architecture, components, database schema
- **DOCKER_ENV_SETUP.md**: Environment variables, container configuration
- **PHASE3B_IMPLEMENTATION.md**: Current phase implementation details

### Development Workflow
- **CONTRIBUTING.md**: Code standards, Git workflow, PR process
- **GITHUB_SETUP.md**: Repository setup, branch strategy
- **CHANGELOG.md**: Version history and release notes
- **VERSION_BUMP_PROCESS.md**: Automated version update workflow

### AI & Memory Systems
- **AI_SYSTEMS.md**: Comprehensive AI documentation
  - OOC (Out of Character) Monitoring System
  - AI Memory Cleanup & ChromaDB Management
  - AI Memory Implementation Plans
  - AI Context & Memory Proposals
  - Complete AI Memory System

### Quality & Testing
- **QUALITY_AND_TESTING.md**: Complete QA documentation
  - Quality Audit Reports
  - Quality Audit Findings
  - Quality Fixes Documentation
  - Frontend Manual Testing Guide

### Features
- **FEATURES.md**: Feature implementations
  - Gothic Horror Theme System
  - Invite Code Registration System

### Bug Fixes & Technical Audits
- **BUG_FIXES_AND_AUDITS.md**: Technical fixes and audits
  - Location Bug Fixes
  - Message Persistence Implementation
  - API Endpoint Audits
  - API Audit Summaries

### Planning
- **PLANNING.md**: Development planning
  - Phase 3A Next Steps
  - Phase 3B Summary & Status

### Historical Documentation
- **PROJECT_STATUS_ARCHIVED.md**: Historical project status
- **PHASE_COMPLETIONS_ARCHIVED.md**: Completed phases (4 & 5A)
- **UI_UX_IMPROVEMENTS_ARCHIVED.md**: UI/UX evolution

## 📝 Contributing to Documentation

When adding new documentation:
1. Place it in the `docs/` directory
2. Add an entry to this README
3. Update the main README if it's a major document
4. Follow Markdown best practices
5. Include examples and code snippets where relevant
6. Consider if it should be consolidated into an existing category

## 🔗 External Resources

- [Project Repository](https://github.com/Somnius/shadowrealms-ai)
- [World of Darkness Books](../books/README.md)
- [Test Suite](../tests/README.md)

## 📋 Consolidation History

### October 28, 2025 - Major Consolidation (28 → 15 files)

**Consolidated Groups:**

1. **AI_SYSTEMS.md** (5 files merged)
   - AI_CONTEXT_MEMORY_PROPOSAL.md
   - AI_MEMORY_CLEANUP.md
   - AI_MEMORY_IMPLEMENTATION_PLAN.md
   - AI_MEMORY_SYSTEM_COMPLETE.md
   - OOC_MONITORING.md

2. **QUALITY_AND_TESTING.md** (4 files merged)
   - QUALITY_AUDIT_FINDINGS.md
   - QUALITY_AUDIT_REPORT.md
   - QUALITY_FIXES_COMPLETE.md
   - test_frontend_manual.md

3. **FEATURES.md** (2 files merged)
   - GOTHIC_THEME.md
   - INVITES_README.md

4. **BUG_FIXES_AND_AUDITS.md** (4 files merged)
   - LOCATION_BUG_FIX.md
   - MESSAGE_PERSISTENCE_FEATURE.md
   - API_AUDIT_REPORT.md
   - API_AUDIT_SUMMARY.txt

5. **PLANNING.md** (2 files merged)
   - PHASE_3A_NEXT.md
   - PHASE3B_SUMMARY.md

6. **VERSION_BUMP_PROCESS.md** (1 file merged)
   - VERSION_BUMP_QUICKREF.md (added as section)

**Result:**
- **Before**: 28 files
- **After**: 15 files
- **Saved**: 13 files (46% reduction)

All consolidated files maintain complete content with proper section headers and navigation.

---

**Last Updated**: October 28, 2025  
**Documentation Version**: 0.7.6  
**Total Documentation Files**: 20 (includes PostgreSQL migration docs)

