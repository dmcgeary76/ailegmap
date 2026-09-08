> **Out of date (2026-09-02):** this document describes the PostgreSQL / `state_legislation` design. The current setup, data model and endpoints are in the top-level [README](../README.md) and `CHANGELOG.md`; the live API reference is at http://localhost:8000/docs.

# Data Schema: State Legislation Records

## Overview

The `state_legislation` table stores comprehensive AI legislation and policy records for each state, including legislation status, state guidance, implementation details, district activity, and regulatory classification.

## Core Fields

### Identification
- **state_code** (String, 2 chars, unique): US state code (e.g., "CA", "TX")
- **state_name** (String): Full state name (e.g., "California")

### Legislation Layer

- **bill_number** (String): Primary bill identifier (e.g., "AB 1159", "HB 2466")
- **bill_title** (String): Full bill title
- **bill_url** (Text): Link to bill text or tracking page
- **bill_status** (String): Current status
  - Values: "Passed", "In Committee", "Proposed", "Pending", "Absent"
- **bill_status_details** (Text): Additional context (e.g., "Senate Education Committee as of May 20, 2026")
- **bill_status_as_of** (DateTime): When status was last verified
- **additional_bills** (JSON): Array of secondary bills related to K-12 AI
- **key_focus_areas** (JSON): Array of focus areas
  - Examples: "data_privacy", "academic_integrity", "student_protection", "equity", "teacher_training"

### State Guidance Layer

- **guidance_issued_by** (String): Name of issuing department (e.g., "California Department of Education")
- **guidance_exists** (Boolean): Whether state has released formal guidance
- **guidance_type** (Enum): Type of guidance
  - Values: "MANDATORY", "ADVISORY", "PROPOSED", "NONE"
- **guidance_core_principles** (JSON): Array of stated principles
  - Examples: "human_centered_ai", "data_privacy", "transparency", "bias_mitigation", "human_oversight", "academic_integrity", "equity"
- **guidance_issued_date** (DateTime): When guidance was released
- **guidance_url** (Text): Link to guidance document
- **guidance_implementation_phase** (String): Current phase of implementation
  - Values: "Planning", "Development", "Implementation", "Rollout", "Embedded"

### Implementation Details

- **teacher_certification_required** (Boolean): Whether teachers must be certified to teach AI/use AI
- **graduation_requirement** (Boolean): Whether AI literacy is a graduation requirement
- **graduation_year** (Integer): Year requirement goes into effect (e.g., 2027)
- **advisory_council** (String): Name of any advisory body established
- **pilot_programs** (JSON): Array of pilot program objects
  ```json
  [
    {
      "name": "AI Literacy Pilot",
      "duration": "3 years",
      "funding": 5000000,
      "schools_participating": 30,
      "focus": "Teacher training and curriculum development"
    }
  ]
  ```

### District Reality

- **districts_have_policies** (Boolean): Whether districts are required to/have adopted policies
- **example_district_actions** (JSON): Array of real examples of what districts are doing
  - Examples: "El Paso ISD creating custom policies", "1,600 students in 30 districts in AI curriculum pilot"
- **tools_in_use** (JSON): Array of AI tools being used in practice
  - Examples: "ChatGPT", "MagicSchool AI", "PowerBuddy", "Grammarly"

### Adoption Metrics

- **adoption_metrics** (JSON): Object with adoption statistics
  ```json
  {
    "student_usage_pct": 20,
    "educator_usage_pct": 6,
    "educator_concern_level": "high",
    "survey_year": 2025
  }
  ```

### Regional Context

- **unique_context** (Text): Geographic, cultural, or economic context
  - Examples: "Island state with unique infrastructure challenges", "Emphasis on how AI relates to Hawaii's history and culture"
- **stakeholder_requirements** (JSON): Array of special requirements
  - Examples: "Include local educators, elders, community members in policy development"

### Classification

- **regulatory_stance** (Enum): Primary regulatory approach
  - **PROHIBIT**: Explicitly prohibits AI use or student data for training
  - **RESTRICT**: Restricts certain uses, requires controls
  - **REGULATE**: Requires policies and oversight but doesn't restrict
  - **SUPPORT**: Proactively supporting adoption with resources
  - **MANDATE**: Requires/mandates AI education or use
  - **ABSENT**: No guidance or legislation yet

