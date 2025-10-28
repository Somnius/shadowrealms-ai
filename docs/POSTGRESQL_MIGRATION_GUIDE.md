# PostgreSQL Migration - Complete Execution Guide

**Version**: 0.7.6  
**Date**: 2025-10-28  
**Status**: Ready for Execution

---

## 📋 Pre-Flight Checklist

Before starting the migration, ensure:

- [ ] Full backup completed (see `backup-before-postgresql.sh`)
- [ ] PostgreSQL credentials generated (see `POSTGRESQL_ENV_SETUP.md`)
- [ ] `.env` file updated with PostgreSQL variables
- [ ] All containers currently stopped
- [ ] LM-Studio not required during migration
- [ ] You have ~30 minutes for the migration

---

## 🔐 Step 1: Generate Secure Credentials

**DO THIS FIRST!**

```bash
# Generate unique username (12 chars)
echo "sr_$(openssl rand -hex 4 | cut -c1-8)"

# Generate secure password (16 chars)
openssl rand -base64 16 | tr -d "=+/" | sed 's/./&#/5' | cut -c1-16
```

**Save these credentials securely!**

---

## 📝 Step 2: Update `.env` File

Open your `.env` file and add these lines to the **DATABASE CONFIGURATION** section:

```bash
# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
# SQLite (legacy - for rollback only)
DATABASE=/app/data/shadowrealms.db

# PostgreSQL (primary database)
POSTGRES_DB=shadowrealms_db
POSTGRES_USER=YOUR_GENERATED_USERNAME_HERE
POSTGRES_PASSWORD=YOUR_GENERATED_PASSWORD_HERE
DATABASE_TYPE=postgresql
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

**Replace the placeholder values with your generated credentials!**

**Verify** no sensitive data is exposed:
```bash
grep "POSTGRES_" .env | sed 's/=.*/=***/'
```

---

## 🛡️ Step 3: Final Backup

Run the comprehensive backup script:

```bash
./backup-before-postgresql.sh
```

This creates a timestamped backup in `backups/pre-postgresql-YYYYMMDD-HHMMSS/`

**Verify backup completed**:
```bash
ls -lh backups/
```

---

## 🐳 Step 4: Start PostgreSQL Container

```bash
# Stop all containers
docker compose down

# Start only PostgreSQL (to initialize schema)
docker compose up -d postgresql

# Wait for PostgreSQL to be ready (healthcheck)
docker compose ps postgresql
```

**Expected output**: `healthy` status

**Verify schema initialized**:
```bash
docker compose logs postgresql | grep "initialized successfully"
```

---

## 📊 Step 5: Test Migration (Dry Run)

Run migration in dry-run mode to preview:

```bash
docker compose exec backend python /app/migrate_sqlite_to_postgresql.py --dry-run
```

**Review the output carefully!**

Expected:
- ✅ Connections successful
- ✅ Table counts shown
- ✅ No actual data written

---

## 🚀 Step 6: Execute Migration

**This is the point of no return (for this session).**

Run the actual migration:

```bash
docker compose exec backend python /app/migrate_sqlite_to_postgresql.py --verify
```

**What happens**:
1. Connects to both databases
2. Migrates all tables in dependency order
3. Updates PostgreSQL sequences
4. Verifies row counts match
5. Commits transaction

**Expected duration**: 2-5 minutes (depends on data volume)

**Watch for**:
- ✅ All tables migrated
- ✅ Verification passed
- ✅ "Migration completed successfully!"

---

## 🔄 Step 7: Switch to PostgreSQL

Update the backend to use PostgreSQL:

```bash
# Stop all services
docker compose down

# Rebuild backend with PostgreSQL support
docker compose build backend

# Start all services
docker compose up -d
```

**Verify services are healthy**:
```bash
docker compose ps
```

All services should show `healthy` or `running`.

---

## ✅ Step 8: Verification Testing

### Test 1: Database Connection
```bash
docker compose exec backend python -c "from database_postgresql import test_connection; test_connection()"
```

Expected: `✅ PostgreSQL connection successful`

### Test 2: Health Check
```bash
curl http://localhost:5000/health
```

Expected: JSON response with `version: "0.7.6"` and `database_type: "postgresql"`

### Test 3: Login to Frontend
1. Open browser: `http://localhost:3000`
2. Login with existing credentials
3. Verify campaigns are visible

### Test 4: Campaign Access
1. Enter a campaign
2. Verify locations load
3. Send a test message
4. Check message persists on location change

