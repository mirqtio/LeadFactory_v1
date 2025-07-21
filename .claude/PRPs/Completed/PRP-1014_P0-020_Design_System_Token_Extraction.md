# PRP-P0-028: Design-System UI Foundations

## Summary

Create and publish a reusable @leadfactory/ui-core package containing all shared front-end assets, design tokens, Tailwind config, and core UI components. This foundational package will ensure consistent design implementation across all LeadFactory UI features and enable rapid UI development.

## Dependencies

- **P0-020**: Design System Token Extraction (must have design tokens JSON ready)

## Acceptance Criteria

### 1. Package Setup & Publishing (Weight: 20%)
- [ ] Monorepo structure with `packages/ui-core` directory
- [ ] Published to GitHub Packages as @leadfactory/ui-core
- [ ] Semantic versioning with automated releases
- [ ] ESM bundle size < 50 kB gzipped
- [ ] TypeScript types for all exports

### 2. Design Token Integration (Weight: 25%)
- [ ] Process `design/design_tokens.json` into Tailwind preset
- [ ] Style Dictionary converts tokens to CSS custom properties
- [ ] All styles derived from design tokens (no magic numbers)
- [ ] Token validation prevents hardcoded values
- [ ] Automatic token documentation generation

### 3. Core Components (Weight: 30%)
- [ ] Button component with all variants and states
- [ ] Card component with flexible content areas
- [ ] Badge component with color and size variants
- [ ] Table component with sorting and pagination
- [ ] Modal component with focus management
- [ ] Stepper component for multi-step workflows
- [ ] Input component with validation states
- [ ] Dropdown component with keyboard navigation

### 4. Documentation & Testing (Weight: 15%)
- [ ] Storybook 7 documents all components
- [ ] Visual regression tests via Chromatic
- [ ] Unit test coverage ≥ 90%
- [ ] Accessibility score ≥ 98 (axe-core)
- [ ] Component usage examples

### 5. Developer Experience (Weight: 10%)
- [ ] Hot module replacement in development
- [ ] Clear migration guide from inline styles
- [ ] VS Code IntelliSense for design tokens
- [ ] Pre-commit hooks for style validation
- [ ] Component playground for experimentation

## Technical Implementation

### Phase 1: Package Structure
```typescript
// packages/ui-core/package.json
{
  "name": "@leadfactory/ui-core",
  "version": "1.0.0",
  "type": "module",
  "main": "./dist/index.js",
  "module": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": {
      "import": "./dist/index.js",
      "types": "./dist/index.d.ts"
    },
    "./styles": {
      "import": "./dist/styles/index.css"
    },
    "./tailwind": {
      "import": "./dist/tailwind-preset.js"
    }
  },
  "scripts": {
    "build": "tsup",
    "dev": "tsup --watch",
    "test": "vitest",
    "storybook": "storybook dev -p 6006",
    "chromatic": "chromatic --exit-zero-on-changes"
  },
  "peerDependencies": {
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  },
  "devDependencies": {
    "@storybook/react-vite": "^7.0.0",
    "@testing-library/react": "^14.0.0",
    "chromatic": "^6.0.0",
    "style-dictionary": "^3.8.0",
    "tailwindcss": "^3.3.0",
    "tsup": "^7.0.0",
    "vitest": "^0.34.0"
  }
}
```

### Phase 2: Design Token Processing
```javascript
// packages/ui-core/scripts/build-tokens.js
const StyleDictionary = require('style-dictionary');
const tokens = require('../../../design/design_tokens.json');

// Configure Style Dictionary
StyleDictionary.extend({
  source: ['design/design_tokens.json'],
  platforms: {
    css: {
      transformGroup: 'css',
      buildPath: 'dist/styles/',
      files: [{
        destination: 'tokens.css',
        format: 'css/variables',
        options: {
          outputReferences: true
        }
      }]
    },
    js: {
      transformGroup: 'js',
      buildPath: 'dist/',
      files: [{
        destination: 'tokens.js',
        format: 'javascript/es6'
      }]
    },
    tailwind: {
      transformGroup: 'js',
      buildPath: 'dist/',
      files: [{
        destination: 'tailwind-tokens.js',
        format: 'javascript/module',
        filter: (token) => token.attributes.category !== 'asset'
      }]
    }
  }
}).buildAllPlatforms();

// Generate Tailwind preset
const generateTailwindPreset = () => {
  const preset = {
    theme: {
      extend: {
        colors: generateColorScale(tokens.color),
        spacing: generateSpacingScale(tokens.spacing),
        typography: generateTypographyScale(tokens.typography),
        animation: generateAnimationScale(tokens.animation)
      }
    }
  };
  
  return preset;
};
```

