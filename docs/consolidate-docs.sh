#!/bin/bash
#
# ShadowRealms AI - Documentation Consolidation Script
# 
# This script consolidates multiple documentation files into organized categories
#

set -e

DOCS_DIR="/home/lef/dev/shadowrealms-ai_dev/shadowrealms-ai/docs"
cd "$DOCS_DIR"

echo "Creating consolidated documentation files..."

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. AI_SYSTEMS.md
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cat > AI_SYSTEMS.md << 'EOFSYS'
# AI & Memory Systems Documentation

**Last Updated**: 2025-10-28  
**Version**: 0.7.6

This document consolidates all AI and memory system documentation for ShadowRealms AI.

---

## Table of Contents

1. [Overview](#overview)
2. [OOC Monitoring System](#ooc-monitoring-system)
3. [AI Memory Cleanup](#ai-memory-cleanup)
4. [AI Memory Implementation](#ai-memory-implementation)
5. [AI Context & Memory Proposal](#ai-context--memory-proposal)
6. [Complete AI Memory System](#complete-ai-memory-system)

---

EOFSYS

# Append each file with section headers
echo -e "\n## OOC Monitoring System\n" >> AI_SYSTEMS.md
tail -n +3 OOC_MONITORING.md >> AI_SYSTEMS.md

echo -e "\n---\n\n## AI Memory Cleanup\n" >> AI_SYSTEMS.md
tail -n +3 AI_MEMORY_CLEANUP.md >> AI_SYSTEMS.md

echo -e "\n---\n\n## AI Memory Implementation\n" >> AI_SYSTEMS.md
tail -n +3 AI_MEMORY_IMPLEMENTATION_PLAN.md >> AI_SYSTEMS.md

echo -e "\n---\n\n## AI Context & Memory Proposal\n" >> AI_SYSTEMS.md
tail -n +3 AI_CONTEXT_MEMORY_PROPOSAL.md >> AI_SYSTEMS.md

echo -e "\n---\n\n## Complete AI Memory System\n" >> AI_SYSTEMS.md
tail -n +3 AI_MEMORY_SYSTEM_COMPLETE.md >> AI_SYSTEMS.md

echo "✓ Created AI_SYSTEMS.md"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. QUALITY_AND_TESTING.md
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cat > QUALITY_AND_TESTING.md << 'EOFQT'
# Quality Assurance & Testing Documentation

**Last Updated**: 2025-10-28  
**Version**: 0.7.6

This document consolidates all quality assurance, auditing, and testing documentation.

---

## Table of Contents

1. [Overview](#overview)
2. [Quality Audit Report](#quality-audit-report)
3. [Quality Audit Findings](#quality-audit-findings)
4. [Quality Fixes Complete](#quality-fixes-complete)
5. [Frontend Manual Testing](#frontend-manual-testing)

---

EOFQT

echo -e "\n## Quality Audit Report\n" >> QUALITY_AND_TESTING.md
tail -n +3 QUALITY_AUDIT_REPORT.md >> QUALITY_AND_TESTING.md

echo -e "\n---\n\n## Quality Audit Findings\n" >> QUALITY_AND_TESTING.md
tail -n +3 QUALITY_AUDIT_FINDINGS.md >> QUALITY_AND_TESTING.md

echo -e "\n---\n\n## Quality Fixes Complete\n" >> QUALITY_AND_TESTING.md
tail -n +3 QUALITY_FIXES_COMPLETE.md >> QUALITY_AND_TESTING.md

echo -e "\n---\n\n## Frontend Manual Testing\n" >> QUALITY_AND_TESTING.md
tail -n +3 test_frontend_manual.md >> QUALITY_AND_TESTING.md

echo "✓ Created QUALITY_AND_TESTING.md"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. FEATURES.md
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cat > FEATURES.md << 'EOFFE'
# Feature Documentation

**Last Updated**: 2025-10-28  
**Version**: 0.7.6

This document consolidates all feature-specific documentation for ShadowRealms AI.

---

## Table of Contents

1. [Overview](#overview)
2. [Gothic Horror Theme](#gothic-horror-theme)
3. [Invite Code System](#invite-code-system)

---

EOFFE

echo -e "\n## Gothic Horror Theme\n" >> FEATURES.md
tail -n +3 GOTHIC_THEME.md >> FEATURES.md

echo -e "\n---\n\n## Invite Code System\n" >> FEATURES.md
tail -n +3 INVITES_README.md >> FEATURES.md

echo "✓ Created FEATURES.md"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. BUG_FIXES_AND_AUDITS.md
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cat > BUG_FIXES_AND_AUDITS.md << 'EOFBUG'
# Bug Fixes & Technical Audits

**Last Updated**: 2025-10-28  
**Version**: 0.7.6

This document consolidates bug fix documentation and technical audit reports.

---

## Table of Contents

1. [Overview](#overview)
2. [Location Bug Fix](#location-bug-fix)
3. [Message Persistence Feature](#message-persistence-feature)
4. [API Audit Report](#api-audit-report)
5. [API Audit Summary](#api-audit-summary)

---

EOFBUG

echo -e "\n## Location Bug Fix\n" >> BUG_FIXES_AND_AUDITS.md
tail -n +3 LOCATION_BUG_FIX.md >> BUG_FIXES_AND_AUDITS.md

echo -e "\n---\n\n## Message Persistence Feature\n" >> BUG_FIXES_AND_AUDITS.md
tail -n +3 MESSAGE_PERSISTENCE_FEATURE.md >> BUG_FIXES_AND_AUDITS.md

echo -e "\n---\n\n## API Audit Report\n" >> BUG_FIXES_AND_AUDITS.md
tail -n +3 API_AUDIT_REPORT.md >> BUG_FIXES_AND_AUDITS.md

echo -e "\n---\n\n## API Audit Summary\n" >> BUG_FIXES_AND_AUDITS.md
echo -e "\`\`\`" >> BUG_FIXES_AND_AUDITS.md
cat API_AUDIT_SUMMARY.txt >> BUG_FIXES_AND_AUDITS.md
echo -e "\`\`\`" >> BUG_FIXES_AND_AUDITS.md

echo "✓ Created BUG_FIXES_AND_AUDITS.md"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. PLANNING.md
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cat > PLANNING.md << 'EOFPLAN'
# Planning & Phase Documentation

**Last Updated**: 2025-10-28  
**Version**: 0.7.6

This document consolidates planning documentation and phase summaries.

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 3A Next Steps](#phase-3a-next-steps)
3. [Phase 3B Summary](#phase-3b-summary)

---

EOFPLAN

echo -e "\n## Phase 3A Next Steps\n" >> PLANNING.md
tail -n +3 PHASE_3A_NEXT.md >> PLANNING.md

echo -e "\n---\n\n## Phase 3B Summary\n" >> PLANNING.md
tail -n +3 PHASE3B_SUMMARY.md >> PLANNING.md

echo "✓ Created PLANNING.md"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Consolidation Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Created 5 consolidated files:"
echo "  1. AI_SYSTEMS.md"
echo "  2. QUALITY_AND_TESTING.md"
echo "  3. FEATURES.md"
echo "  4. BUG_FIXES_AND_AUDITS.md"
echo "  5. PLANNING.md"
echo ""