### Test 5: AI Functionality
1. In a location, send a message to AI
2. Verify AI responds correctly
3. Check response quality (should have context)

---

## 📊 Step 9: Data Integrity Check

Run comprehensive checks:

```bash
# Count users
docker compose exec postgresql psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT COUNT(*) FROM users;"

# Count campaigns
docker compose exec postgresql psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT COUNT(*) FROM campaigns;"

# Count messages
docker compose exec postgresql psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT COUNT(*) FROM messages;"

# Count locations
docker compose exec postgresql psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT COUNT(*) FROM locations;"
```

**Compare these counts with your SQLite backup** to ensure all data migrated.

---

## 🔥 Rollback Plan (If Needed)

If something goes wrong, you can rollback to SQLite:

```bash
# Stop all services
docker compose down

# Edit .env - change DATABASE_TYPE back to sqlite
nano .env
# Change: DATABASE_TYPE=sqlite

# Remove PostgreSQL volume (optional, to start fresh)
docker volume rm shadowrealms-ai_postgresql_data

# Restart services
docker compose up -d
```

Your SQLite database is untouched and in the backup.

---

## 🎯 Success Criteria

Migration is successful if:

- [ ] All services start without errors
- [ ] Health endpoint returns PostgreSQL
- [ ] Frontend loads and displays data
- [ ] Login works with existing users
- [ ] Campaigns are visible and accessible
- [ ] Locations load in campaigns
- [ ] Messages persist across location changes
- [ ] AI responses work correctly
- [ ] No error logs in `docker compose logs`

---

## 🐛 Troubleshooting

### Issue: "Connection refused" to PostgreSQL

**Solution**:
```bash
# Check PostgreSQL is running
docker compose ps postgresql

# Check logs
docker compose logs postgresql

# Verify credentials in .env match docker-compose.yml
```

### Issue: "Authentication failed"

**Solution**:
- Double-check `POSTGRES_USER` and `POSTGRES_PASSWORD` in `.env`
- Ensure no extra spaces or quotes
- Restart PostgreSQL: `docker compose restart postgresql`

### Issue: "Table does not exist"

**Solution**:
```bash
# Check if schema was initialized
docker compose logs postgresql | grep "schema"

# If not, remove volume and recreate:
docker compose down
docker volume rm shadowrealms-ai_postgresql_data
docker compose up -d postgresql
```

### Issue: Migration hangs or fails

**Solution**:
1. Check backend logs: `docker compose logs backend`
2. Verify both databases are accessible
3. Check disk space: `df -h`
4. Run dry-run again to identify the failing table

### Issue: Data missing after migration

**Solution**:
1. Check verification output from Step 6
2. Run manual count queries (Step 9)
3. If critical data missing, rollback and investigate
4. Check for foreign key violations in logs

---

## 📞 Post-Migration Tasks

After successful migration:

1. **Monitor performance** for 24-48 hours
2. **Test all features** thoroughly
3. **Update documentation** if needed
4. **Keep SQLite backup** for at least 2 weeks
5. **Take a new PostgreSQL backup**:
   ```bash
   docker compose exec postgresql pg_dump -U $POSTGRES_USER $POSTGRES_DB > backups/postgresql_first_backup_$(date +%Y%m%d).sql
   ```
6. **Update `.gitignore`** to ensure no DB files are committed
7. **Document any issues** encountered

---

## 📚 Reference Files

- `docs/DATABASE_MIGRATION_POSTGRESQL.md` - Technical details and planning
- `POSTGRESQL_ENV_SETUP.md` - Credential generation guide
- `backend/init_postgresql_schema.sql` - Database schema
- `migrate_sqlite_to_postgresql.py` - Migration script
- `backup-before-postgresql.sh` - Backup script

---

## 🚨 Emergency Contacts

If you encounter critical issues:

1. Stop all services immediately: `docker compose down`
2. Check logs: `docker compose logs > migration_error.log`
3. Rollback to SQLite (see Rollback Plan above)
4. Review error logs before attempting again

---

## ✨ Final Notes

**Remember**:
- PostgreSQL is more robust than SQLite
- Performance will improve with proper indexes (already in schema)
- Connection pooling is handled automatically
- Foreign key constraints are always enabled
- Backups are easier with PostgreSQL (`pg_dump`)

**Good luck with the migration!** 🚀

---

**Last Updated**: 2025-10-28  
**Next Review**: After first successful production migration

