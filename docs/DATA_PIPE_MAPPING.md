# Data Pipe Mapping: Sources & Access Methods

Strategic mapping of where to pull K-12 AI legislation data for each state/territory and how to access it.

---

## Overview

**Total Jurisdictions**: 53 (50 states + 3 territories)

**Access Methods**:
1. **LegiScan API** — Universal bill tracking (covers all 50 states)
2. **State Education Dept APIs** — Direct guidance + policy documents
3. **State Legislature APIs** — Bill status and metadata
4. **Web Scraping** — State-specific government sites
5. **Manual Collection** — Guidance PDFs and task force reports
6. **Federal Guidance** — For territories and states with absent policies

---

## Primary Data Source by State

### Group A: LegiScan + State Education API
States with formal legislation + comprehensive state education guidance. **Recommended**: dual-source for legislation + guidance.

| State | Bills | Education Dept | LegiScan | Ed API | Notes |
|-------|-------|---|---|---|---|
| AK | No | ✅ guidance | ✅ API | ✅ | Framework-driven; state guidance primary |
| CA | AB 1159 | ✅ guidance | ✅ API | ❓ | Most mature state; bill tracking + guidance |
| HI | HB 1887 | ✅ guidance | ✅ API | ❓ | Mandate-based; strong state ownership |
| MA | S.429 | ✅ guidance | ✅ API | ❓ | Multi-year strategy; state-led coordination |
| OK | SB 1734 | ✅ guidance | ✅ API | ❓ | Passed; district compliance required |
| RI | No | ✅ guidance | ✅ API | ✅ | Guidance-first approach |
| TX | HB 149 | No K12 | ✅ API | ❌ | No formal K-12 guidance; district-driven |

**Data Flow**: LegiScan → Bill Status + Metadata | State Ed Site → Guidance PDF + Policy Documents

---

### Group B: LegiScan + Manual Collection
States with early-stage or proposal-stage bills; guidance from task forces or pending.

| State | Bills | Data Source | LegiScan | Method | Notes |
|-------|-------|---|---|---|---|
| AR | No | Task Force Report | ✅ API | Web Scraping | 2025 task force report + guidance; no formal bill |
| CO | Proposed | State Ed Roadmap | ✅ API | Manual | Colorado Education Initiative roadmap; district-driven |
| ID | SB 1227 | State Ed Site | ✅ API | Web Scraping | Framework exists; may have guidance document |
| LA | Proposed | State Ed Guidance | ✅ API | Web Scraping | LDOE guidance exists; bill pending |
| MD | SB 720 | State Ed Site | ✅ API | Web Scraping | Requires state guidance development; AI Collaborative |
| NJ | A 4352 / S 2862 | State Ed Site | ✅ API | Web Scraping | Curriculum requirements; state implementation pending |
| NM | HB 330 | State Ed Guidance | ✅ API | Web Scraping | Guidance exists; bill + oversight body recommended |
| OH | No | Model Policy | ✅ API | Web Scraping | ODE model policy; mandatory adoption by July 2026 |

**Data Flow**: LegiScan → Bill Status | State Ed Site → Guidance Document (PDF/web) | Manual Review

---

### Group C: LegiScan Only
States where K-12 AI legislation is absent or nascent; no formal state education guidance yet.

| State | Data Source | LegiScan | Status | Notes |
|-------|---|---|---|---|
| AL | Legislature | ✅ API | NASCENT | HB 329 exists; needs guidance tracking |
| AZ | Legislature | ✅ API | NASCENT | HB 4040 exists; needs status verification |
| CT | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| DE | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| FL | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| GA | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| IL | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| IN | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| IA | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| KS | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| KY | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| ME | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| MI | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| MN | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| MS | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| MO | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| MT | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| NE | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| NV | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| NH | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| NY | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| NC | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| ND | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| OR | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| PA | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| SC | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| SD | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| TN | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| UT | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| VT | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| VA | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| WA | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| WV | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| WI | Legislature | ✅ API | NASCENT | No identified bill; needs research |
| WY | Legislature | ✅ API | NASCENT | No identified bill; needs research |

**Data Flow**: LegiScan API only (polling for new/updated bills)

---

### Group D: Federal Guidance + Direct Outreach
Territories and special cases with no local K-12 AI legislation.

| Territory | Data Source | Method | Status | Notes |
|-----------|---|---|---|---|
| PR | Federal + Dept Guidance | Manual Collection | RESEARCHED | Has 9-core framework; align with federal guidance |
| GU | Federal Guidance | Direct Outreach | NASCENT | No public guidance; contact Guam Dept of Ed |
| VI | Federal Guidance | Direct Outreach | NASCENT | No public guidance; contact VIDE |

**Data Flow**: LegiScan (if legislation introduced) | Federal guidance documents | Direct API/email outreach to territorial education depts

