#!/usr/bin/env python3
"""
Test data pipelines: validate LegiScan API and state education sources.
Maps external data formats to internal schema.
"""

import requests
import json
from typing import Dict, List, Any
import time

# Test configuration
LEGISCAN_BASE = "https://api.legiscan.com/v1"
KNOWN_BILLS = {
    "CA": {"query": "AB 1159", "keywords": ["artificial intelligence", "student data"]},
    "HI": {"query": "HB 1887", "keywords": ["artificial intelligence", "graduation"]},
    "OK": {"query": "SB 1734", "keywords": ["artificial intelligence", "responsible technology"]},
    "MA": {"query": "S.429", "keywords": ["artificial intelligence", "education"]},
    "TX": {"query": "HB 149", "keywords": ["artificial intelligence"]},
    "AR": {"query": "artificial intelligence", "keywords": ["education", "AI"]},
    "LA": {"query": "artificial intelligence", "keywords": ["literacy", "K-12"]},
}

STATE_ED_GUIDANCE_URLS = {
    "CA": "https://www.cde.ca.gov/ci/pl/aiincalifornia.asp",
    "HI": "https://hawaiipublicschools.org/student-programs/artificial-intelligence/",
    "MA": "https://www.doe.mass.edu/edtech/ai/default.html",
    "RI": "https://ride.ri.gov/sites/g/files/xkgbur806/files/2025-12/RIDE%20AI%20Guidance%208.15.25.pdf",
    "AK": "https://education.alaska.gov/artificial-intelligence/",
}


