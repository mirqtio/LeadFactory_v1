#!/usr/bin/env python3
"""Update dashboard with actual CI status - tasks are NOT complete if CI is failing."""

from datetime import datetime


def create_ci_aware_dashboard():
    """Create dashboard showing real CI status."""

    # ZERO tasks are actually complete - CI is FAILING

    # Tasks that are committed/pushed but CI is FAILING
    committed_but_ci_failing = [
        "P0-000 - Prerequisites Check - ❌ Unit Tests FAILING",
        "P0-001 - Fix D4 Coordinator - ⚠️ Integration Tests Skipped",
        "P0-002 - Wire Prefect Full Pipeline - ❌ Latest CI FAILING",
        "P0-003 - Dockerize CI - ❌ Latest CI FAILING",
        "P0-004 - Database Migrations - ❌ Latest CI FAILING",
        "P0-005 - Environment & Stub Wiring - ❌ Latest CI FAILING",
        "P0-007 - Health Endpoint - ❌ Latest CI FAILING",
        "P0-024 - Template Studio - ✅ Previously committed",
    ]

    # Uncommitted local work
    uncommitted_work = ["AI CTO Dashboard updates", "Various test fixes", "89 uncommitted files total"]

    # Tasks ready for implementation
    ready_for_implementation = [
        "P0-006 - Green KEEP Test Suite",
        "P0-008 - Test Infrastructure Cleanup",
        "P0-009 - Remove Yelp Remnants",
        "P0-010 - Fix Missing Dependencies",
        "P0-011 - Deploy to VPS",
        "P0-012 - Postgres on VPS Container",
        "P0-013 - CI/CD Pipeline Stabilization",
        "P0-014 - Test Suite Re-enablement",
        "P0-015 - Test Coverage Enhancement (BLOCKED)",
        "P0-021 - Lead Explorer",
        "P0-022 - Batch Report Runner",
        "P0-023 - Lineage Panel",
        "P0-025 - Scoring Playground",
        "P0-026 - Governance",
        "P0-027 - Global Navigation Shell",
    ]

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI CTO Dashboard - CI Reality Check</title>
    <style>
        :root {{
            --primary-color: #2563eb;
            --success-color: #16a34a;
            --warning-color: #d97706;
            --danger-color: #dc2626;
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --bg-primary: #ffffff;
            --bg-secondary: #f3f4f6;
            --border-color: #e5e7eb;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-secondary);
            color: var(--text-primary);
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            color: var(--primary-color);
        }}
        
        .subtitle {{
            color: var(--text-secondary);
            margin-bottom: 30px;
            font-size: 1.1rem;
        }}
        
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric {{
            background: var(--bg-primary);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            text-align: center;
        }}
        
        .metric-value {{
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .metric-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .status-card {{
            background: var(--bg-primary);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }}
        
        .status-card h3 {{
            margin-bottom: 15px;
            font-size: 1.2rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .task-list {{
            list-style: none;
        }}
        
        .task-list li {{
            padding: 8px 0;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.95rem;
        }}
        
        .task-list li:last-child {{
            border-bottom: none;
        }}
        
        .completed {{ color: var(--success-color); }}
        .in-progress {{ color: var(--warning-color); }}
        .blocked {{ color: var(--danger-color); }}
        .pending {{ color: var(--text-secondary); }}
        .failing {{ color: var(--danger-color); font-weight: bold; }}
        
        .last-updated {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.9rem;
            padding: 20px;
        }}
        
        button {{
            background: var(--primary-color);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
        }}
        
        button:hover {{
            opacity: 0.9;
        }}
        
        .critical-note {{
            background: #fee2e2;
            border: 2px solid #dc2626;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.95rem;
        }}
        
        .ci-status {{
            background: #fef3c7;
            border: 1px solid #f59e0b;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        
        .big-zero {{
            font-size: 5rem;
            color: var(--danger-color);
            text-align: center;
            margin: 20px 0;
            font-weight: bold;
        }}
    </style>
    <script>
        function refreshPage() {{
            location.reload();
        }}
        
        // Auto-refresh every 30 seconds
        setInterval(refreshPage, 30000);
    </script>
</head>
<body>
    <div class="container">
        <h1>🤖 AI CTO Dashboard - CI Reality Check</h1>
        <p class="subtitle">Actual Task Completion Status Based on CI Results</p>
        
        <div class="critical-note">
            <strong>🚨 CRITICAL:</strong> Per CLAUDE.md, tasks are ONLY complete when:
            <ol>
                <li>Code is implemented ✅</li>
                <li>Pushed to GitHub ✅</li>
                <li><strong>ALL CI checks pass GREEN ❌</strong></li>
            </ol>
            <strong>Current Status: CI IS FAILING - NO TASKS ARE COMPLETE!</strong>
        </div>
        
        <div class="ci-status">
            <h3>🔴 CI Status Summary</h3>
            <ul>
                <li><strong>P0-000:</strong> Unit Tests FAILING</li>
                <li><strong>Latest commit:</strong> Tests FAILING</li>
                <li><strong>Overall:</strong> Multiple CI checks not passing</li>
            </ul>
        </div>
        
        <div class="big-zero">0</div>
        <p style="text-align: center; font-size: 1.2rem; margin-bottom: 30px;">
            Tasks Actually Complete (with CI passing)
        </p>
        
        <div class="metrics">
            <div class="metric">
                <div class="metric-value completed">0</div>
                <div class="metric-label">Complete (CI Green)</div>
            </div>
            <div class="metric">
                <div class="metric-value failing">{len(committed_but_ci_failing)}</div>
                <div class="metric-label">Pushed but CI Failing</div>
            </div>
            <div class="metric">
                <div class="metric-value in-progress">89</div>
                <div class="metric-label">Uncommitted Files</div>
            </div>
            <div class="metric">
                <div class="metric-value pending">{len(ready_for_implementation)}</div>
                <div class="metric-label">Ready to Implement</div>
            </div>
        </div>
        
        <div class="status-grid">
            <div class="status-card">
                <h3 class="failing">❌ Pushed but CI Failing</h3>
                <ul class="task-list">
                    {"".join(f'<li>{task}</li>' for task in committed_but_ci_failing)}
                </ul>
            </div>
            
            <div class="status-card">
                <h3 class="in-progress">📝 Uncommitted Local Work</h3>
                <ul class="task-list">
                    {"".join(f'<li>{task}</li>' for task in uncommitted_work)}
                </ul>
            </div>
            
            <div class="status-card">
                <h3 class="pending">📋 Ready for Implementation</h3>
                <ul class="task-list">
                    {"".join(f'<li>{task}</li>' for task in ready_for_implementation[:7])}
                    <li><em>...and {len(ready_for_implementation) - 7} more</em></li>
                </ul>
            </div>
        </div>
        
        <div class="status-card">
            <h3>🔧 Required Actions</h3>
            <ul class="task-list">
                <li><strong>1.</strong> Fix failing unit tests in P0-000</li>
                <li><strong>2.</strong> Fix all failing tests in latest commit</li>
                <li><strong>3.</strong> Ensure ALL CI checks pass (not just some)</li>
                <li><strong>4.</strong> Only then can tasks be marked complete</li>
            </ul>
        </div>
        
        <div class="last-updated">
            Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC | Auto-refresh: 30s | 
            <button onclick="refreshPage()">Manual Refresh</button>
        </div>
    </div>
</body>
</html>"""

    with open("ai_cto_dashboard.html", "w") as f:
        f.write(html_content)

    print("✅ Dashboard updated with CI reality")
    print("   - 0 tasks actually complete (CI is failing)")
    print("   - 8 tasks pushed but CI failing")
    print("   - 89 uncommitted files")
    print("   - P0-000 has failing unit tests")
    print("   - Latest commit has failing tests")


if __name__ == "__main__":
    create_ci_aware_dashboard()
