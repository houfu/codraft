# Event Invitation Template

This template demonstrates all v2 features of Codraft:

## Features

### 1. Unconditional Variables
- Event name, date, time, location, and address
- Event description
- Host name and address
- RSVP information (date, email, phone)

### 2. Boolean Conditional
- **Dietary Requirements Section** (`{% if include_dietary_section %}`)
  - If `include_dietary_section` is true, a dietary requirements table is included
  - If false, the section is excluded
  - Collects: `dietary_requirements` for each guest

### 3. Loops
- **Guest List** (`{% for guest in guests %}`)
  - Collects a list of guests
  - Each guest has: `name`, `email`, `phone`, `num_guests`
  - `dietary_requirements` is collected per guest only when `include_dietary_section` is true
  - Renders as a table with guest details

### 4. Developer Configuration (`config.yaml`)
- Custom questions for each variable
- Type inference overrides (e.g., `include_dietary_section` as `boolean` type)
- Interview grouping hints
- Validation rules
- Default values
- Format hints

## Template Structure

```
event_invitation/
├── event-invitation.html         # The template document
├── config.yaml                   # Developer configuration
└── README.md                     # This file
```

## Usage

1. Place this template in `templates/event_invitation/`
2. The Analyzer will automatically generate a v2 manifest
3. The Orchestrator will use the config.yaml for custom questions and grouping
4. The Renderer will handle conditionals and loops during rendering

## Example Interview Flow

1. **Event Details** — Collect event name, date, time, location, description
2. **Host Information** — Collect host name and address
3. **RSVP Information** — Collect RSVP deadline, email, phone
4. **Guest List** (loop) — Collect multiple guests with name, email, phone, num_guests
5. **Dietary Requirements** (conditional loop) — Collect dietary_requirements per guest, only if `include_dietary_section` is true

## Validation Rules

- RSVP deadline must be on or before the event date
- Event start time must be a valid time

## Output

The template produces both HTML and PDF files:
- `event-invitation.html` — The rendered HTML version
- `event-invitation.pdf` — The PDF version (via WeasyPrint)