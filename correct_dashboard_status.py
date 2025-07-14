#!/usr/bin/env python3
"""Correct dashboard to show actual CI status - tests are failing."""

from datetime import datetime


def create_correct_dashboard():
    """Create dashboard showing the actual failing CI status."""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI CTO Dashboard - CI FAILING</title>
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
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-secondary);
            color: var(--text-primary);
            line-height: 1.6;
            margin: 0;
            padding: 0;
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
        
        .big-zero {{
            font-size: 8rem;
            color: var(--danger-color);
            text-align: center;
            margin: 40px 0;
            font-weight: bold;
            line-height: 1;
        }}
        
        .critical-note {{
            background: #fee2e2;
            border: 2px solid #dc2626;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 1.1rem;
        }}
        
        .summary-box {{
            background: var(--bg-primary);
            padding: 30px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            margin: 20px 0;
        }}
        
        .summary-box h2 {{
            color: var(--primary-color);
            margin-bottom: 20px;
        }}
        
        .status-list {{
            list-style: none;
            padding: 0;
        }}
        
        .status-list li {{
            padding: 10px 0;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .status-list li:last-child {{
            border-bottom: none;
        }}
        
        .failing {{
            color: var(--danger-color);
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 AI CTO Dashboard - CORRECT STATUS</h1>
        
        <div class="critical-note">
            <strong>🚨 CORRECTION:</strong> Upon checking actual CI logs, <strong>TESTS ARE FAILING!</strong><br><br>
            Error: <code>Failed: Stub server failed to start at http://stub-server:5010</code><br><br>
            Per CLAUDE.md: Tasks are ONLY complete when ALL CI checks pass GREEN.<br>
            <strong>Current Status: CI IS FAILING - NO TASKS ARE COMPLETE!</strong>
        </div>
        
        <div class="big-zero">0</div>
        <p style="text-align: center; font-size: 1.5rem; margin-bottom: 40px;">
            Tasks Actually Complete (CI Must Be Green)
        </p>
        
        <div class="summary-box">
            <h2>🔍 Actual CI Status Investigation</h2>
            <ul class="status-list">
                <li><strong>Local Test Run:</strong> <span class="failing">❌ ERROR - Stub server failed to start</span></li>
                <li><strong>Error Message:</strong> <code>Failed: Stub server failed to start at http://stub-server:5010</code></li>
                <li><strong>Root Cause:</strong> conftest.py stub server configuration issue</li>
                <li><strong>Impact:</strong> ALL tests fail at setup before running</li>
                <li><strong>GitHub CI:</strong> Also failing (misleading status display)</li>
            </ul>
        </div>
        
        <div class="summary-box">
            <h2>📋 Work Done (But Not Complete)</h2>
            <ul class="status-list">
                <li>✅ Code implementations pushed to GitHub</li>
                <li>❌ Tests failing due to stub server setup</li>
                <li>❌ CI not actually green despite initial appearances</li>
                <li>❌ CLAUDE.md criteria NOT met</li>
            </ul>
        </div>
        
        <div class="summary-box">
            <h2>🔧 Immediate Actions Required</h2>
            <ul class="status-list">
                <li><strong>1.</strong> Fix stub server configuration in tests/conftest.py</li>
                <li><strong>2.</strong> Ensure stub server starts properly for all test environments</li>
                <li><strong>3.</strong> Verify all tests pass locally</li>
                <li><strong>4.</strong> Push fixes and verify CI is actually green</li>
                <li><strong>5.</strong> Only then can tasks be marked complete</li>
            </ul>
        </div>
        
        <div style="text-align: center; margin-top: 40px; color: var(--text-secondary);">
            Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC<br>
            <strong>TRUTH: CI must actually pass, not just appear to pass</strong>
        </div>
    </div>
</body>
</html>"""

    with open('ai_cto_dashboard.html', 'w') as f:
        f.write(html_content)

    print("✅ Dashboard corrected to show actual failing CI status")
    print("   - 0 tasks complete (CI is actually failing)")
    print("   - Stub server configuration issue blocking all tests")
    print("   - Must fix before any tasks can be marked complete")


if __name__ == "__main__":
    create_correct_dashboard()
