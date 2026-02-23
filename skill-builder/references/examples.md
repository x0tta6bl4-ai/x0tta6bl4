# Примеры готовых скиллов

## Пример 1: Document Creation (docx)

```yaml
---
name: docx
description: Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. Use when Claude needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks
---

# DOCX Skill

## Instructions

### Creating documents
1. Use python-docx library
2. Structure with proper headings hierarchy
3. Apply consistent formatting

### Editing existing documents
1. Unpack the docx (it's a zip)
2. Modify word/document.xml
3. Validate changes
4. Repack

## Validation
Run `scripts/validate.py` before finalizing.
```

## Пример 2: Code Review

```yaml
---
name: code-review
description: Reviews code for bugs, style issues, and improvements. Use when user asks to "review code", "check my code", "find bugs", or uploads code files for feedback.
---

# Code Review Skill

## Review Process

1. **Security check**: Look for vulnerabilities
2. **Bug detection**: Identify logical errors
3. **Style review**: Check against conventions
4. **Performance**: Suggest optimizations
5. **Feedback**: Clear, actionable comments

## Output Format

```markdown
## Review Summary

### 🔴 Critical Issues
[List critical bugs/security issues]

### 🟡 Improvements
[List suggested improvements]

### 🟢 Positive
[What's done well]
```
```

## Пример 3: MCP Enhancement (Linear)

```yaml
---
name: linear-workflows
description: Manages Linear project workflows including sprint planning, task creation, and status tracking. Use when user mentions "sprint", "Linear tasks", "project planning", or asks to "create tickets".
---

# Linear Workflows

## Sprint Planning

### Step 1: Fetch current status
```
Call MCP: linear_get_projects
```

### Step 2: Analyze capacity
Review team velocity from last 3 sprints.

### Step 3: Create tasks
```
Call MCP: linear_create_issue
Parameters: title, description, estimate, assignee
```

### Step 4: Organize
Apply proper labels and set priorities.

## Error Handling

**Connection failed:**
1. Check MCP server status in Settings > Extensions
2. Verify API key is valid
3. Try reconnecting
```

## Пример 4: Brand Guidelines

```yaml
---
name: brand-guidelines
description: Applies company brand colors, typography, and style to documents and designs. Use when user asks to "apply brand", "use company colors", "follow brand guidelines", or creates marketing materials.
---

# Brand Guidelines

## Colors
- Primary: #1a73e8
- Secondary: #34a853
- Accent: #ea4335

## Typography
- Headings: Inter Bold
- Body: Inter Regular
- Code: JetBrains Mono

## Usage

When creating any visual content:
1. Load `assets/brand-colors.json`
2. Apply primary color to headings
3. Use secondary for CTAs
4. Maintain 16px minimum body text

## Templates

See `assets/templates/` for:
- presentation-template.pptx
- document-template.docx
- email-template.html
```

## Пример 5: API Documentation Generator

```yaml
---
name: api-docs-generator
description: Generates API documentation from code. Use when user asks to "document API", "create API docs", "generate OpenAPI spec", or mentions "swagger documentation".
---

# API Documentation Generator

## Process

### Step 1: Analyze endpoints
Parse code for route definitions, parameters, responses.

### Step 2: Extract types
Get request/response schemas from type definitions.

### Step 3: Generate documentation
Create OpenAPI 3.0 spec with:
- Endpoint descriptions
- Parameter documentation  
- Response examples
- Error codes

### Step 4: Validate
```bash
python scripts/validate_openapi.py output/api.yaml
```

## Output Format

```yaml
openapi: 3.0.0
info:
  title: API Name
  version: 1.0.0
paths:
  /endpoint:
    get:
      summary: Description
      parameters: []
      responses:
        200:
          description: Success
```
```

## Пример 6: Iterative Refinement Pattern

```yaml
---
name: report-generator
description: Creates detailed analytical reports with iterative quality improvement. Use when user asks to "create report", "analyze data and write report", or "generate analysis document".
---

# Report Generator

## Iterative Process

### Initial Draft
1. Fetch data
2. Generate first draft
3. Save to temporary file

### Quality Check
Run `scripts/check_report.py` to identify:
- Missing sections
- Inconsistent formatting
- Data validation errors

### Refinement Loop
1. Address each identified issue
2. Regenerate affected sections
3. Re-validate
4. Repeat until quality threshold met

### Finalization
1. Apply final formatting
2. Generate executive summary
3. Save final version

## Quality Criteria
- All sections present
- Data accuracy verified
- Formatting consistent
- Executive summary < 200 words
```

## Пример 7: Multi-MCP Coordination

```yaml
---
name: design-handoff
description: Coordinates design-to-development handoff across Figma, Drive, and Linear. Use when user mentions "design handoff", "developer specs", or "hand off to engineering".
---

# Design Handoff

## Phase 1: Design Export (Figma MCP)
1. Export design assets
2. Generate specifications
3. Create asset manifest

## Phase 2: Asset Storage (Drive MCP)
1. Create project folder
2. Upload all assets
3. Generate shareable links

## Phase 3: Task Creation (Linear MCP)
1. Create development tasks
2. Attach asset links
3. Assign to team

## Phase 4: Notification (Slack MCP)
1. Post handoff summary to #engineering
2. Include links and task references

## Validation Between Phases
Before moving to next phase:
- Verify previous phase completed
- Check all assets accessible
- Confirm no errors
```

## Шаблон для нового скилла

```yaml
---
name: [kebab-case-name]
description: [Что делает]. Use when [конкретные триггеры и фразы пользователя].
---

# [Название]

## Instructions

### Step 1: [Название шага]
[Чёткие инструкции]

### Step 2: [Название шага]
[Чёткие инструкции]

## Examples

### Example: [Типичный сценарий]
User says: "[Что говорит пользователь]"
Actions:
1. [Действие 1]
2. [Действие 2]
Result: [Ожидаемый результат]

## Troubleshooting

**Error: [Сообщение]**
Cause: [Причина]
Solution: [Решение]
```
