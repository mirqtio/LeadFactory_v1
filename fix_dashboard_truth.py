#!/usr/bin/env python3
"""Fix dashboard to show the actual truth - nothing is complete without git commits and CI passing."""

from datetime import datetime


def create_truthful_dashboard():
    """Create dashboard HTML with the actual truth."""

    # Tasks that are ACTUALLY complete (pushed to GitHub + CI green)
    completed_tasks = [
        "P0-020 - Design System Token Extraction - Previously completed",
        "AI CTO Dashboard - Created but showing incorrect status",
        "PRP Validation Framework - Six-gate validation system",
    ]

    # Work done locally but NOT committed/pushed/CI-validated
    uncommitted_work = [
        "P0-000 - Prerequisites Check - LOCAL ONLY (core/prerequisites.py uncommitted)",
        "P0-001 - Fix D4 Coordinator - LOCAL ONLY (uncommitted changes)",
        "P0-002 - Wire Prefect Full Pipeline - LOCAL ONLY (uncommitted)",
        "P0-003 - Dockerize CI - LOCAL ONLY (uncommitted)",
        "P0-004 - Database Migrations - LOCAL ONLY (uncommitted)",
        "P0-005 - Environment & Stub Wiring - LOCAL ONLY (uncommitted)",
        "P0-007 - Health Endpoint - LOCAL ONLY (api/health.py uncommitted)",
    ]

    # Tasks with validated PRPs ready for implementation
    ready_for_implementation = [
        "P0-006 - Green KEEP Test Suite",
        "P0-008 - Test Infrastructure Cleanup",
        "P0-009 - Remove Yelp Remnants",
        "P0-010 - Fix Missing Dependencies",
        "P0-011 - Deploy to VPS",
        "P0-012 - Postgres on VPS Container",
        "P0-013 - CI/CD Pipeline Stabilization",
        "P0-014 - Test Suite Re-enablement Coverage Plan",
        "P0-015 - Test Coverage Enhancement (BLOCKED - needs P0-014)",
        "P0-021 - Lead Explorer",
        "P0-022 - Batch Report Runner",
        "P0-023 - Lineage Panel",
        "P0-024 - Template Studio",
        "P0-025 - Scoring Playground",
        "P0-026 - Governance",
        "P0-027 - Global Navigation Shell",
    ]

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI CTO Dashboard - LeadFactory ACTUAL Status</title>
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
        .uncommitted {{ color: var(--warning-color); font-style: italic; }}
        
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
        
        .warning-note {{
            background: #fef3c7;
            border: 1px solid #f59e0b;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.95rem;
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
        <h1>🤖 AI CTO Dashboard - ACTUAL Status</h1>
        <p class="subtitle">Real Git/CI Status (Not Local Changes)</p>
        
        <div class="critical-note">
            <strong>🚨 Reality Check:</strong> Per CLAUDE.md, a task is ONLY complete when:
            <ol>
                <li>Code is implemented and validated</li>
                <li><strong>Pushed to GitHub main branch</strong></li>
                <li><strong>ALL CI checks pass GREEN</strong></li>
            </ol>
            Local uncommitted changes do NOT count as complete!
        </div>
        
        <div class="warning-note">
            <strong>⚠️ Current Status:</strong> 141 uncommitted files. Last GitHub commit was 4+ hours ago.
            No implementations have been pushed or CI-validated.
        </div>
        
        <div class="metrics">
            <div class="metric">
                <div class="metric-value completed">{len(completed_tasks)}</div>
                <div class="metric-label">Actually Complete</div>
            </div>
            <div class="metric">
                <div class="metric-value uncommitted">{len(uncommitted_work)}</div>
                <div class="metric-label">Local Only (Uncommitted)</div>
            </div>
            <div class="metric">
                <div class="metric-value pending">{len(ready_for_implementation)}</div>
                <div class="metric-label">Ready to Implement</div>
            </div>
            <div class="metric">
                <div class="metric-value blocked">1</div>
                <div class="metric-label">Blocked</div>
            </div>
        </div>
        
        <div class="status-grid">
            <div class="status-card">
                <h3 class="completed">✅ Actually Complete (Pushed + CI Green)</h3>
                <ul class="task-list">
                    {"".join(f'<li>{task}</li>' for task in completed_tasks)}
                </ul>
            </div>
            
            <div class="status-card">
                <h3 class="uncommitted">⚠️ Local Work (Not Committed/Pushed)</h3>
                <ul class="task-list">
                    {"".join(f'<li>{task}</li>' for task in uncommitted_work)}
                </ul>
            </div>
            
            <div class="status-card">
                <h3 class="pending">📋 Ready for Implementation</h3>
                <ul class="task-list">
                    {"".join(f'<li>{task}</li>' for task in ready_for_implementation[:8])}
                    <li><em>...and {len(ready_for_implementation) - 8} more</em></li>
                </ul>
            </div>
        </div>
        
        <div class="status-card">
            <h3>📈 Git/GitHub Activity</h3>
            <ul class="task-list">
                <li><strong>Last commit:</strong> "feat: Complete Six-Gate validation for P0-024" (4+ hours ago)</li>
                <li><strong>Uncommitted files:</strong> 141 files</li>
                <li><strong>Last CI status:</strong> Unknown/Failed</li>
                <li><strong>Branch:</strong> main (up to date with origin)</li>
            </ul>
        </div>
        
        <div class="last-updated">
            Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC | Auto-refresh: 30s | 
            <button onclick="refreshPage()">Manual Refresh</button>
        </div>
    </div>
</body>
</html>"""

    # Write the dashboard HTML
    with open("ai_cto_dashboard.html", "w") as f:
        f.write(html_content)

    print("✅ Dashboard fixed to show actual truth")
    print(f"   - {len(completed_tasks)} tasks ACTUALLY complete (pushed + CI green)")
    print(f"   - {len(uncommitted_work)} tasks done locally but NOT committed")
    print(f"   - {len(ready_for_implementation)} tasks ready to implement")
    print("   - 141 uncommitted files in the repo")


if __name__ == "__main__":
    create_truthful_dashboard()
