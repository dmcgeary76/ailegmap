# Data Normalization Specification

Mapping strategy for external data sources → internal database schema.

---

## Data Source Capabilities vs. Schema Requirements

### What LegiScan Provides (Automated)
```
✅ bill_id
✅ bill_number
✅ bill_title
✅ bill_status (Introduced, In Committee, Passed, etc.)
✅ bill_status_date
✅ bill_url (official legislature link)
✅ bill_sponsors (requires detail endpoint)
✅ bill_text_url (for fetching full text)
```

### What LegiScan CANNOT Provide (Manual Only)
```
❌ regulatory_stance (PROHIBIT, RESTRICT, REGULATE, SUPPORT, MANDATE, ABSENT)
❌ maturity (NASCENT, IN_PROGRESS, ACTIVE, MATURE)
❌ guidance_exists
❌ guidance_type
❌ guidance_issued_by
❌ guidance_issued_date
❌ guidance_core_principles
❌ guidance_url
❌ bill_status_details (contextual notes, like "stuck in committee since 2024")
❌ teacher_certification_required
❌ graduation_requirement
```

### What State Education Depts Provide (Semi-Automated)
```
✅ guidance_issued_by
✅ guidance_issued_date
✅ guidance_url
✅ guidance_core_principles (in document text, requires extraction)
⚠️  guidance_type (requires document classification)
⚠️  regulatory_stance indicators (in text, requires reading)
```

---

## Field-by-Field Normalization Rules

### Legislation Layer

| Field | Source | Type | Example Value | Notes |
|-------|--------|------|---|---|
| bill_number | LegiScan | Automated | "AB 1159" | Clean format from API |
| bill_title | LegiScan | Automated | "Student Data Protection Act" | Direct from API |
| bill_url | LegiScan | Automated | "leginfo.legislature.ca.gov/bill/..." | Official link |
| bill_status | LegiScan | Automated | "In Committee" | Maps to enum: INTRODUCED, COMMITTEE, PASSED, SIGNED, DEAD |
| bill_status_details | Manual | Manual Review | "Stuck in Education Committee since May 2025" | Context from news/tracking |
| bill_status_date | LegiScan | Automated | "2025-05-15" | Last status update timestamp |
| bill_text_url | LegiScan | Automated | LegiScan URL or state link | For full bill text retrieval |

### State Guidance Layer

| Field | Source | Type | Example Value | Notes |
|-------|--------|------|---|---|
| guidance_exists | Manual/Auto | Logic | True/False | True if guidance_url is populated |
| guidance_type | Manual Review | Semi-Auto | "ADVISORY" or "MANDATORY" | Must read guidance document |
| guidance_issued_by | State Website | Semi-Auto | "California Department of Education" | Extract from guidance header |
| guidance_issued_date | State Website | Semi-Auto | "2025-03-15" | From guidance document date |
| guidance_url | State Website | Automated | "cde.ca.gov/ci/pl/aiincalifornia.asp" | Web scrape to find |
| guidance_core_principles | State Website | Manual Review | ["data_privacy", "equity"] | Extract from document text |

### Classification Layer

| Field | Source | Type | Example Value | Notes |
|-------|--------|------|---|---|
| regulatory_stance | Manual Review | Manual | "SUPPORT" | Requires expert reading of bill + guidance |
| maturity | Timeline Analysis | Manual | "ACTIVE" | Based on bill passage date + implementation timeline |

### Implementation Layer

| Field | Source | Type | Example Value | Notes |
|-------|--------|------|---|---|
| teacher_certification_required | Bill Text | Manual | True | Must read bill details |
| graduation_requirement | Bill Text | Manual | True | Must read bill details |
| graduation_year | Bill Text | Manual | 2028 | If applicable |
| advisory_council | Manual | Manual | True | Track if state formed oversight body |
| pilot_programs | Manual | Manual | JSON list | Track pilot programs and funding |

### Data Tracking Layer

| Field | Source | Type | Example Value | Notes |
|-------|--------|------|---|---|
| source_url | Pipeline | Automated | "https://api.legiscan.com/bills/123456" | Track data origin |
| last_sync | Pipeline | Automated | "2026-06-25T14:30:00Z" | When data was last fetched |
| data_source | Pipeline | Automated | "LEGISCAN" or "STATE_ED_DEPT" | Enum: LEGISCAN, STATE_ED_DEPT, MANUAL |
| created_at | Database | Automated | "2026-01-15T10:00:00Z" | First creation timestamp |
| updated_at | Database | Automated | "2026-06-25T14:30:00Z" | Last update timestamp |

