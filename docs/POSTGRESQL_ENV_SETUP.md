# PostgreSQL Environment Variables Setup

**SECURITY CRITICAL**: These credentials will be stored in your `.env` file (gitignored)

---

## 🔐 Generate Unique Credentials

**IMPORTANT**: Do NOT use the example values below. Generate your own!

### Quick Generation Commands

```bash
# Generate secure username (12 chars)
echo "sr_$(openssl rand -hex 4 | cut -c1-8)"

# Generate secure password (16 chars with special chars)
openssl rand -base64 16 | tr -d "=+/" | sed 's/./&#/5' | cut -c1-16

# Or use pwgen if installed
pwgen -s -y -1 16
```

---

## 📝 Add to Your `.env` File

**Location**: `/home/lef/dev/shadowrealms-ai_dev/shadowrealms-ai/.env`

Add these lines to the **DATABASE CONFIGURATION** section (replace values with YOUR generated ones):

```bash
# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
# SQLite (old - for rollback only)
DATABASE=/app/data/shadowrealms.db

# PostgreSQL (new - primary database)
POSTGRES_DB=shadowrealms_db
POSTGRES_USER=YOUR_GENERATED_USERNAME_HERE
POSTGRES_PASSWORD=YOUR_GENERATED_PASSWORD_HERE
DATABASE_TYPE=postgresql
DATABASE_HOST=localhost
DATABASE_PORT=5432
```

---

## ⚠️ Example Values (DO NOT USE AS-IS)

```bash
# These are EXAMPLES ONLY - Generate your own!
POSTGRES_USER=sr_admin_7xK2
POSTGRES_PASSWORD=Pg#9mR2wL4nQ8vT
```

---

## 🛡️ Security Best Practices

### Password Requirements:
- **Length**: 12-16 characters
- **Uppercase**: A-Z
- **Lowercase**: a-z  
- **Numbers**: 0-9
- **Special**: # $ % & (avoid quotes and backslashes)

### What NOT to do:
- ❌ Don't use default/example passwords
- ❌ Don't use common words or patterns
- ❌ Don't reuse passwords from other systems
- ❌ Don't commit .env to git (already gitignored)
- ❌ Don't share credentials in chat/email

### What TO do:
- ✅ Generate unique credentials for THIS installation
- ✅ Store securely (password manager)
- ✅ Use different credentials for production
- ✅ Keep .env file permissions restricted (600)

---

## 📋 Quick Setup Steps

1. **Generate credentials** using commands above
2. **Open** your `.env` file
3. **Add** PostgreSQL variables to DATABASE CONFIGURATION section
4. **Save** and close
5. **Verify** file permissions: `chmod 600 .env`
6. **Test** connection after migration

---

## 🔍 Verify Your Setup

After adding to `.env`, verify (without showing passwords):

```bash
# Check variables are set (won't show values)
grep "POSTGRES_" .env | sed 's/=.*/=***/'
```

Expected output:
```
POSTGRES_DB=***
POSTGRES_USER=***
POSTGRES_PASSWORD=***
```

---

## 🚨 If Credentials Are Compromised

If you suspect your credentials have been exposed:

1. **Stop containers**: `docker compose down`
2. **Change credentials** in `.env`
3. **Remove old data**: `docker volume rm shadowrealms-ai_postgresql_data`
4. **Restart**: `docker compose up -d`
5. **Re-run migration** with new credentials

---

**Remember**: The `.env` file is already in `.gitignore` - your credentials will NOT be committed to git.

**Last Updated**: 2025-10-28