def test_legiscan_search(state: str, query: str) -> Dict[str, Any]:
    """Test LegiScan bill search API."""
    print(f"\n🔍 LegiScan Search: {state} - {query}")
    print("-" * 60)

    try:
        url = f"{LEGISCAN_BASE}/bills/search"
        params = {
            "state": state,
            "query": query,
            "year": "2024,2025,2026"
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK":
            bills = data.get("bills", [])
            print(f"✅ Found {len(bills)} bills")

            if bills:
                # Show first bill structure
                bill = bills[0]
                print(f"\n📋 Sample bill structure:")
                print(f"  bill_id: {bill.get('bill_id')}")
                print(f"  bill_number: {bill.get('bill_number')}")
                print(f"  title: {bill.get('title')}")
                print(f"  status: {bill.get('status')}")
                print(f"  status_date: {bill.get('status_date')}")
                print(f"  url: {bill.get('url')}")

                return {
                    "status": "success",
                    "count": len(bills),
                    "sample": bill
                }
        else:
            print(f"❌ API returned: {data.get('status')}")
            return {"status": "failed", "error": data}

    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return {"status": "error", "error": str(e)}


def test_state_guidance_urls() -> Dict[str, Any]:
    """Test state education guidance URL accessibility."""
    print(f"\n🌐 State Education Guidance URLs")
    print("-" * 60)

    results = {}
    for state, url in STATE_ED_GUIDANCE_URLS.items():
        print(f"\n{state}: {url}")
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                print(f"  ✅ Accessible (status: {response.status_code})")
                results[state] = "accessible"
            else:
                print(f"  ⚠️  Status: {response.status_code}")
                results[state] = f"status_{response.status_code}"
        except requests.RequestException as e:
            print(f"  ❌ Error: {type(e).__name__}")
            results[state] = f"error_{type(e).__name__}"

        time.sleep(0.5)  # Rate limiting

    return results


def map_legiscan_to_schema(legiscan_bill: Dict) -> Dict[str, Any]:
    """
    Map LegiScan bill data to internal schema.
    Shows what fields are available and what gaps exist.
    """
    mapping = {
        "state_code": None,  # Must extract from legiscan_bill or context
        "state_name": None,  # Must provide separately
        "bill_number": legiscan_bill.get("bill_number"),
        "bill_title": legiscan_bill.get("title"),
        "bill_url": legiscan_bill.get("url"),
        "bill_status": legiscan_bill.get("status"),
        "bill_status_details": None,  # LegiScan doesn't have detailed status notes
        # LegiScan doesn't have these fields:
        "guidance_exists": None,  # Requires separate Ed Dept lookup
        "guidance_type": None,
        "guidance_issued_by": None,
        "guidance_issued_date": None,
        "guidance_core_principles": None,
        "guidance_url": None,
        # Need to fetch separately:
        "bill_text_url": legiscan_bill.get("url"),  # May need separate fetch
        "bill_sponsors": None,  # Available in detailed bill endpoint
        # Default values from schema:
        "regulatory_stance": None,  # Requires manual classification
        "maturity": None,  # Requires manual assessment
    }

    return mapping


def generate_normalization_spec() -> str:
    """Generate data normalization specification."""
    spec = """
# Data Normalization Specification

## LegiScan API Field Mapping

### Available from LegiScan (bills/search):
- bill_id → internal bill reference
- bill_number → bill_number
- title → bill_title
- status → bill_status
- status_date → (timestamp, not in our schema)
- url → bill_url

### Available from LegiScan (bill detail endpoint):
- sponsors[] → Need to flatten/summarize
- bill_text → May need separate fetch or store URL

### NOT available from LegiScan (requires manual/external lookup):
- regulatory_stance (PROHIBIT, RESTRICT, REGULATE, SUPPORT, MANDATE, ABSENT)
- maturity (NASCENT, IN_PROGRESS, ACTIVE, MATURE)
- guidance_exists
- guidance_type
- guidance_issued_by
- guidance_issued_date
- guidance_core_principles
- guidance_url
- bill_status_details (detailed context)

## State Education Dept Guidance Field Mapping

### Expected format from web pages:
- Title/heading → guidance document name
- Date → guidance_issued_date
- PDF/text content → requires parsing for:
  - Core principles
  - Regulatory stance indicators
  - Key requirements

### Extraction requirements:
- PDF parsing (pdfplumber) for guidance documents
- HTML parsing (BeautifulSoup) for web pages
- Manual review required to extract structured data

## Normalization Strategy

### Phase 1: LegiScan → Database
1. Search LegiScan for known bills (monthly)
2. Fetch bill details (sponsors, status history)
3. Update bill_number, bill_title, bill_status, bill_url
4. Keep manual fields (stance, maturity) from previous research
5. Flag new bills for manual review

### Phase 2: State Ed Guidance → Database
1. Fetch guidance documents (quarterly)
2. Extract text/HTML
3. Parse for core principles and requirements
4. Manual review queue: classify regulatory_stance + maturity
5. Update guidance_* fields

### Phase 3: Data Quality
1. Audit trail via legislation_updates table
2. Before→after values for each field change
3. changed_by field tracks which pipeline made changes
4. Manual review queue prevents bad data from going live

## Database Schema Alignment

### Required updates for syncing:
1. Add source_url field (track where data came from)
2. Add last_sync timestamp (know when data was last pulled)
3. Add data_source field (LEGISCAN, STATE_ED_DEPT, MANUAL, etc.)
4. Maintain legislation_updates for full audit trail

### Fields that stay manual (for now):
- regulatory_stance (requires expert classification)
- maturity (requires timeline analysis)
- guidance_core_principles (requires document reading)
- teacher_certification_required (varies by bill text)
- graduation_requirement (requires bill analysis)

## Classification Rules (Manual Review)

### Regulatory Stance:
- PROHIBIT: Bill/guidance explicitly forbids AI use in specific contexts
- RESTRICT: Bill/guidance limits AI use (requires conditions, oversight)
- REGULATE: Bill/guidance requires policies/compliance but doesn't prohibit
- SUPPORT: Bill/guidance encourages AI adoption (positive framing)
- MANDATE: Bill/guidance requires AI use (curriculum, training, etc.)
- ABSENT: No bill or guidance exists

### Maturity:
- NASCENT: Proposed bill (not yet voted) or initial guidance
- IN_PROGRESS: Passed bill but not yet implemented, or active pilot
- ACTIVE: Bill enforced, guidance widely adopted
- MATURE: 2+ years of implementation, established practices

## Implementation Checklist

- [ ] LegiScan API connectivity verified
- [ ] State Ed dept URLs verified
- [ ] PDF parsing pipeline created
- [ ] HTML parsing pipeline created
- [ ] Manual review queue database table created
- [ ] Test sync for 3-5 sample states
- [ ] Audit trail validates all changes
- [ ] No data pushed live without manual approval
"""
    return spec


# Main execution
if __name__ == "__main__":
    print("\n" + "="*70)
    print("K-12 AI LEGISLATIVE MAP: DATA PIPELINE TEST")
    print("="*70)

    # Test LegiScan API
    print("\n📡 TESTING LEGISCAN API")
    print("="*70)

    legiscan_results = {}
    for state, config in list(KNOWN_BILLS.items())[:3]:  # Test 3 states
        result = test_legiscan_search(state, config["query"])
        legiscan_results[state] = result
        time.sleep(1)  # Rate limit

    # Test state guidance URLs
    print("\n\n🎓 TESTING STATE EDUCATION GUIDANCE URLS")
    print("="*70)
    guidance_results = test_state_guidance_urls()

    # Show mapping example
    print("\n\n📊 DATA MAPPING EXAMPLE")
    print("="*70)
    if legiscan_results and any(r.get("sample") for r in legiscan_results.values()):
        sample_bill = next(r["sample"] for r in legiscan_results.values() if r.get("sample"))
        mapping = map_legiscan_to_schema(sample_bill)
        print("\nLegiScan → Internal Schema Mapping:")
        for key, value in mapping.items():
            status = "✅" if value else "❌"
            print(f"  {status} {key}: {value}")

    # Generate normalization spec
    print("\n\n📋 GENERATING NORMALIZATION SPECIFICATION")
    print("="*70)
    spec = generate_normalization_spec()
    print(spec)

    # Summary
    print("\n\n📈 SUMMARY")
    print("="*70)
    print(f"LegiScan Tests: {len(legiscan_results)} states tested")
    print(f"  Successful: {sum(1 for r in legiscan_results.values() if r.get('status') == 'success')}")
    print(f"  Failed: {sum(1 for r in legiscan_results.values() if r.get('status') != 'success')}")

    print(f"\nGuidance URLs: {len(guidance_results)} states tested")
    print(f"  Accessible: {sum(1 for r in guidance_results.values() if 'accessible' in str(r))}")
    print(f"  Issues: {sum(1 for r in guidance_results.values() if 'accessible' not in str(r))}")

    print("\n✅ Test complete. See DATA_NORMALIZATION_SPEC.md for detailed mapping rules.")
