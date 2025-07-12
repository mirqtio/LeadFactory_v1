# Generate UI Style Guide

Create a one-time UI style guide with design tokens, component patterns, and accessibility standards that all future PRPs will reference.

## Usage
Arguments: $ARGUMENTS (optional: --regenerate to force refresh)

## Process Overview

1. **Research Design System Best Practices**
   - Analyze existing UI patterns in codebase
   - Research design token standards (W3C Design Tokens, Style Dictionary)
   - Study accessibility requirements (WCAG 2.1 AA)
   - Review modern component libraries (Fluent, Material, Tailwind)

2. **Generate Core Artifacts**
   - Design tokens JSON (colors, spacing, typography, shadows)
   - Tailwind config extending tokens
   - Component patterns library
   - Storybook configuration
   - Accessibility checklist

3. **Validate and Commit**
   - Test token application in sample components
   - Verify accessibility compliance
   - Generate documentation

## Output Structure

```
.claude/ui-styleguide/
├── tokens/
│   ├── colors.json
│   ├── spacing.json
│   ├── typography.json
│   └── index.ts (exports)
├── tailwind/
│   └── tailwind.config.js
├── storybook/
│   ├── .storybook/
│   └── stories/
├── components/
│   └── patterns.md
└── README.md
```

## Research Agent Task

```
Task: Research UI design system best practices
1. Analyze existing LeadFactory UI code for patterns
2. Research design token specifications:
   - W3C Design Tokens Community Group
   - Style Dictionary by Amazon
   - Tailwind CSS design principles
3. Study accessibility standards:
   - WCAG 2.1 AA requirements
   - ARIA patterns for common components
   - Keyboard navigation best practices
4. Review enterprise design systems:
   - Fluent UI (Microsoft)
   - Material Design (Google)
   - Ant Design (Alibaba)
5. Synthesize findings into actionable guidelines
6. Save to .claude/research_cache/ui_styleguide_research.txt
```

## Generation Task

```
Task: Generate UI style guide artifacts
1. Create design tokens:
   - Primary/secondary/accent colors with shades
   - Spacing scale (4px base: 1, 2, 3, 4, 6, 8, 12, 16, 24, 32)
   - Typography scale (12, 14, 16, 18, 20, 24, 32, 48)
   - Border radius, shadows, transitions
2. Generate Tailwind config:
   - Extend default theme with tokens
   - Custom utility classes for common patterns
3. Create component patterns:
   - Form inputs (text, select, checkbox, radio)
   - Buttons (primary, secondary, ghost, danger)
   - Cards and panels
   - Navigation components
   - Data display (tables, lists)
4. Set up Storybook:
   - Configure with design tokens addon
   - Create stories for each pattern
   - Add interaction tests
5. Write accessibility guidelines:
   - Required ARIA labels
   - Focus management rules
   - Color contrast requirements
   - Keyboard navigation patterns
```

## Validation Gates

1. **Token Consistency Check**
   - All colors meet WCAG contrast ratios
   - Spacing follows consistent scale
   - Typography is readable at all sizes

2. **Component Coverage**
   - All common UI patterns documented
   - Each pattern has Storybook story
   - Accessibility notes included

3. **Integration Test**
   - Sample component uses only tokens
   - Tailwind config loads correctly
   - Storybook builds without errors

## Cache Strategy

- Style guide cached at `.claude/ui-styleguide/`
- Regenerate only with --regenerate flag
- Version tracked in `styleguide-version.json`
- PRPs reference specific version

## Integration with PRP Generation

After this command completes, the PRP generation process will:
1. Auto-detect UI-related tasks
2. Inject UI scaffold sections using tokens
3. Add UI-specific acceptance criteria
4. Include accessibility requirements

## Style Guide Structure (Professional Format)

### Color Palette
- **Primary Colors**: Brand colors for main UI elements
- **Secondary Colors**: Supporting colors for hover states and accents
- **Accent Colors**: High-emphasis colors for CTAs and notifications
- **Functional Colors**: Success, error, warning, info states
- **Background Colors**: Surface colors for cards, modals, and screens

### Typography
- **Font Family**: Primary and fallback fonts
- **Font Weights**: Regular (400), Medium (500), Semibold (600), Bold (700)
- **Text Styles**: H1-H3, Body (Large/Normal/Small), Caption, Button, Link

### Component Styling
- **Buttons**: Primary, Secondary, Text, Disabled states
- **Cards**: Shadow, radius, padding specifications
- **Input Fields**: Height, borders, active states
- **Icons**: Sizes and color usage

### Spacing System
Based on 4px grid:
- 4px - Micro spacing
- 8px - Small spacing
- 16px - Default spacing
- 24px - Medium spacing
- 32px - Large spacing
- 48px - Extra large spacing

### Motion & Animation
- Standard transitions (200ms)
- Emphasis animations (300ms)
- Microinteractions (150ms)
- Page transitions (350ms)

## Example Token Structure

```json
{
  "colors": {
    "primary": {
      "main": "#0A5F55",
      "light": "#4CAF94",
      "pale": "#E6F4F1",
      "white": "#F8F9FA"
    },
    "accent": {
      "teal": "#00BFA5",
      "yellow": "#FFD54F"
    },
    "functional": {
      "success": "#43A047",
      "error": "#E53935",
      "neutral": "#9E9E9E",
      "text": "#424242"
    },
    "background": {
      "white": "#FFFFFF",
      "light": "#F5F7F9",
      "dark": "#263238"
    }
  },
  "spacing": {
    "micro": "4px",
    "small": "8px",
    "default": "16px",
    "medium": "24px",
    "large": "32px",
    "xlarge": "48px"
  },
  "typography": {
    "h1": {
      "size": "28px",
      "lineHeight": "32px",
      "weight": 700,
      "letterSpacing": "-0.2px"
    },
    "body": {
      "size": "15px",
      "lineHeight": "20px",
      "weight": 400,
      "letterSpacing": "0px"
    }
  }
}
```

## Success Criteria

- [ ] Design tokens cover all UI needs
- [ ] Zero hardcoded colors/spacing in new PRPs
- [ ] Accessibility gates pass on all components
- [ ] Visual regression tests configured
- [ ] Documentation clear and searchable