---

## LegiScan API Strategy

### Why LegiScan?
- **Covers all 50 states** with unified bill tracking API
- **Real-time updates** on bill status, sponsors, text
- **No authentication needed** for basic endpoints
- **Structured data** (JSON) for easy integration

### LegiScan API Endpoints

**Search bills by keyword**:
```
https://api.legiscan.com/v1/bills/search
?state=CA&query=artificial+intelligence&year=2024,2025,2026
```

**Get bill details**:
```
https://api.legiscan.com/v1/bill
?bill_id=123456
```

**Get recent bill activity**:
```
https://api.legiscan.com/v1/bills
?state=CA&year=2026
```

**Full API docs**: https://legiscan.com/api

### Polling Strategy
- Query each state monthly for new bills containing: "artificial intelligence", "AI", "machine learning", "large language model"
- Update bill status for known bills weekly
- Capture bill text, sponsors, status changes

---

## State Education Department APIs

### States with Documented Guidance
- **AK**: https://education.alaska.gov/artificial-intelligence/
- **CA**: https://www.cde.ca.gov/ci/pl/aiincalifornia.asp
- **HI**: https://hawaiipublicschools.org/student-programs/artificial-intelligence/
- **MA**: https://www.doe.mass.edu/edtech/ai/default.html
- **RI**: https://ride.ri.gov/sites/g/files/xkgbur806/files/2025-12/RIDE%20AI%20Guidance%208.15.25.pdf

### States with Downloadable Guidance Documents
- **AR**: Task force report (2025) — requires web scraping or manual collection
- **CO**: Colorado Education Initiative roadmap (2024) — requires manual collection
- **LA**: LDOE AI Guidance PDF — requires web scraping from doe.louisiana.gov
- **NM**: Public Education Dept guidance (2025) — requires web scraping
- **OH**: ODE Model Policy (release date: end of 2025) — requires web scraping from education.ohio.gov
- **PR**: Department of Education framework — requires contact for structured format

### Data Collection Method
1. **Manual Web Scraping**: Download guidance PDFs from state education dept URLs
2. **Direct API Calls** (where available): Query state education tech APIs
3. **Direct Contact**: Email education dept for structured data export (PR, GU, VI)

---

## Web Scraping & Parsing Strategy

### States Requiring Web Scraping

| State | URL | Content Type | Format | Extraction |
|-------|-----|---|---|---|
| AR | arkansased.gov | Task force report | PDF + HTML | Text extraction + parsing |
| CO | coloradoedinitiative.org | Roadmap document | PDF | Text extraction |
| LA | doe.louisiana.gov | AI Guidance PDF | PDF | Text extraction + OCR if needed |
| NM | env.nm.gov/ped | Guidance documents | PDF + HTML | Text extraction |
| OH | education.ohio.gov | Model policy | PDF + HTML | Text extraction |

### Web Scraping Tools
- **BeautifulSoup** (Python) — HTML parsing
- **Selenium** (Python) — JavaScript-rendered content
- **pdfplumber** (Python) — PDF text extraction
- **PyPDF2** (Python) — PDF parsing

---

## Data Mapping Summary

### Access Method Tally
- **LegiScan API**: All 50 states + will check for PR, GU, VI
- **State Education APIs**: 7 states (AK, CA, HI, MA, RI, + others developing)
- **Web Scraping**: 5+ states (AR, CO, LA, NM, OH)
- **Manual Collection**: 3 territories (PR, GU, VI)

### Implementation Priority

**Phase 1 (Immediate)**:
1. LegiScan API polling for all 50 states (monthly bill search + weekly status updates)
2. Manual collection of guidance documents from Group A states (CA, HI, MA, RI, AK)

**Phase 2 (Next)**:
1. State Education API integration for states offering machine-readable guidance
2. Web scraping for Group B states (AR, CO, LA, NM, OH)

**Phase 3**:
1. Outreach to Group C states (if legislation introduced)
2. Direct contact with PR, GU, VI education departments

---

## Next Steps

1. **Validate LegiScan Coverage**: Confirm LegiScan has K-12 AI bills for all states researched
2. **Test API Connections**: 
   - LegiScan bill search for known bills (CA: AB 1159, HI: HB 1887, OK: SB 1734)
   - State Education APIs (CA, MA, RI links in pull test)
3. **Set Up Web Scraping**:
   - Create BeautifulSoup parsers for state education department sites
   - Test PDF extraction from guidance documents
4. **Build Sync Pipeline** (Phase 4):
   - Scheduled LegiScan polling (daily/weekly)
   - Manual review queue before pushing to database
   - Audit trail for all data changes (via legislation_updates table)
5. **Territory Outreach**:
   - Send inquiry emails to PR, GU, VI education departments
   - Request guidance documents and clarification on AI policy stance
