#!/bin/bash

API_URL="http://localhost:8000/api/states"

echo "📊 Loading pilot state data..."
echo ""

# Check if backend is running
if ! curl -s $API_URL > /dev/null 2>&1; then
    echo "❌ Backend not responding at $API_URL"
    echo "Make sure backend is running: ./start.sh"
    exit 1
fi

# Function to load a state
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

# Load each state
load_state "California" '{"state_code":"CA","state_name":"California","bill_number":"AB 1159","bill_title":"Student Data Protection Act","bill_status":"In Committee","guidance_exists":true,"guidance_type":"ADVISORY","guidance_issued_by":"California Department of Education","guidance_core_principles":["data_privacy","equity","academic_integrity"],"regulatory_stance":"PROHIBIT","maturity":"ACTIVE","key_focus_areas":["data_privacy","student_protection"]}'

load_state "Texas" '{"state_code":"TX","state_name":"Texas","bill_status":"Absent","guidance_exists":false,"regulatory_stance":"ABSENT","maturity":"NASCENT","districts_have_policies":true,"example_district_actions":["El Paso ISD creating custom policies"],"tools_in_use":["PowerBuddy","MagicSchool AI"]}'

load_state "Massachusetts" '{"state_code":"MA","state_name":"Massachusetts","bill_number":"S.429","bill_title":"Commission to Investigate AI in Education","bill_status":"Proposed","guidance_exists":true,"guidance_type":"ADVISORY","guidance_issued_by":"Massachusetts DESE","guidance_core_principles":["data_privacy","transparency","bias_mitigation","human_oversight","academic_integrity"],"regulatory_stance":"SUPPORT","maturity":"IN_PROGRESS"}'

load_state "Rhode Island" '{"state_code":"RI","state_name":"Rhode Island","bill_status":"Absent","guidance_exists":true,"guidance_type":"ADVISORY","guidance_issued_by":"Rhode Island Department of Education","guidance_core_principles":["academic_integrity","equity","security_privacy"],"regulatory_stance":"SUPPORT","maturity":"IN_PROGRESS"}'

load_state "Alaska" '{"state_code":"AK","state_name":"Alaska","bill_status":"Absent","guidance_exists":true,"guidance_type":"ADVISORY","guidance_issued_by":"Alaska Department of Education","guidance_core_principles":["human_centered_design","fair_access","transparency","oversight","security","ethical_use","cultural_responsiveness"],"regulatory_stance":"SUPPORT","maturity":"IN_PROGRESS","unique_context":"Remote/rural state with cultural responsiveness focus"}'

load_state "Hawaii" '{"state_code":"HI","state_name":"Hawaii","bill_number":"HB 1887","bill_title":"AI Literacy Graduation Requirement","bill_status":"Passed","guidance_exists":true,"guidance_type":"ADVISORY","guidance_issued_by":"Hawaii Department of Education","guidance_core_principles":["human_oversight","data_protection","equity","accountability"],"regulatory_stance":"MANDATE","maturity":"MATURE","graduation_requirement":true,"graduation_year":2028,"teacher_certification_required":true,"unique_context":"Island state with cultural curriculum integration"}'

echo ""
echo "✅ Done loading pilot states"
echo "🔄 Refresh http://localhost:5173 to see the data"
