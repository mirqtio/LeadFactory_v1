# Flaky Test Detection Tools

This directory contains tools for identifying and analyzing flaky tests in the codebase.

## Scripts

### 1. `detect_flaky_tests.py`

Runs tests multiple times to identify tests that fail intermittently.

**Usage:**
```bash
# Run tests 5 times (default)
python scripts/detect_flaky_tests.py

# Run tests 10 times with verbose output
python scripts/detect_flaky_tests.py -n 10 -v

# Focus on specific test pattern
python scripts/detect_flaky_tests.py -f "test_smoke" -n 3

# Custom output file
python scripts/detect_flaky_tests.py -o my_flaky_report.md
```

**Options:**
- `-n, --iterations`: Number of test runs (default: 5)
- `-p, --path`: Test directory path (default: tests/)
- `-f, --filter`: Filter tests by pattern (pytest -k)
- `-v, --verbose`: Show detailed output
- `-o, --output`: Output report filename

**Output:**
- Markdown report with flaky test analysis
- JSON data file for programmatic access
- Exit code 1 if flaky tests found

### 2. `analyze_test_issues.py`

Static analysis of test code to identify patterns that commonly lead to flaky tests.

**Usage:**
```bash
python scripts/analyze_test_issues.py
```

**Detected Issues:**
- **HIGH Priority:**
  - Hardcoded ports (e.g., `port=5432`)
  - Missing cleanup/teardown
  - Race conditions without synchronization

- **MEDIUM Priority:**
  - `time.sleep()` usage
  - Async/await issues
  - Unmocked external dependencies

- **LOW Priority:**
  - Tests marked with `@pytest.mark.xfail`
  - Tests marked with `@pytest.mark.skip`
  - Tests without timeouts

**Output:**
- `test_issues_report.json`: Detailed JSON report
- `test_issues_analysis.md`: Human-readable markdown report

## Common Flaky Test Patterns Found

### 1. Port Conflicts (114 issues)
Tests using hardcoded ports like 5011, 5432, 8000 can fail when:
- Multiple tests run in parallel
- Previous test didn't clean up properly
- System already has service on that port

**Fix:** Use dynamic port allocation or pytest fixtures

### 2. Missing Cleanup (85 issues)
Tests creating resources without proper cleanup:
- Database connections
- Thread/process creation
- Temporary files
- Mock patches

**Fix:** Use pytest fixtures with proper teardown or context managers

### 3. Async Issues (203 issues)
- Missing `@pytest.mark.asyncio` decorators
- Mixing sync and async tests
- Calling `asyncio.run()` in async context

**Fix:** Consistent use of pytest-asyncio

### 4. Time-based Tests (35 issues)
Tests using `time.sleep()` are inherently flaky due to:
- System load variations
- CI environment differences
- Race conditions

**Fix:** Use proper wait conditions or mock time

## Recommendations

1. **Immediate Actions:**
   - Fix all HIGH priority issues (ports, cleanup)
   - Add `@pytest.mark.asyncio` to all async tests
   - Replace hardcoded ports with dynamic allocation

2. **Short-term Improvements:**
   - Replace `time.sleep()` with proper synchronization
   - Mock all external service calls
   - Add timeouts to prevent hanging tests

3. **Long-term Strategy:**
   - Implement test isolation fixtures
   - Use pytest-xdist with proper scope
   - Regular flaky test detection in CI

## CI Integration

To integrate flaky test detection in CI:

```yaml
# Run flaky test detection
- name: Detect Flaky Tests
  run: |
    python scripts/detect_flaky_tests.py -n 3 -o flaky_report.md
  continue-on-error: true
  
# Upload reports
- name: Upload Test Reports
  uses: actions/upload-artifact@v3
  with:
    name: test-reports
    path: |
      flaky_*.md
      flaky_*.json
      test_issues_*.md
      test_issues_*.json
```

## Next Steps

1. Fix HIGH priority issues first (ports and cleanup)
2. Add proper test fixtures for resource management
3. Implement dynamic port allocation utility
4. Create shared test utilities for common patterns
5. Add flaky test detection to PR checks