# PostgreSQL Migration - Decision & Plan

**Date**: 2025-10-28  
**Version**: 0.7.6 → 0.8.0 (post-migration)  
**Status**: 🚧 IN PROGRESS

---

## 📋 Migration Decision Discussion

### User's Concerns About SQLite
- Past experience: SQLite databases failing after 1-2 years
- Performance degradation concerns
- File corruption risks
- Limited concurrency
- Anxiety about production reliability

### User's Requirements

**Current Scale:**
- Me and some friends starting out
- Single campaign at a time initially
- 1 campaign now, scaling to 2+ in near future
- Home desktop (beefed up) - see README for specs

**Future Vision:**
- Potential scaling to larger user base
- Dedicated server with GPU capability
- Node of servers infrastructure
- Multiple concurrent campaigns
- Production-level deployment

**Backup Strategy:**
- Currently: Manual backups via existing script
- Migration: Pre-migration backup essential
- Future: Automated backup pipeline (post-production release)

### Decision: PostgreSQL Migration

**Why PostgreSQL:**
1. ✅ Rock-solid stability and crash recovery
2. ✅ Excellent concurrent write performance (critical for chat)
3. ✅ Battle-tested in production environments
4. ✅ Advanced features: JSON/JSONB, full-text search, triggers
5. ✅ Scales from single instance to distributed systems
6. ✅ Multiple backup strategies
7. ✅ Can utilize full system resources
8. ✅ Industry standard with massive community

**Migration Timing:** NOW
- Minimal data to migrate (Phase 3B early stage)
- Before character system adds complexity
- Clean slate for future development
- Addresses reliability concerns proactively

---

## 🎯 Migration Plan

### Phase 1: Preparation (Pre-Migration)
- [x] Document migration decision
- [ ] Create comprehensive backup script
- [ ] Backup current SQLite database
- [ ] Test backup restoration
- [ ] Document current schema

### Phase 2: PostgreSQL Setup
- [ ] Add PostgreSQL container to docker-compose.yml
- [ ] Configure PostgreSQL credentials in .env
- [ ] Create initialization scripts
- [ ] Test PostgreSQL connectivity

### Phase 3: Schema Migration
- [ ] Generate PostgreSQL schema from SQLite
- [ ] Add PostgreSQL-specific optimizations
  - Indexes on foreign keys
  - Indexes on frequently queried columns
  - JSON fields for flexible data
- [ ] Create migration SQL script
- [ ] Test schema creation

### Phase 4: Data Migration
- [ ] Export data from SQLite
- [ ] Transform data for PostgreSQL
- [ ] Import data to PostgreSQL
- [ ] Verify data integrity
- [ ] Test queries

### Phase 5: Backend Code Updates
- [ ] Update database connection (SQLAlchemy)
- [ ] Update connection pooling
- [ ] Add PostgreSQL-specific optimizations
- [ ] Update health checks
- [ ] Add connection retry logic

### Phase 6: Testing
- [ ] Test all CRUD operations
- [ ] Test authentication flow
- [ ] Test campaign operations
- [ ] Test location operations
- [ ] Test message persistence
- [ ] Test AI integration
- [ ] Test concurrent operations
- [ ] Load testing

### Phase 7: Deployment
- [ ] Stop current services
- [ ] Apply final migration
- [ ] Start with PostgreSQL
- [ ] Monitor for issues
- [ ] Keep SQLite backup for rollback

### Phase 8: Post-Migration
- [ ] Document new backup procedures
- [ ] Set up PostgreSQL monitoring
- [ ] Configure automated vacuuming
- [ ] Optimize queries if needed
- [ ] Update documentation

---

## 📊 Schema Comparison

### Current SQLite Schema

**Tables:**
- users (authentication, roles, ban system)
- campaigns (name, game_system, world_setting)
- locations (campaign locations, OOC rooms)
- messages (chat messages, AI responses)
- characters (player characters) - TODO
- npcs (non-player characters) - TODO
- combat_state (combat tracking) - TODO
- relationships (character relationships) - TODO
- location_connections (location graph) - TODO
- ooc_violations (OOC monitoring)
- location_deletion_log (audit trail)
- moderation_log (admin actions)

### PostgreSQL Enhancements

**Performance Improvements:**
- Connection pooling
- Prepared statements
- Query optimization
- Proper indexing strategy

**Feature Additions:**
- JSONB columns for flexible AI data
- Full-text search for messages
- Triggers for audit logging
- Views for complex queries
- Materialized views for analytics

**Reliability:**
- Transaction isolation
- Foreign key constraints (properly enforced)
- Check constraints
- Not-null constraints where appropriate

---

## 🔐 Security Considerations

**PostgreSQL Credentials:**
- Store in .env (not version controlled)
- Use strong passwords
- Restrict network access
- Use SSL in production

**Access Control:**
- Application user with limited privileges
- No superuser access from app
- Separate backup user
- Read-only user for analytics (future)

---

## 📦 Backup Strategy

### Pre-Migration Backup
```bash
# Full SQLite backup
./scripts/backup-before-postgresql.sh
```

### PostgreSQL Backup Options

**Daily Backups (pg_dump):**
```bash
pg_dump -U shadowrealms shadowrealms_db > backup_$(date +%Y%m%d).sql
```

**Continuous Archiving (WAL):**
- Point-in-time recovery capability
- Minimal data loss (seconds)
- Configure after production release

**Automated Pipeline (Future):**
- Scheduled backups
- Rotation policy
- Off-site storage
- Restoration testing

---

## 🚨 Rollback Plan

**If Migration Fails:**
1. Stop PostgreSQL container
2. Restore SQLite backup
3. Start with SQLite
4. Investigate issues
5. Retry migration

**SQLite Backup Retention:**
- Keep SQLite backup for 30 days post-migration
- Test restoration before deleting
- Document any issues encountered

---

## 📈 Performance Expectations

**Current (SQLite):**
- Single writer limitation
- ~1000 messages: Fast
- ~10000 messages: Noticeable slowdown
- Concurrent writes: Queue/wait

**After (PostgreSQL):**
- Multiple concurrent writers
- ~1M messages: Fast with proper indexes
- ~10M messages: Still performant
- Concurrent writes: No waiting

---

## 🎓 Learning Resources

**PostgreSQL Documentation:**
- https://www.postgresql.org/docs/
- JSON/JSONB: https://www.postgresql.org/docs/current/datatype-json.html
- Full-text search: https://www.postgresql.org/docs/current/textsearch.html
- Performance tuning: https://wiki.postgresql.org/wiki/Performance_Optimization

**SQLAlchemy with PostgreSQL:**
- https://docs.sqlalchemy.org/en/14/dialects/postgresql.html

---

## ✅ Success Criteria

Migration is successful when:
- [x] All data migrated without loss
- [x] All features working as before
- [x] No performance regressions
- [x] Backup/restore tested
- [x] Documentation updated
- [x] Team can use system normally

---

## 📝 Notes

**User Quote:**
> "I have postgreSQL in very high regard generally used it in many projects, and yes it is battle tested rock sold and stable solution in general."

**Migration Timing Rationale:**
- Phase 3B is early stage (v0.7.6)
- Character system not yet implemented
- Minimal production data
- Clean migration window
- Addresses long-term concerns now

**Future Scalability:**
- Dedicated server with GPU (future)
- Node of servers infrastructure (future)
- Multiple concurrent campaigns (near future)
- PostgreSQL supports all these scenarios

---

**Last Updated**: 2025-10-28  
**Migration Status**: Preparing Phase 1  
**Target Completion**: 2025-10-28


