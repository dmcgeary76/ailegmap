> **Out of date (2026-09-02):** this document describes the PostgreSQL / `state_legislation` design. The current setup, data model and endpoints are in the top-level [README](../README.md) and `CHANGELOG.md`; the live API reference is at http://localhost:8000/docs.

# API Specification

## Base URL

```
http://localhost:8000
```

## Authentication

Currently no authentication required. Future versions will add API key or OAuth2.

## Endpoints

### Health Check

**GET** `/api/health`

Check if API is running.

**Response:**
```json
{
  "status": "ok"
}
```

### Get All States

**GET** `/api/states`

Retrieve all state legislation records with optional filtering.

**Query Parameters:**
- `stance` (string, optional): Filter by regulatory stance (PROHIBIT, RESTRICT, REGULATE, SUPPORT, MANDATE, ABSENT)
- `maturity` (string, optional): Filter by maturity (NASCENT, IN_PROGRESS, ACTIVE, MATURE)

**Examples:**
```
GET /api/states
GET /api/states?stance=SUPPORT
GET /api/states?maturity=ACTIVE
GET /api/states?stance=SUPPORT&maturity=ACTIVE
```

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "state_code": "CA",
    "state_name": "California",
    "bill_number": "AB 1159",
    "bill_title": "Student Data Protection Act",
    "bill_status": "In Committee",
    "bill_status_details": "Senate Education Committee as of May 20, 2026",
    "bill_url": "https://...",
    "guidance_exists": true,
    "guidance_type": "ADVISORY",
    "guidance_issued_by": "California Department of Education",
    "guidance_core_principles": ["data_privacy", "equity"],
    "regulatory_stance": "PROHIBIT",
    "maturity": "ACTIVE",
    "last_updated": "2026-06-24T00:00:00",
    "updates": []
  }
]
```

### Get Specific State

**GET** `/api/states/{state_code}`

Retrieve detailed record for a specific state (e.g., "CA").

**Path Parameters:**
- `state_code` (string): Two-letter state code

**Response (200 OK):** Same as individual state object above

**Response (404 Not Found):**
```json
{
  "detail": "State XX not found"
}
```

### Create State Record

**POST** `/api/states`

Create a new state legislation record.

**Request Body:**
```json
{
  "state_code": "CA",
  "state_name": "California",
  "bill_number": "AB 1159",
  "bill_title": "Student Data Protection Act",
  "bill_status": "In Committee",
  "guidance_exists": true,
  "guidance_type": "ADVISORY",
  "guidance_issued_by": "California Department of Education",
  "guidance_core_principles": ["data_privacy", "equity"],
  "regulatory_stance": "PROHIBIT",
  "maturity": "ACTIVE",
  "sources": ["https://..."]
}
```

**Response (200 OK):** Returns created state object with ID

**Response (400 Bad Request):**
```json
{
  "detail": "State CA already exists"
}
```

### Update State Record

**PUT** `/api/states/{state_code}`

Update an existing state record. Only provided fields will be updated.

**Path Parameters:**
- `state_code` (string): Two-letter state code

**Request Body (all optional):**
```json
{
  "bill_status": "Passed",
  "bill_status_details": "Signed into law on June 10, 2026",
  "regulatory_stance": "RESTRICT",
  "maturity": "ACTIVE",
  "notes": "New update"
}
```

**Response (200 OK):** Returns updated state object

**Response (404 Not Found):**
```json
{
  "detail": "State XX not found"
}
```

### Dashboard Summary

**GET** `/api/dashboard/summary`

Get summary statistics for the dashboard.

**Response (200 OK):**
```json
{
  "total_states": 50,
  "states_by_stance": {
    "PROHIBIT": 5,
    "RESTRICT": 12,
    "REGULATE": 18,
    "SUPPORT": 10,
    "MANDATE": 2,
    "ABSENT": 3
  },
  "states_by_maturity": {
    "NASCENT": 8,
    "IN_PROGRESS": 15,
    "ACTIVE": 20,
    "MATURE": 7
  },
  "states_with_guidance": 35,
  "states_with_legislation": 42,
  "recent_updates": [
    {
      "id": 1,
      "state_legislation_id": 1,
      "field_changed": "bill_status",
      "old_value": "Proposed",
      "new_value": "In Committee",
      "changed_at": "2026-06-20T10:30:00",
      "changed_by": "user",
      "change_reason": "Status update"
    }
  ]
}
```

## Error Responses

All errors follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

Common HTTP status codes:
- `200 OK`: Successful request
- `400 Bad Request`: Invalid request body
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

## Data Types

### RegulatoryStance (Enum)
```
"PROHIBIT" | "RESTRICT" | "REGULATE" | "SUPPORT" | "MANDATE" | "ABSENT"
```

### Maturity (Enum)
```
"NASCENT" | "IN_PROGRESS" | "ACTIVE" | "MATURE"
```

### GuidanceType (Enum)
```
"MANDATORY" | "ADVISORY" | "PROPOSED" | "NONE"
```

## Rate Limiting

Currently no rate limiting. Will be added in future versions.

## CORS

CORS is enabled for all origins in development. Update in production.

## API Documentation

Interactive API documentation available at:
```
http://localhost:8000/docs  (Swagger UI)
http://localhost:8000/redoc (ReDoc)
```

## Future Endpoints

- Timeline data for viewing policy evolution
- Comparison endpoint for side-by-side state analysis
- Search/filter enhancements
- Bulk upload for data seeding
- Export functionality (CSV, JSON)
