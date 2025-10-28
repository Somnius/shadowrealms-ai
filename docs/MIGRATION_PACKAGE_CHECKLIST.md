# PostgreSQL Migration Package - Pre-Flight Checklist

**Version**: 0.7.6  
**Created**: 2025-10-28  
**Status**: Ready for Execution

---

## ✅ Package Integrity Check

Run this checklist before starting the migration to ensure all files are in place.

### Core Migration Files

- [ ] `POSTGRESQL_MIGRATION_GUIDE.md` exists (8.5K)
- [ ] `POSTGRESQL_ENV_SETUP.md` exists (3.1K)
- [ ] `backend/init_postgresql_schema.sql` exists (21K)
- [ ] `backend/database_postgresql.py` exists (12K)
- [ ] `scripts/migrate_sqlite_to_postgresql.py` exists (12K)
- [ ] `scripts/migrate_sqlite_to_postgresql.py` is executable
- [ ] `scripts/backup-before-postgresql.sh` exists and is executable

### Configuration Files

- [ ] `docker-compose.yml` updated (PostgreSQL service added)
- [ ] `env.template` updated (PostgreSQL variables added)
- [ ] `backend/requirements.txt` updated (psycopg2-binary added)
- [ ] `.gitignore` contains `.env` (verified)

### Documentation

- [ ] `docs/DATABASE_MIGRATION_POSTGRESQL.md` exists (technical details)
- [ ] `README.md` up to date (version 0.7.6)

---

## 🔐 Security Verification

Before proceeding, verify:

- [ ] `.env` file is in `.gitignore`
- [ ] `docker-compose.yml` has NO hardcoded credentials
- [ ] `env.template` has only PLACEHOLDER values
- [ ] You have OpenSSL or pwgen for credential generation

---

## 💾 Backup Verification

- [ ] Previous backup exists in `backups/` directory
- [ ] SQLite database file exists: `data/shadowrealms.db` (or Docker volume)
- [ ] Disk space available for new PostgreSQL data (check `df -h`)

---

## 🐳 Docker Environment

- [ ] Docker Compose installed (version 2.x+)
- [ ] Docker daemon running
- [ ] No conflicting services on ports 5432, 5000, 3000, 8000
- [ ] Sufficient memory for PostgreSQL (~512MB minimum)

---

## 📊 Current System State

Document your current state before migration:

```bash
# Count current users
docker compose exec backend sqlite3 /app/data/shadowrealms.db "SELECT COUNT(*) FROM users;"

# Count current campaigns
docker compose exec backend sqlite3 /app/data/shadowrealms.db "SELECT COUNT(*) FROM campaigns;"

# Count current messages
docker compose exec backend sqlite3 /app/data/shadowrealms.db "SELECT COUNT(*) FROM messages;"

# Count current locations
docker compose exec backend sqlite3 /app/data/shadowrealms.db "SELECT COUNT(*) FROM locations;"
```

**Record these numbers**:
- Users: _______
- Campaigns: _______
- Messages: _______
- Locations: _______

You'll compare these after migration.

---

## 🚦 Ready to Start?

If ALL items above are checked:

✅ **You are ready to begin the migration!**

**Next step**: Open `POSTGRESQL_MIGRATION_GUIDE.md` and start with Step 1.

---

## 🆘 If Something is Missing

If any items are NOT checked:

1. Review the package contents summary (shown after Option B)
2. Check for file existence: `ls -lh <filename>`
3. Verify git status: `git status`
4. If files are missing, regenerate them or contact support

---

## 📝 Notes Section

Use this space for any notes during migration:

```
Credential Username: _________________
Backup Location: _____________________
Migration Start Time: ________________
Migration End Time: __________________
Issues Encountered: __________________
_____________________________________
_____________________________________
```

---

**Good luck!** 🍀

Remember: The SQLite database is NOT modified. You can always rollback.