- **maturity** (Enum): How developed the policy/guidance is
  - **NASCENT**: Just introduced, early stage
  - **IN_PROGRESS**: Under development/pilot implementation
  - **ACTIVE**: Implemented and actively used
  - **MATURE**: Established, iterating, well-developed

### Metadata

- **last_updated** (DateTime): When this record was last updated
- **sources** (JSON): Array of source URLs where data came from
- **notes** (Text): Any additional context or caveats

## Related Tables

### legislation_updates (Audit Trail)

Tracks all changes to state records for compliance and historical tracking.

- **id** (Integer): Primary key
- **state_legislation_id** (Integer): Foreign key to state_legislation
- **field_changed** (String): Which field was updated (e.g., "bill_status", "regulatory_stance")
- **old_value** (Text): Previous value
- **new_value** (Text): New value
- **changed_at** (DateTime): When change occurred
- **changed_by** (String): Who made the change (e.g., "system", "user_id")
- **change_reason** (Text): Why the change was made

## Example Records

### California (PROHIBIT, ACTIVE)
```json
{
  "state_code": "CA",
  "state_name": "California",
  "bill_number": "AB 1159",
  "bill_title": "Student Data Protection Act",
  "bill_status": "In Committee",
  "regulatory_stance": "PROHIBIT",
  "maturity": "ACTIVE",
  "guidance_exists": true,
  "guidance_type": "ADVISORY",
  "guidance_core_principles": ["human_centered_ai", "data_privacy", "equity", "academic_integrity"],
  "key_focus_areas": ["data_privacy", "student_protection"]
}
```

### Hawaii (MANDATE, MATURE)
```json
{
  "state_code": "HI",
  "state_name": "Hawaii",
  "bill_number": "HB 1887",
  "bill_title": "AI Literacy Graduation Requirement",
  "bill_status": "Passed",
  "graduation_requirement": true,
  "graduation_year": 2028,
  "regulatory_stance": "MANDATE",
  "maturity": "MATURE",
  "teacher_certification_required": true,
  "pilot_programs": [
    {
      "duration": "3 years",
      "funding": 5000000,
      "focus": "Teacher training and curriculum development"
    }
  ],
  "unique_context": "Curriculum includes how AI relates to Hawaii's history and culture"
}
```

### Texas (ABSENT, NASCENT)
```json
{
  "state_code": "TX",
  "state_name": "Texas",
  "bill_number": null,
  "bill_status": "Absent",
  "guidance_exists": false,
  "regulatory_stance": "ABSENT",
  "maturity": "NASCENT",
  "districts_have_policies": true,
  "example_district_actions": ["El Paso ISD creating custom policies"],
  "tools_in_use": ["PowerBuddy", "MagicSchool AI"],
  "notes": "One of 16 states without formal K-12 AI guidance; districts implementing policies independently"
}
```

## Dashboard Query Examples

### Count states by stance
```sql
SELECT regulatory_stance, COUNT(*) as count
FROM state_legislation
GROUP BY regulatory_stance
ORDER BY count DESC;
```

### States with legislation passed
```sql
SELECT state_name, bill_number, bill_title
FROM state_legislation
WHERE bill_status = 'Passed'
ORDER BY state_name;
```

### States with guidance by maturity
```sql
SELECT state_name, guidance_type, maturity, guidance_issued_date
FROM state_legislation
WHERE guidance_exists = true
ORDER BY maturity DESC, guidance_issued_date DESC;
```

## Data Quality Guidelines

1. **Status dates**: Always update `bill_status_as_of` when `bill_status` changes
2. **Sources**: Always include at least one source URL for any claim
3. **Audit trail**: All changes are automatically tracked in `legislation_updates`
4. **Completeness**: Not all fields need to be populated for every state (e.g., `graduation_requirement` only if applicable)
5. **Precision**: Use JSON arrays for multi-value fields to enable filtering

## Future Enhancements

- Timeline data for tracking policy evolution over time
- Regional/geographic grouping (Northeast, South, etc.)
- Integration with legislative APIs for automated updates
- Student/educator usage survey data
- Comparative metrics between states
