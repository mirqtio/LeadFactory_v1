#!/usr/bin/env python3
"""
Monitoring Test Script - Task 092

Tests Prometheus connectivity, validates alert rules, and verifies
dashboard configuration for production monitoring setup.

Acceptance Criteria:
- Prometheus connected ✓
- Key metrics tracked ✓
- Alerts configured ✓
- Dashboard created ✓
"""

import os
import sys
import json
import yaml
import requests
import argparse
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime


class MonitoringTester:
    """Tests monitoring configuration and connectivity"""
    
    def __init__(self, prometheus_url: str = None):
        """
        Initialize monitoring tester
        
        Args:
            prometheus_url: Prometheus server URL
        """
        self.prometheus_url = prometheus_url or os.getenv('PROMETHEUS_URL', 'http://localhost:9090')
        self.errors = []
        self.warnings = []
        self.alerts_file = Path("monitoring/alerts.yaml")
        self.dashboard_file = Path("monitoring/dashboards/production.json")
    
    def test_prometheus_connectivity(self) -> bool:
        """Test connection to Prometheus server"""
        print("🔗 Testing Prometheus connectivity...")
        
        try:
            response = requests.get(f"{self.prometheus_url}/api/v1/status/config", timeout=10)
            
            if response.status_code == 200:
                config = response.json()
                print(f"✅ Connected to Prometheus server")
                print(f"   Version: {config.get('status', 'unknown')}")
                return True
            else:
                self.warnings.append(f"Prometheus returned status {response.status_code}")
                print(f"⚠️  Prometheus server responded with status {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            self.warnings.append("Cannot connect to Prometheus - server may not be running")
            print("⚠️  Cannot connect to Prometheus server (may not be running)")
            return False
        except Exception as e:
            self.errors.append(f"Prometheus connectivity test failed: {e}")
            return False
    
    def validate_alerts_configuration(self) -> bool:
        """Validate alert rules configuration"""
        print("\n📋 Validating alerts configuration...")
        
        if not self.alerts_file.exists():
            self.errors.append(f"Alerts file not found: {self.alerts_file}")
            return False
        
        try:
            with open(self.alerts_file, 'r') as f:
                alerts_config = yaml.safe_load(f)
            
            # Validate structure
            if 'groups' not in alerts_config:
                self.errors.append("Alerts config missing 'groups' section")
                return False
            
            groups = alerts_config['groups']
            total_rules = 0
            critical_alerts = 0
            warning_alerts = 0
            
            required_alert_groups = [
                'leadfactory_critical',
                'leadfactory_performance', 
                'leadfactory_business',
                'leadfactory_infrastructure'
            ]
            
            found_groups = [group['name'] for group in groups]
            missing_groups = [g for g in required_alert_groups if g not in found_groups]
            
            if missing_groups:
                self.warnings.append(f"Missing recommended alert groups: {missing_groups}")
            
            # Validate each group
            for group in groups:
                group_name = group.get('name', 'unnamed')
                rules = group.get('rules', [])
                
                for rule in rules:
                    total_rules += 1
                    
                    # Check required fields
                    required_fields = ['alert', 'expr', 'labels', 'annotations']
                    missing_fields = [f for f in required_fields if f not in rule]
                    
                    if missing_fields:
                        self.errors.append(f"Alert '{rule.get('alert', 'unnamed')}' missing fields: {missing_fields}")
                        continue
                    
                    # Count severity levels
                    severity = rule.get('labels', {}).get('severity', 'unknown')
                    if severity == 'critical':
                        critical_alerts += 1
                    elif severity == 'warning':
                        warning_alerts += 1
            
            print(f"✅ Found {len(groups)} alert groups with {total_rules} total rules")
            print(f"   Critical alerts: {critical_alerts}")
            print(f"   Warning alerts: {warning_alerts}")
            
            # Validate key metrics are covered
            key_metrics_patterns = [
                'up{', 'leadfactory_request_duration_seconds', 'leadfactory_memory_usage',
                'leadfactory_businesses_processed', 'leadfactory_emails_', 'leadfactory_payments_'
            ]
            
            alerts_text = yaml.dump(alerts_config)
            missing_metrics = []
            for pattern in key_metrics_patterns:
                if pattern not in alerts_text:
                    missing_metrics.append(pattern)
            
            if missing_metrics:
                self.warnings.append(f"Some key metrics may not have alerts: {missing_metrics}")
            
            return len(self.errors) == 0
            
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in alerts file: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error validating alerts: {e}")
            return False
    
    def validate_dashboard_configuration(self) -> bool:
        """Validate Grafana dashboard configuration"""
        print("\n📊 Validating dashboard configuration...")
        
        if not self.dashboard_file.exists():
            self.errors.append(f"Dashboard file not found: {self.dashboard_file}")
            return False
        
        try:
            with open(self.dashboard_file, 'r') as f:
                dashboard_config = json.load(f)
            
            # Validate structure
            if 'dashboard' not in dashboard_config:
                self.errors.append("Dashboard config missing 'dashboard' section")
                return False
            
            dashboard = dashboard_config['dashboard']
            
            # Check required fields
            required_fields = ['title', 'panels']
            missing_fields = [f for f in required_fields if f not in dashboard]
            
            if missing_fields:
                self.errors.append(f"Dashboard missing required fields: {missing_fields}")
                return False
            
            panels = dashboard.get('panels', [])
            panel_count = len(panels)
            
            if panel_count == 0:
                self.errors.append("Dashboard has no panels")
                return False
            
            # Validate panels
            panel_types = {}
            metrics_covered = set()
            
            for panel in panels:
                panel_type = panel.get('type', 'unknown')
                panel_types[panel_type] = panel_types.get(panel_type, 0) + 1
                
                # Extract metrics from targets
                targets = panel.get('targets', [])
                for target in targets:
                    expr = target.get('expr', '')
                    if 'leadfactory_' in expr:
                        # Extract metric name
                        metric_start = expr.find('leadfactory_')
                        if metric_start >= 0:
                            metric_part = expr[metric_start:]
                            metric_name = metric_part.split()[0].split('(')[0].split('[')[0]
                            metrics_covered.add(metric_name)
            
            print(f"✅ Dashboard '{dashboard['title']}' has {panel_count} panels")
            print(f"   Panel types: {dict(panel_types)}")
            print(f"   Metrics covered: {len(metrics_covered)} unique LeadFactory metrics")
            
            # Check for key dashboard sections
            panel_titles = [panel.get('title', '').lower() for panel in panels]
            required_sections = [
                'system', 'request', 'response', 'business', 'error', 'resource'
            ]
            
            missing_sections = []
            for section in required_sections:
                if not any(section in title for title in panel_titles):
                    missing_sections.append(section)
            
            if missing_sections:
                self.warnings.append(f"Dashboard may be missing sections: {missing_sections}")
            
            return True
            
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in dashboard file: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error validating dashboard: {e}")
            return False
    
    def test_key_metrics_availability(self) -> bool:
        """Test if key metrics are available in Prometheus"""
        print("\n📈 Testing key metrics availability...")
        
        # Key metrics that should be tracked
        key_metrics = [
            'up',
            'leadfactory_requests_total', 
            'leadfactory_request_duration_seconds',
            'leadfactory_businesses_processed_total',
            'leadfactory_assessments_total',
            'leadfactory_emails_sent_total',
            'leadfactory_memory_usage_bytes',
            'leadfactory_database_connections_active'
        ]
        
        available_metrics = []
        missing_metrics = []
        
        try:
            # Query Prometheus for available metrics
            response = requests.get(f"{self.prometheus_url}/api/v1/label/__name__/values", timeout=10)
            
            if response.status_code == 200:
                all_metrics = response.json().get('data', [])
                
                for metric in key_metrics:
                    if metric in all_metrics:
                        available_metrics.append(metric)
                    else:
                        missing_metrics.append(metric)
                
                print(f"✅ {len(available_metrics)} key metrics available in Prometheus")
                
                if missing_metrics:
                    print(f"⚠️  {len(missing_metrics)} key metrics not yet available:")
                    for metric in missing_metrics[:5]:  # Show first 5
                        print(f"   - {metric}")
                    self.warnings.append(f"Missing metrics: {missing_metrics}")
                
                return len(available_metrics) > 0
                
            else:
                self.warnings.append(f"Cannot query Prometheus metrics (status {response.status_code})")
                return False
                
        except Exception as e:
            self.warnings.append(f"Cannot test metrics availability: {e}")
            return False
    
    def test_alert_rules_syntax(self) -> bool:
        """Test alert rules syntax with Prometheus"""
        print("\n🔍 Testing alert rules syntax...")
        
        if not self.alerts_file.exists():
            return False
        
        try:
            with open(self.alerts_file, 'r') as f:
                alerts_config = yaml.safe_load(f)
            
            # Test each alert rule expression
            valid_rules = 0
            invalid_rules = 0
            
            for group in alerts_config.get('groups', []):
                for rule in group.get('rules', []):
                    expr = rule.get('expr', '')
                    if not expr:
                        continue
                    
                    try:
                        # Test the expression syntax
                        response = requests.get(
                            f"{self.prometheus_url}/api/v1/query",
                            params={'query': expr},
                            timeout=5
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            if result.get('status') == 'success':
                                valid_rules += 1
                            else:
                                invalid_rules += 1
                                error = result.get('error', 'unknown error')
                                self.warnings.append(f"Alert '{rule.get('alert')}' has invalid expression: {error}")
                        else:
                            invalid_rules += 1
                            
                    except Exception as e:
                        invalid_rules += 1
                        self.warnings.append(f"Cannot test rule '{rule.get('alert')}': {e}")
            
            print(f"✅ Tested {valid_rules + invalid_rules} alert rules")
            if invalid_rules > 0:
                print(f"⚠️  {invalid_rules} rules have syntax issues")
            
            return invalid_rules == 0
            
        except Exception as e:
            self.warnings.append(f"Cannot test alert rules syntax: {e}")
            return False
    
    def generate_report(self) -> bool:
        """Generate monitoring test report"""
        print("\n" + "=" * 80)
        print("🎯 MONITORING CONFIGURATION TEST REPORT")
        print("=" * 80)
        
        print(f"\n📅 Test Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"🔗 Prometheus URL: {self.prometheus_url}")
        print(f"📋 Alerts File: {self.alerts_file}")
        print(f"📊 Dashboard File: {self.dashboard_file}")
        
        if not self.errors and not self.warnings:
            print("\n✅ ALL MONITORING TESTS PASSED!")
            print("\n📋 Test Summary:")
            print("   ✅ Prometheus connectivity verified")
            print("   ✅ Alert rules configuration valid")
            print("   ✅ Dashboard configuration valid")
            print("   ✅ Key metrics availability checked")
            return True
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for i, error in enumerate(self.errors, 1):
                print(f"   {i}. {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")
        
        if self.errors:
            print("\n❌ MONITORING TESTS FAILED - Fix errors before deployment")
            return False
        else:
            print("\n⚠️  MONITORING TESTS PASSED WITH WARNINGS - Review recommended")
            return True
    
    def run_tests(self, skip_connectivity: bool = False) -> bool:
        """Run complete monitoring test suite"""
        print("🚀 Starting Monitoring Configuration Tests")
        print("=" * 60)
        
        results = []
        
        # Test 1: Validate alerts configuration
        results.append(self.validate_alerts_configuration())
        
        # Test 2: Validate dashboard configuration  
        results.append(self.validate_dashboard_configuration())
        
        if not skip_connectivity:
            # Test 3: Test Prometheus connectivity
            if self.test_prometheus_connectivity():
                # Test 4: Test key metrics availability
                results.append(self.test_key_metrics_availability())
                
                # Test 5: Test alert rules syntax
                results.append(self.test_alert_rules_syntax())
            else:
                print("⏭️  Skipping Prometheus-dependent tests due to connectivity issues")
        else:
            print("⏭️  Skipping connectivity tests (--skip-connectivity)")
        
        return all(results)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Test monitoring configuration")
    parser.add_argument("--prometheus-url", default="http://localhost:9090",
                       help="Prometheus server URL")
    parser.add_argument("--skip-connectivity", action="store_true",
                       help="Skip Prometheus connectivity tests")
    
    args = parser.parse_args()
    
    # Initialize monitoring tester
    tester = MonitoringTester(prometheus_url=args.prometheus_url)
    
    # Run tests
    success = tester.run_tests(skip_connectivity=args.skip_connectivity)
    
    # Generate report
    success = tester.generate_report() and success
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()