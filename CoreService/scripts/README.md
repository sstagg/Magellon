# Magellon Scripts

Utility scripts for managing the Magellon Core Service.

## Security Scripts

### `setup_security_permissions.py`

**Purpose:** Set up and sync security permissions after initial database setup.

**When to run:**
- After initial database creation
- If users get "permission denied" errors
- After restoring database from backup
- If casbin_rule table is empty

**Usage:**
```bash
cd C:\projects\Magellon\CoreService
python scripts/setup_security_permissions.py
```

**What it does:**
1. Creates Administrator and Users roles (if not exist)
2. Creates type permissions for msession and image
3. Syncs all permissions to Casbin (casbin_rule table)
4. Verifies the setup with enforcement tests

**Expected output:**
```
[OK] Security permissions setup completed successfully!

The 'super' user should now be able to:
  - Read, write, and create sessions (msession)
  - Read, write, and create images
  - Access the application
```

---

### `sync_policies_to_casbin.py`

**Purpose:** Sync existing database permissions to Casbin.

**When to run:**
- When you've modified permissions in sys_sec_* tables manually
- After adding new type permissions
- If Casbin is out of sync with database

**Usage:**
```bash
python scripts/sync_policies_to_casbin.py
```

---

## Troubleshooting

### "Permission denied" after login

Run the setup script:
```bash
python scripts/setup_security_permissions.py
```

### Script fails with database error

1. Make sure MySQL is running
2. Check database connection in `configs/app_settings_dev.yaml`
3. Ensure no other connections are locking the database

### Casbin policies not persisting

The script automatically persists policies. If issues persist:
```bash
# Restart the application to reload Casbin
python -m uvicorn main:app --reload
```

---

**Last Updated:** 2025-12-09
