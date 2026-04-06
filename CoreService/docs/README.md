# Magellon Core Service - Documentation

**Project documentation hub**

---

## 📁 Documentation Structure

```
docs/
├── README.md (this file)
├── magellon_schemal.sql (database schema)
├── architecture/
│   ├── README.md (architecture docs index)
│   ├── WORKFLOW_ARCHITECTURE.md (Temporal + NATS workflow system)
│   └── EVENT_ARCHITECTURE.md (event system & CloudEvents evaluation)
└── security/
    ├── README.md (security docs index)
    ├── SECURITY_ARCHITECTURE.md (complete security guide)
    └── DEVELOPER_GUIDE.md (developer quick reference)
```

---

## 📚 Available Documentation

### Architecture Documentation

**Location:** `architecture/`

**Start Here:** [architecture/README.md](architecture/README.md)

**Documents:**
- **[WORKFLOW_ARCHITECTURE.md](architecture/WORKFLOW_ARCHITECTURE.md)** - Distributed workflow system
- **[EVENT_ARCHITECTURE.md](architecture/EVENT_ARCHITECTURE.md)** - Event system design

**Coverage:**
- ✅ Temporal workflow orchestration
- ✅ NATS event broadcasting
- ✅ Distributed workers
- ✅ Job management
- ✅ Quick start guide
- ✅ Deployment guide

### Security Documentation

**Location:** `security/`

**Start Here:** [security/README.md](security/README.md)

**Documents:**
- **[SECURITY_ARCHITECTURE.md](security/SECURITY_ARCHITECTURE.md)** - Complete security architecture
- **[DEVELOPER_GUIDE.md](security/DEVELOPER_GUIDE.md)** - Developer quick reference

**Coverage:**
- ✅ JWT Authentication
- ✅ Casbin Authorization
- ✅ Row-Level Security (RLS)
- ✅ Database Security
- ✅ API Security
- ✅ Deployment Guide
- ✅ Troubleshooting
- ✅ Code Examples
- ✅ Testing Guide

### Database Schema

**File:** `magellon_schemal.sql`

Complete MySQL database schema including:
- Application tables (Image, Msession, Camera, etc.)
- Security tables (sys_sec_*)
- Casbin tables (casbin_rule)

---

## 🚀 Quick Links

### For Developers

- **Quick Start:** [security/DEVELOPER_GUIDE.md § Quick Start](security/DEVELOPER_GUIDE.md#quick-start-30-seconds)
- **Code Examples:** [security/DEVELOPER_GUIDE.md § Code Examples](security/DEVELOPER_GUIDE.md#code-examples)
- **Testing:** [security/DEVELOPER_GUIDE.md § Testing Guide](security/DEVELOPER_GUIDE.md#testing-guide)

### For Architects

- **Architecture Overview:** [security/SECURITY_ARCHITECTURE.md § System Architecture](security/SECURITY_ARCHITECTURE.md#system-architecture)
- **Security Layers:** [security/SECURITY_ARCHITECTURE.md § Security Layers](security/SECURITY_ARCHITECTURE.md#security-layers)
- **Audit Results:** [security/SECURITY_ARCHITECTURE.md § Security Audit Results](security/SECURITY_ARCHITECTURE.md#security-audit-results)

### For Operations

- **Deployment:** [security/SECURITY_ARCHITECTURE.md § Deployment Guide](security/SECURITY_ARCHITECTURE.md#deployment-guide)
- **Troubleshooting:** [security/SECURITY_ARCHITECTURE.md § Troubleshooting](security/SECURITY_ARCHITECTURE.md#troubleshooting)

---

## 📖 Documentation Standards

### Recently Consolidated (2025-12-09)

We consolidated all documentation into organized folders:

**Deleted from root:**
- 11 workflow/architecture markdown files → `docs/architecture/`
- 3 security markdown files → `docs/security/`
- 2 personal notes files

**Current Structure:**
- `docs/architecture/` - 2 comprehensive architecture documents
- `docs/security/` - 2 comprehensive security documents
- Root has only `CLAUDE.md` and `Readme.md`

### Document Status

| Document | Version | Last Updated | Status |
|----------|---------|--------------|--------|
| WORKFLOW_ARCHITECTURE.md | 1.0 | 2025-12-09 | ✅ Current |
| EVENT_ARCHITECTURE.md | 1.0 | 2025-12-09 | ✅ Current |
| SECURITY_ARCHITECTURE.md | 3.1 | 2025-12-09 | ✅ Current |
| DEVELOPER_GUIDE.md | 3.0 | 2025-11-18 | ✅ Current |
| Database Schema | - | 2024-10-21 | 🟡 Stable |

---

## 🛠️ Contributing to Documentation

### Guidelines

1. **Update existing docs** rather than creating new files
2. **Keep information current** - update dates and version numbers
3. **Follow existing format** - maintain consistency
4. **Test code examples** - ensure they work
5. **Add to changelog** - document significant changes

### Where to Update

- **Workflow/architecture changes** → `architecture/WORKFLOW_ARCHITECTURE.md`
- **Event system changes** → `architecture/EVENT_ARCHITECTURE.md`
- **Security changes** → `security/SECURITY_ARCHITECTURE.md`
- **Developer examples** → `security/DEVELOPER_GUIDE.md`
- **Database schema** → `magellon_schemal.sql`

---

## 📞 Support

### Security Issues

Report to security team immediately

### Documentation Issues

- Outdated information? → Update the relevant document
- Missing information? → Add to existing document
- Unclear explanation? → Improve existing section

### Code Questions

See inline documentation in:
- `dependencies/auth.py` - Authentication
- `dependencies/permissions.py` - Authorization
- `core/sqlalchemy_row_level_security.py` - RLS
- `services/casbin_service.py` - Casbin

---

## 🔗 Related Documentation

- **Project README:** `../Readme.md`
- **Project Instructions (for Claude Code):** `../CLAUDE.md`
- **Configuration Examples:** `../configs/`
- **Test Suite:** `../tests/`

---

**Last Updated:** 2025-12-09
**Maintained By:** Magellon Development Team

---

**GET STARTED:**
- New to the project? → [security/DEVELOPER_GUIDE.md](security/DEVELOPER_GUIDE.md)
- Need workflow info? → [architecture/WORKFLOW_ARCHITECTURE.md](architecture/WORKFLOW_ARCHITECTURE.md)
- Need security info? → [security/SECURITY_ARCHITECTURE.md](security/SECURITY_ARCHITECTURE.md)
- Have questions? → [security/DEVELOPER_GUIDE.md § FAQ](security/DEVELOPER_GUIDE.md#faq)
