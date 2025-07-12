# P0-020 - Design System Token Extraction
**Priority**: P0
**Status**: Not Started
**Estimated Effort**: 1 day
**Dependencies**: P0-014

## Goal & Success Criteria

### Goal
Extract machine-readable design tokens from the Anthrasite Design System HTML style guide for automated UI component validation and consistent design implementation across the application.

### Success Criteria
1. All colors extracted with proper categorization (primary/status/functional)
2. Typography scale captured with all size/weight/line-height combinations
3. Spacing tokens follow 8px base unit system
4. Animation tokens include duration and easing functions
5. WCAG contrast ratios documented for all color combinations
6. JSON file size ≤ 2KB with minification
7. Schema validation passes for token structure
8. Coverage ≥ 95% on token extraction logic

## Context & Background

### Business Context
The Anthrasite Design System embodies a synthesis-driven approach to transforming complex data into actionable insights. Currently, design values are embedded in HTML/CSS, making it difficult to enforce consistency across UI components. Extracting these values into machine-readable tokens enables:

- Automated style guide enforcement
- Prevention of hardcoded values in UI code
- Consistent application of the Anthrasite brand
- WCAG 2.1 AA accessibility compliance validation
- Foundation for Phase 0.5 UI components

### Technical Context
The existing `design/styleguide.html` contains:
- CSS custom properties defining core design values
- Inline styles with specific color, typography, and spacing values
- Accessibility data including contrast ratios
- Animation timing specifications
- Responsive breakpoint definitions

These need to be extracted into a structured JSON format following W3C Design Tokens Community Group recommendations.

### Current State
```
design/
├── styleguide.html    # Comprehensive Anthrasite Design System guide
```

## Technical Approach

### 1. Token Extraction Strategy
Use BeautifulSoup to parse the HTML and extract:
- CSS custom properties from the `:root` declaration
- Color values from `.color-swatch` elements
- Typography values from `.type-example` elements
- Spacing values from tables and demos
- Animation timings from the motion table
- Contrast ratios from the accessibility table

### 2. Token Structure Design
```json
{
  "colors": {
    "primary": {
      "anthracite": { "value": "#0a0a0a", "contrast": { "white": "20.4:1" } },
      "white": { "value": "#ffffff" },
      "synthesis-blue": { "value": "#0066ff" }
    },
    "status": {
      "critical": { "value": "#dc2626", "usage": "Critical issues" },
      "warning": { "value": "#f59e0b", "usage": "Medium priority" },
      "success": { "value": "#10b981", "usage": "Positive metrics" }
    }
  },
  "typography": {
    "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "scale": {
      "display": { "size": "72px", "weight": "300", "lineHeight": "0.9" },
      "h1": { "size": "48px", "weight": "400", "lineHeight": "1.1" }
    }
  },
  "spacing": {
    "base": "8px",
    "scale": { "xs": "8px", "sm": "16px", "md": "24px" }
  },
  "animation": {
    "micro": { "duration": "150ms", "easing": "ease-out" }
  }
}
```

### 3. Implementation Steps
1. Create extraction script using BeautifulSoup4
2. Parse HTML structure and extract values by category
3. Transform to standardized token format
4. Validate against JSON schema
5. Minify output to meet size constraint
6. Write comprehensive tests for extraction logic

## Acceptance Criteria

1. **Token Completeness**
   - All 10 colors extracted (3 primary, 3 status, 4 functional)
   - All 9 typography scale values captured
   - All 7 spacing scale values included
   - All 4 animation timings documented
   - All 3 breakpoints defined

2. **Token Quality**
   - JSON validates against design token schema
   - File size ≤ 2KB when minified
   - All color contrast ratios included where specified
   - Usage descriptions preserved for contextual tokens

3. **Code Quality**
   - Extraction logic has ≥95% test coverage
   - No hardcoded values in extraction code
   - Error handling for missing/malformed HTML elements
   - Type hints on all functions

4. **Integration Ready**
   - Tokens importable as Python module
   - Documentation includes usage examples
   - Existing hardcoded values identified for replacement

## Dependencies

### Task Dependencies
- **P0-014**: Test Suite Re-Enablement and Coverage Plan (required for UI task validation)

### Technical Dependencies
- beautifulsoup4>=4.12.0 - HTML parsing
- pydantic>=2.0.0 - Schema validation
- pytest>=7.4.0 - Testing framework
- jsonschema>=4.19.0 - JSON validation

## Testing Strategy

### Unit Tests
1. **Extraction Tests** (`test_token_extraction.py`)
   - Test color extraction from swatches
   - Test typography extraction from examples
   - Test spacing extraction from tables
   - Test CSS custom property parsing
   - Test error handling for missing elements

2. **Validation Tests** (`test_token_validation.py`)
   - JSON schema compliance
   - File size constraints
   - Required token presence
   - Value format validation

3. **Integration Tests** (`test_token_usage.py`)
   - Token import functionality
   - Usage in style generation
   - Backward compatibility

### Test Coverage Requirements
- Minimum 95% line coverage on extraction logic
- 100% coverage on validation functions
- All error paths tested

## Rollback Plan

### Rollback Triggers
1. Token extraction produces invalid JSON
2. File size exceeds 2KB limit
3. Missing critical design values
4. Breaking changes to existing UI code

### Rollback Steps
1. Delete `design/design_tokens.json`
2. Remove `design/__init__.py` 
3. Revert any code changes referencing tokens
4. Remove test files from `tests/unit/design/`

### Rollback Impact
- No database changes to revert
- No API modifications to undo
- UI continues using existing hardcoded values
- No user-facing impact

## Validation Framework

### Pre-Implementation Validation
- [ ] Styleguide HTML exists and is valid
- [ ] BeautifulSoup can parse the HTML successfully
- [ ] All expected design values present in source

### Post-Implementation Validation
- [ ] All tokens extracted match source values
- [ ] JSON schema validation passes
- [ ] File size ≤ 2KB requirement met
- [ ] Tests achieve ≥95% coverage
- [ ] No regression in existing UI components

### CI/CD Validation Gates
```bash
# Syntax and style checks
ruff check design/ tests/unit/design/ --fix
mypy design/ --strict

# Run tests with coverage
pytest tests/unit/design/ -v --cov=design --cov-report=term-missing

# Validate JSON output
python -m json.tool design/design_tokens.json > /dev/null

# Check file size (cross-platform)
[ $(wc -c < design/design_tokens.json) -le 2048 ] || exit 1

# Schema validation
python -c "import json, jsonschema; schema=json.load(open('design/token_schema.json')); tokens=json.load(open('design/design_tokens.json')); jsonschema.validate(tokens, schema)"
```

### Missing-Checks Framework
**Required for UI Tasks:**
- [ ] Pre-commit hooks configured for Python linting
- [ ] Branch protection with required status checks
- [ ] Visual regression testing setup
- [ ] Style-guide enforcement via tokens
- [ ] WCAG 2.1 AA contrast validation
- [ ] Design token naming convention linting

**Additional Checks:**
- [ ] Token documentation auto-generation
- [ ] Usage analytics for token adoption
- [ ] Visual diff for token changes
- [ ] Integration with design tools