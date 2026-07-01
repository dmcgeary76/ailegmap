#!/bin/bash
#
# Seeds PR/GU/VI into state_legislation. LegiScan does not cover US territories
# at all (confirmed 2026-07-01), so these three can never be populated by
# legiscan_sync.py -- they need to be loaded manually, same pattern as the
# original pilot states in load_data.sh.
#
# PR has a real, researched guidance framework (see docs/STATE_DATA_SOURCES.md).
# GU and VI have no K-12-specific policy yet -- they're seeded as explicit
# ABSENT records (with research notes + sources) rather than left with no row
# at all, so clicking them on the map shows *why* nothing's there instead of
# looking like a bug. Re-run outreach to GU/VI education departments (see
# docs/territory_outreach_emails.md) and update these records when they reply.

API_URL="http://localhost:8000/api/states"

echo "📊 Loading territory data (PR/GU/VI)..."
echo ""

if ! curl -s $API_URL > /dev/null 2>&1; then
    echo "❌ Backend not responding at $API_URL"
    echo "Make sure backend is running: ./start.sh"
    exit 1
fi

load_state() {
    local name=$1
    local json=$2

    echo -n "Loading $name... "
    response=$(curl -s -X POST $API_URL -H "Content-Type: application/json" -d "$json" 2>&1)

    if echo "$response" | grep -q "state_code"; then
        echo "✅"
    else
        echo "❌"
        echo "Response: $response"
    fi
}

load_state "Puerto Rico" '{
  "state_code": "PR",
  "state_name": "Puerto Rico",
  "bill_status": "Absent",
  "guidance_exists": true,
  "guidance_type": "ADVISORY",
  "guidance_issued_by": "Puerto Rico Department of Education",
  "guidance_url": "https://de.pr.gov",
  "guidance_core_principles": ["ai_literacy", "digital_citizenship", "privacy_protection", "personalized_learning", "responsible_ai_use"],
  "regulatory_stance": "SUPPORT",
  "maturity": "IN_PROGRESS",
  "unique_context": "Comprehensive guidance framework with 9 core objectives from the Department of Education, not formal legislation. Guidance-driven approach aligned with mainland states; follows US education policy generally.",
  "notes": "Fully researched 2026-06-30 (see docs/STATE_DATA_SOURCES.md). LegiScan does not cover PR, so this record will never be touched by legiscan_sync.py -- update manually if the guidance changes."
}'

load_state "Guam" '{
  "state_code": "GU",
  "state_name": "Guam",
  "bill_status": "Absent",
  "guidance_exists": false,
  "regulatory_stance": "ABSENT",
  "maturity": "NASCENT",
  "unique_context": "No K-12-specific AI policy yet. Guam established an AI Regulatory Task Force (2025) with a University of Guam-led education subcommittee aligning to federal AI priorities (child protection, workforce readiness) -- education is on its radar but not yet codified. GovGuam OTECH separately issued a government-wide AI Use Policy for line agencies (Jan 2025, OTECH-POL2025-001), which is IT/administrative, not education-specific.",
  "sources": [
    "https://islandtimes.org/guam-establishes-artificial-intelligence-regulatory-task-force/",
    "https://www.postguam.com/news/local/early-progress-for-ai-task-force/article_2a7680d4-43a3-472e-8a58-daf4f6d7d0c2.html",
    "https://otech.guam.gov/wp-otech-content/uploads/2025/01/OTECH-POL2025-001-AI-Use-Policy-for-GovGuam-Line-Agencies.pdf"
  ],
  "notes": "Re-researched 2026-07-01 -- see docs/STATE_DATA_SOURCES.md. Direct outreach to Guam Dept of Education still needed for a K-12-specific answer; draft in docs/territory_outreach_emails.md."
}'

load_state "US Virgin Islands" '{
  "state_code": "VI",
  "state_name": "US Virgin Islands",
  "bill_status": "Absent",
  "guidance_exists": false,
  "regulatory_stance": "ABSENT",
  "maturity": "NASCENT",
  "unique_context": "No public K-12 AI legislation or department guidance found. Governor Albert Bryan Jr. has publicly called for a broad education-system overhaul citing AI-driven changes in the future of work, but this is political commentary, not a VIDE policy.",
  "sources": ["http://viconsortium.com/vi-government/virgin-islands-bryan-calls-for-education-overhaul-as-ai-redefines-the-future-of-work"],
  "notes": "Re-researched 2026-07-01, no change from original research -- see docs/STATE_DATA_SOURCES.md. Direct outreach to VIDE still needed; draft in docs/territory_outreach_emails.md."
}'

echo ""
echo "✅ Done loading territory data"
echo "🔄 Refresh http://localhost:5173 to see PR/GU/VI update on the map"