---

## Data Flow Diagrams

### Automated: LegiScan Bill Updates
```
LegiScan API (monthly)
    ↓
bill_id, bill_number, bill_title, bill_status, bill_url
    ↓
Database INSERT/UPDATE
    ↓
legislation_updates table (audit trail)
    ↓
✅ Live (no manual review needed)
```

### Semi-Automated: State Education Guidance
```
State Education Website (quarterly scan)
    ↓
Web scraping (BeautifulSoup)
    ↓
guidance_url, guidance_issued_date, guidance_issued_by
    ↓
PDF parsing (pdfplumber) for guidance_core_principles
    ↓
Manual Review Queue
    (assign regulatory_stance, maturity, guidance_type)
    ↓
Database UPDATE with changes
    ↓
legislation_updates table (audit trail)
    ↓
✅ Live (after approval)
```

### Manual: Classification & Context
```
Human Review
    ↓
Assign: regulatory_stance, maturity
Assign: bill_status_details, teacher_certification_required, etc.
    ↓
Database INSERT/UPDATE
    ↓
legislation_updates table (changed_by: "David McGeary", reason: "Manual research")
    ↓
✅ Live (immediate)
```

---

## Normalization Examples

### Example 1: California (Group A - Full Data)

**LegiScan Input**:
```json
{
  "bill_id": 1234567,
  "bill_number": "AB 1159",
  "title": "Student Data Protection Act",
  "status": "In Committee",
  "status_date": "2025-05-20",
  "url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320AB1159"
}
```

**State Ed Site Input**:
```
URL: https://www.cde.ca.gov/ci/pl/aiincalifornia.asp
Date: 2025-03-15
Text: "The California Department of Education provides guidance on AI in schools, emphasizing data privacy, equity, and academic integrity..."
```

**Normalized Output**:
```json
{
  "state_code": "CA",
  "state_name": "California",
  "bill_number": "AB 1159",
  "bill_title": "Student Data Protection Act",
  "bill_status": "In Committee",
  "bill_url": "https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320AB1159",
  "guidance_exists": true,
  "guidance_type": "ADVISORY",
  "guidance_issued_by": "California Department of Education",
  "guidance_issued_date": "2025-03-15",
  "guidance_url": "https://www.cde.ca.gov/ci/pl/aiincalifornia.asp",
  "guidance_core_principles": ["data_privacy", "equity", "academic_integrity"],
  "regulatory_stance": "PROHIBIT",
  "maturity": "ACTIVE",
  "source_url": "https://api.legiscan.com/bill/1234567",
  "data_source": "LEGISCAN + STATE_ED_DEPT",
  "last_sync": "2026-06-25T14:30:00Z"
}
```

### Example 2: Arkansas (Group B - Guidance-Only)

**LegiScan Input**:
```json
{
  "bills": []  // No formal K-12 AI bills found
}
```

**State Task Force Input** (manual):
```
Arkansas AI Task Force Report (2025)
- Guidance on curriculum, professional development, equity, data protection
- Vendor agreement requirements for student data handling
- No formal legislation yet
```

**Normalized Output**:
```json
{
  "state_code": "AR",
  "state_name": "Arkansas",
  "bill_number": null,
  "guidance_exists": true,
  "guidance_type": "ADVISORY",
  "guidance_issued_by": "Arkansas AI Task Force / Department of Education",
  "guidance_issued_date": "2025-06-01",
  "guidance_url": "arkansased.gov/task-force-report",
  "guidance_core_principles": ["curriculum_integration", "professional_development", "equity", "data_protection"],
  "regulatory_stance": "SUPPORT",
  "maturity": "IN_PROGRESS",
  "source_url": "manual_research_batch_1",
  "data_source": "MANUAL + STATE_ED_DEPT",
  "last_sync": "2026-01-15T00:00:00Z"
}
```

### Example 3: Texas (Group C - Minimal/Absent)

**LegiScan Input**:
```json
{
  "bill_id": 9999999,
  "bill_number": "HB 149",
  "title": "Artificial Intelligence",
  "status": "Dead",
  "scope": "General AI governance, NOT K-12 specific"
}
```

