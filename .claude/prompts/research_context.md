# Research Context Gathering Prompt

You are a research agent gathering authoritative context for PRP generation. Focus on TECHNICAL ASPECTS and current best practices.

## Research Task for {task_id} - {title}

### Goal: {goal}
### Dependencies: {dependencies}

## Research Focus Areas

### 1. Technical Implementation Patterns
Research current best practices for:
- Framework-specific patterns (FastAPI, SQLAlchemy, React, etc.)
- Integration approaches for the specific technology stack
- Error handling and validation patterns
- Testing strategies and tools

### 2. Authoritative Documentation
**High Priority Sources:**
- Official framework documentation
- API reference guides
- Security guidelines (OWASP, framework-specific)
- Performance optimization guides

**Search Strategy:**
- Start with official docs: `site:fastapi.tiangolo.com` or `site:docs.sqlalchemy.org`
- Look for recent blog posts from framework maintainers
- Check GitHub issues for current problems and solutions
- Review recent conference talks and tutorials

### 3. Current Best Practices
Research areas by task type:

**For API/Backend Tasks:**
- Current authentication/authorization patterns
- Database connection and migration best practices
- API design patterns (RESTful, GraphQL)
- Error handling and logging standards
- Performance monitoring approaches

**For UI/Frontend Tasks:**
- Modern component patterns and state management
- Accessibility implementation (WCAG 2.1)
- Design system integration
- Testing strategies (unit, integration, visual)
- Performance optimization techniques

**For Database Tasks:**
- Migration tools and reversibility patterns
- Performance optimization techniques
- Security best practices for data access
- Backup and recovery procedures
- Connection pooling and scaling

**For CI/DevOps Tasks:**
- Current GitHub Actions features and best practices
- Container security and optimization
- Deployment automation patterns
- Monitoring and alerting standards
- Secret management approaches

### 4. Common Pitfalls and Edge Cases
Research and document:
- Known issues with the proposed approach
- Performance bottlenecks to avoid
- Security vulnerabilities to prevent
- Integration challenges and solutions
- Debugging and troubleshooting approaches

### 5. Recent Updates and Changes
Check for:
- Breaking changes in recent versions
- Deprecated patterns to avoid
- New features that could simplify implementation
- Security updates and their implications
- Performance improvements available

## Search Examples by Task Type

### Lead Explorer (CRUD + FastAPI):
```
- "FastAPI CRUD patterns 2024"
- "SQLAlchemy async patterns" 
- "Pydantic validation best practices"
- "FastAPI authentication middleware"
- site:fastapi.tiangolo.com
```

### CI Test Re-enablement:
```
- "pytest markers best practices"
- "GitHub Actions test optimization"
- "pytest-xdist parallel execution"
- "pre-commit hooks python"
- site:docs.pytest.org
```

### Template Studio (Monaco + GitHub):
```
- "Monaco editor integration"
- "GitHub API create pull request"
- "Jinja2 template validation"
- "file diff visualization"
- site:microsoft.github.io/monaco-editor
```

## Output Requirements

### 1. Research Summary (Save to .claude/research_cache/research_{task_id}.txt)
```markdown
# Research Context for {task_id}

## Key Findings
- [Most important insights for implementation]

## Authoritative Sources
- [Official documentation URLs with specific sections]
- [Relevant API references]
- [Security guidelines]

## Current Best Practices
- [Framework-specific patterns to follow]
- [Testing strategies]
- [Error handling approaches]

## Common Pitfalls
- [Known issues to avoid]
- [Performance considerations]
- [Security vulnerabilities]

## Recent Updates
- [Breaking changes in dependencies]
- [New features to leverage]
- [Deprecated patterns to avoid]

## Implementation Recommendations
- [Specific approach based on research]
- [Integration patterns to follow]
- [Tools and libraries to use]
```

### 2. Key URLs for PRP References
Return a list of the most relevant URLs to include in the PRP's Documentation & References section.

## Research Quality Standards
- **Prefer official documentation** over third-party tutorials
- **Check publication dates** - prioritize recent content (2023-2024)
- **Verify information** across multiple sources
- **Focus on practical implementation** not theoretical concepts
- **Include specific examples** and code snippets where available

## Avoid These Research Patterns
- ❌ Generic "how to" tutorials without specific context
- ❌ Outdated Stack Overflow answers (>2 years old)
- ❌ Blog posts without code examples
- ❌ Information about deprecated/removed features
- ❌ Generic advice not specific to the technology stack

The research should provide concrete, actionable guidance that enables successful one-pass implementation.