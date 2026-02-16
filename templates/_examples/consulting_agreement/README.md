# Consulting Agreement Template

This template demonstrates all v2 features of Codraft:

## Features

### 1. Unconditional Variables
- Client and consultant details (name, address, email)
- Effective date
- Scope of services
- Total fee and payment terms
- Governing law and arbitration body
- Signature dates

### 2. Boolean Conditional
- **IP Assignment Clause** (`{% if include_ip_assignment %}`)
  - If `include_ip_assignment` is true, the IP ownership section is included
  - If false, the section is excluded
  - Collects: `ip_ownership_entity`, `ip_assignment_date`

### 3. Value-Based Conditional
- **Bank Details** (`{% if payment_method == 'bank_transfer' %}`)
  - If `payment_method` is "bank_transfer", collect bank details
  - If "check", collect check payment details
  - Collects: `bank_name`, `account_name`, `account_number`, `swift_code` (if bank transfer)
  - Collects: `check_payable_to` (if check)

### 4. Loops
- **Project Milestones** (`{% for milestone in milestones %}`)
  - Collects a list of milestones
  - Each milestone has: `name`, `description`, `due_date`
  - Renders as a table with milestone number, name, description, and due date

### 5. Developer Configuration (`config.yaml`)
- Custom questions for each variable
- Type inference overrides (e.g., `payment_method` as `choice` type)
- Interview grouping hints
- Validation rules
- Default values
- Format hints

## Template Structure

```
consulting_agreement/
├── Consulting-Agreement.docx    # The template document
├── config.yaml                  # Developer configuration
└── README.md                    # This file
```

## Usage

1. Place this template in `templates/consulting_agreement/`
2. The Analyzer will automatically generate a v2 manifest
3. The Orchestrator will use the config.yaml for custom questions and grouping
4. The Renderer will handle conditionals and loops during rendering

## Example Interview Flow

1. **Parties** — Collect client and consultant details
2. **Engagement Terms** — Collect effective date, scope, fee, payment method
3. **IP Assignment** (conditional) — Only asked if `include_ip_assignment` is true
4. **Bank Details** (conditional) — Only asked if `payment_method == 'bank_transfer'`
5. **Legal Terms** — Collect governing law and arbitration body
6. **Signatures** — Collect signature dates
7. **Milestones** (loop) — Collect multiple milestones with name, description, due date

## Validation Rules

- Client signature date must be on or after the effective date
- Consultant signature date must be on or after the effective date