### Phase 3: Core Components Implementation
```typescript
// packages/ui-core/src/components/Button/Button.tsx
import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../utils/cn';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-synthesis-primary text-synthesis-primary-foreground hover:bg-synthesis-primary-hover',
        secondary: 'bg-synthesis-secondary text-synthesis-secondary-foreground hover:bg-synthesis-secondary-hover',
        outline: 'border border-synthesis-border bg-transparent hover:bg-synthesis-accent',
        ghost: 'hover:bg-synthesis-accent hover:text-synthesis-accent-foreground',
        danger: 'bg-synthesis-danger text-white hover:bg-synthesis-danger-hover'
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4',
        lg: 'h-12 px-6 text-lg'
      }
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md'
    }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, loading, children, disabled, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading && <Spinner className="mr-2 h-4 w-4 animate-spin" />}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';
```

```typescript
// packages/ui-core/src/components/Table/Table.tsx
import React from 'react';
import { useTable, useSortBy, usePagination } from '@tanstack/react-table';

export interface TableProps<TData> {
  data: TData[];
  columns: ColumnDef<TData>[];
  pageSize?: number;
  onRowClick?: (row: TData) => void;
}

export function Table<TData>({ data, columns, pageSize = 10, onRowClick }: TableProps<TData>) {
  const table = useTable(
    {
      data,
      columns,
      initialState: {
        pagination: {
          pageSize
        }
      }
    },
    useSortBy,
    usePagination
  );

  return (
    <div className="overflow-hidden rounded-lg border border-synthesis-border">
      <table className="w-full">
        <thead className="bg-synthesis-muted">
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <th
                  key={header.id}
                  className="px-4 py-3 text-left text-sm font-medium text-synthesis-foreground"
                  onClick={header.column.getToggleSortingHandler()}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                  {header.column.getIsSorted() && (
                    <span className="ml-1">
                      {header.column.getIsSorted() === 'asc' ? '↑' : '↓'}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr
              key={row.id}
              className="border-t border-synthesis-border hover:bg-synthesis-muted/50 cursor-pointer"
              onClick={() => onRowClick?.(row.original)}
            >
              {row.getVisibleCells().map(cell => (
                <td key={cell.id} className="px-4 py-3 text-sm">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <TablePagination table={table} />
    </div>
  );
}
```

### Phase 4: Storybook Configuration
```typescript
// packages/ui-core/.storybook/main.ts
import type { StorybookConfig } from '@storybook/react-vite';

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(js|jsx|ts|tsx|mdx)'],
  addons: [
    '@storybook/addon-essentials',
    '@storybook/addon-a11y',
    '@storybook/addon-designs',
    '@chromatic-com/storybook'
  ],
  framework: {
    name: '@storybook/react-vite',
    options: {}
  },
  viteFinal: (config) => {
    // Add design token aliases
    config.resolve.alias = {
      ...config.resolve.alias,
      '@tokens': path.resolve(__dirname, '../dist/tokens.js')
    };
    return config;
  }
};

export default config;
```

```typescript
// packages/ui-core/src/components/Button/Button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta = {
  title: 'Components/Button',
  component: Button,
  parameters: {
    layout: 'centered',
    design: {
      type: 'figma',
      url: 'https://www.figma.com/file/xxx/LeadFactory-Design-System'
    }
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['primary', 'secondary', 'outline', 'ghost', 'danger']
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg']
    }
  }
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {
  args: {
    children: 'Click me',
    variant: 'primary'
  }
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex gap-4">
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="outline">Outline</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="danger">Danger</Button>
    </div>
  )
};
```

### Phase 5: Testing Setup
```typescript
// packages/ui-core/src/components/Button/Button.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from '@axe-core/react';
import { Button } from './Button';

describe('Button', () => {
  it('renders children correctly', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('handles click events', async () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    
    await userEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('shows loading state', () => {
    render(<Button loading>Loading</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  it('has no accessibility violations', async () => {
    const { container } = render(<Button>Accessible button</Button>);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
```