**State Ed Input**:
```
No formal K-12 AI guidance. One of 16 states without formal guidance.
Districts implementing independently.
```

**Normalized Output**:
```json
{
  "state_code": "TX",
  "state_name": "Texas",
  "bill_number": "HB 149",
  "bill_title": "Artificial Intelligence (general governance, not K-12)",
  "bill_status": "Dead",
  "bill_status_details": "General AI bill; not K-12 specific. TEA uses AI for STAAR grading.",
  "guidance_exists": false,
  "guidance_type": null,
  "regulatory_stance": "ABSENT",
  "maturity": "NASCENT",
  "districts_have_policies": true,
  "example_district_actions": ["El Paso ISD creating custom policies"],
  "tools_in_use": ["PowerBuddy", "MagicSchool AI"],
  "source_url": "https://api.legiscan.com/bill/9999999",
  "data_source": "LEGISCAN",
  "last_sync": "2026-06-25T14:30:00Z"
}
```

---

## Schema Updates Required

### Add new fields to `state_legislation` table:

```sql
ALTER TABLE state_legislation ADD COLUMN source_url VARCHAR(500);
ALTER TABLE state_legislation ADD COLUMN last_sync TIMESTAMP;
ALTER TABLE state_legislation ADD COLUMN data_source VARCHAR(50);  -- Enum: LEGISCAN, STATE_ED_DEPT, MANUAL
ALTER TABLE state_legislation ADD COLUMN bill_status_date DATE;
ALTER TABLE state_legislation ADD COLUMN bill_text_url VARCHAR(500);
```

### Create manual review queue table:

```sql
CREATE TABLE data_review_queue (
  id SERIAL PRIMARY KEY,
  state_code VARCHAR(2),
  field_name VARCHAR(100),
  current_value TEXT,
  proposed_value TEXT,
  source VARCHAR(100),
  status VARCHAR(20) DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED
  reviewed_by VARCHAR(255),
  review_notes TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  reviewed_at TIMESTAMP
);
```

---

## Classification Guidelines

### Regulatory Stance Classification

Read the bill text + state guidance, then assign:

| Stance | Indicators | Example |
|--------|-----------|---------|
| **PROHIBIT** | "shall not", "prohibited", "banned" for specific uses | "AI cannot be used for student discipline decisions" |
| **RESTRICT** | "must have approval", "requires oversight", "limited to" | "AI use requires parental opt-out right" |
| **REGULATE** | "districts must adopt policies", "require transparency" | "Each district must have AI policy by 2026" |
| **SUPPORT** | "encourage", "promote", "allocate funding" | "State provides $5M to fund AI literacy programs" |
| **MANDATE** | "required", "must include in curriculum", "graduation requirement" | "All students must complete AI literacy course" |
| **ABSENT** | No bill, no guidance, no regulations | "No state-level K-12 AI policy" |

### Maturity Classification

Track timeline + implementation status:

| Maturity | Timeline | Status | Example |
|----------|----------|--------|---------|
| **NASCENT** | < 1 year | Proposed or new guidance | "HB 1887 passed Feb 2025" |
| **IN_PROGRESS** | 1-2 years | Bill passed, implementation underway | "Guidance issued Aug 2025, districts adopting" |
| **ACTIVE** | 2-3 years | Bill enforced, guidance widely adopted | "Model policy adopted by 80% of districts" |
| **MATURE** | 3+ years | Established practices, track record | "AI requirements in place since 2023" |

---

## Implementation Checklist

- [ ] Add source_url, last_sync, data_source, bill_status_date, bill_text_url fields to schema
- [ ] Create data_review_queue table
- [ ] Build LegiScan sync script (monthly bill search)
- [ ] Build state education website scraper
- [ ] Build PDF parser for guidance documents
- [ ] Test on 3-5 sample states
- [ ] Implement manual review workflow
- [ ] Set up audit trail validation
- [ ] Document rollback procedures
- [ ] Train on classification guidelines before going live

---

## Data Quality Guardrails

1. **No auto-update of classification fields** (stance, maturity, core_principles)
2. **All changes logged to legislation_updates** with source + reason
3. **Manual review queue blocks live database updates** for non-trivial changes
4. **Timestamp tracking** (last_sync) shows staleness
5. **Source attribution** (source_url, data_source) enables traceability