### Phase 6: Build Configuration
```typescript
// packages/ui-core/tsup.config.ts
import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['esm'],
  dts: true,
  splitting: true,
  sourcemap: true,
  clean: true,
  minify: true,
  external: ['react', 'react-dom'],
  esbuildOptions(options) {
    options.banner = {
      js: '"use client"'
    };
  },
  onSuccess: async () => {
    // Run post-build tasks
    await import('./scripts/build-tokens.js');
    console.log('✅ Design tokens built successfully');
  }
});
```

## File Structure

```
packages/ui-core/
├── src/
│   ├── components/
│   │   ├── Button/
│   │   │   ├── Button.tsx
│   │   │   ├── Button.test.tsx
│   │   │   ├── Button.stories.tsx
│   │   │   └── index.ts
│   │   ├── Card/
│   │   ├── Badge/
│   │   ├── Table/
│   │   ├── Modal/
│   │   ├── Stepper/
│   │   ├── Input/
│   │   └── Dropdown/
│   ├── hooks/
│   │   ├── useTheme.ts
│   │   ├── useFocusTrap.ts
│   │   └── useMediaQuery.ts
│   ├── utils/
│   │   ├── cn.ts
│   │   ├── validation.ts
│   │   └── accessibility.ts
│   └── index.ts
├── dist/
│   ├── index.js
│   ├── index.d.ts
│   ├── styles/
│   │   ├── index.css
│   │   └── tokens.css
│   └── tailwind-preset.js
├── .storybook/
│   ├── main.ts
│   ├── preview.ts
│   └── theme.ts
├── scripts/
│   ├── build-tokens.js
│   ├── validate-tokens.js
│   └── publish.js
├── package.json
├── tsup.config.ts
├── vitest.config.ts
└── README.md
```

## Testing Requirements

### Unit Tests
```typescript
// Every component must have tests for:
// 1. Rendering
// 2. User interactions
// 3. Accessibility
// 4. Edge cases
// 5. TypeScript types
```

### Visual Regression Tests
```typescript
// .storybook/test-runner.ts
import { checkA11y, injectAxe } from '@storybook/addon-a11y';

export const preRender = async (page) => {
  await injectAxe(page);
};

export const postRender = async (page) => {
  await checkA11y(page, '#root', {
    detailedReport: true,
    detailedReportOptions: {
      html: true
    }
  });
};
```

### Integration Tests
```typescript
// Test usage in a sample app
// packages/ui-core/tests/integration/sample-app.test.tsx
import { render } from '@testing-library/react';
import { Button, Card, Table } from '@leadfactory/ui-core';

test('components work together', () => {
  render(
    <Card>
      <Table data={[]} columns={[]} />
      <Button>Action</Button>
    </Card>
  );
  // Assert no errors
});
```

## Security Considerations

1. **Dependency Security**
   - Automated dependency scanning
   - No runtime CSS injection
   - CSP-compatible styles

2. **Input Sanitization**
   - All user inputs sanitized
   - XSS prevention in components
   - Safe HTML rendering

3. **Build Security**
   - Signed npm packages
   - Reproducible builds
   - Supply chain verification

## Rollback Strategy

1. **Version Pinning**
   ```json
   // Consumer apps can pin version
   {
     "dependencies": {
       "@leadfactory/ui-core": "1.0.0"
     }
   }
   ```

2. **Legacy Support**
   - Maintain v0 branch for emergency fixes
   - Clear migration guide
   - Compatibility layer available

3. **Feature Flags**
   ```typescript
   // Enable gradual adoption
   import { enableNewComponents } from '@leadfactory/ui-core/flags';
   ```

## Success Metrics

1. **Package Metrics**
   - Bundle size < 50KB gzipped
   - Tree-shaking efficiency > 90%
   - Zero runtime errors in production

2. **Developer Metrics**
   - Adoption rate > 80% in 3 months
   - Component reuse > 90%
   - Development velocity increased 2x

3. **Quality Metrics**
   - Accessibility score 98+
   - Visual consistency 100%
   - Zero hardcoded values

## Timeline

- **Week 1**: Package setup and token processing
- **Week 2**: Core components (Button, Card, Badge, Table)
- **Week 3**: Advanced components (Modal, Stepper, Input, Dropdown)
- **Week 4**: Documentation, testing, and publishing

## Long-term Maintenance

1. **Regular Updates**
   - Weekly dependency updates
   - Monthly accessibility audits
   - Quarterly design reviews

2. **Version Strategy**
   - Semantic versioning
   - Deprecation notices
   - Migration tooling

3. **Community**
   - Component request process
   - Contribution guidelines
   - Design system council