#!/usr/bin/env python3
"""
Health Check Script - Task 093

Comprehensive health checking for LeadFactory application and infrastructure
components in production deployment.

Acceptance Criteria:
- All services running ✓
- Health checks pass ✓
- Logs accessible ✓
- Restart policy set ✓
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

import psycopg2
import redis
import requests


class HealthChecker:
    """Comprehensive health checking for LeadFactory"""

    def __init__(self, config: dict[str, Any] = None):
        """
        Initialize health checker

        Args:
            config: Configuration dictionary with service endpoints
        """
        self.config = config or {
            "api_endpoint": os.getenv("API_ENDPOINT", "http://localhost:8000"),
            "prometheus_endpoint": os.getenv("PROMETHEUS_ENDPOINT", "http://localhost:9091"),
            "grafana_endpoint": os.getenv("GRAFANA_ENDPOINT", "http://localhost:3001"),
            "database_url": os.getenv(
                "DATABASE_URL",
                "postgresql://leadfactory:password@localhost:5432/leadfactory",
            ),
            "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            "timeout": int(os.getenv("HEALTH_CHECK_TIMEOUT", "10")),
        }

        self.results = {}
        self.errors = []
        self.warnings = []

    def check_api_health(self) -> bool:
        """Check LeadFactory API health"""
        service = "leadfactory-api"
        print(f"🔗 Checking {service}...")

        try:
            endpoint = f"{self.config['api_endpoint']}/health"
            response = requests.get(endpoint, timeout=self.config["timeout"])

            if response.status_code == 200:
                data = response.json()
                self.results[service] = {
                    "status": "healthy",
                    "response_time": response.elapsed.total_seconds(),
                    "details": data,
                }
                print(f"✅ {service} is healthy (response time: {response.elapsed.total_seconds():.3f}s)")
                return True
            self.results[service] = {
                "status": "unhealthy",
                "error": f"HTTP {response.status_code}",
            }
            self.errors.append(f"{service} returned HTTP {response.status_code}")
            return False

        except requests.exceptions.ConnectionError:
            self.results[service] = {
                "status": "unreachable",
                "error": "Connection refused",
            }
            self.errors.append(f"{service} is unreachable")
            return False
        except requests.exceptions.Timeout:
            self.results[service] = {
                "status": "timeout",
                "error": f"Timeout after {self.config['timeout']}s",
            }
            self.errors.append(f"{service} health check timed out")
            return False
        except Exception as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"{service} health check failed: {e}")
            return False

    def check_database_health(self) -> bool:
        """Check PostgreSQL database health"""
        service = "postgres"
        print(f"🗄️  Checking {service}...")

        try:
            start_time = time.time()
            conn = psycopg2.connect(self.config["database_url"])

            # Test basic query
            cursor = conn.cursor()
            cursor.execute("SELECT version(), now(), current_database()")
            result = cursor.fetchone()

            # Check if alembic_version table exists (migrations applied)
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'alembic_version'
                )
            """
            )
            migrations_applied = cursor.fetchone()[0]

            # Get connection stats
            cursor.execute(
                """
                SELECT count(*) as total_connections,
                       count(*) FILTER (WHERE state = 'active') as active_connections
                FROM pg_stat_activity 
                WHERE datname = current_database()
            """
            )
            conn_stats = cursor.fetchone()

            cursor.close()
            conn.close()

            response_time = time.time() - start_time

            self.results[service] = {
                "status": "healthy",
                "response_time": response_time,
                "details": {
                    "version": result[0].split()[1],
                    "current_time": result[1].isoformat(),
                    "database": result[2],
                    "migrations_applied": migrations_applied,
                    "total_connections": conn_stats[0],
                    "active_connections": conn_stats[1],
                },
            }

            print(f"✅ {service} is healthy (response time: {response_time:.3f}s)")
            print(f"   Database: {result[2]}, Version: {result[0].split()[1]}")
            print(f"   Connections: {conn_stats[1]} active / {conn_stats[0]} total")

            if not migrations_applied:
                self.warnings.append("Database migrations may not be applied")

            return True

        except psycopg2.Error as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"{service} connection failed: {e}")
            return False
        except Exception as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"{service} health check failed: {e}")
            return False

    def check_redis_health(self) -> bool:
        """Check Redis cache health"""
        service = "redis"
        print(f"🔄 Checking {service}...")

        try:
            start_time = time.time()

            # Parse Redis URL
            parsed = urlparse(self.config["redis_url"])
            r = redis.Redis(
                host=parsed.hostname,
                port=parsed.port or 6379,
                db=int(parsed.path[1:]) if parsed.path else 0,
                password=parsed.password,
                socket_timeout=self.config["timeout"],
            )

            # Test connection
            r.ping()

            # Get Redis info
            info = r.info()

            # Test read/write
            test_key = "health_check_test"
            r.set(test_key, "test_value", ex=60)
            test_value = r.get(test_key)
            r.delete(test_key)

            response_time = time.time() - start_time

            self.results[service] = {
                "status": "healthy",
                "response_time": response_time,
                "details": {
                    "version": info.get("redis_version", "unknown"),
                    "uptime_seconds": info.get("uptime_in_seconds", 0),
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory": info.get("used_memory_human", "unknown"),
                    "keyspace": {db: stats for db, stats in info.items() if db.startswith("db")},
                    "read_write_test": test_value == b"test_value",
                },
            }

            print(f"✅ {service} is healthy (response time: {response_time:.3f}s)")
            print(f"   Version: {info.get('redis_version')}, Uptime: {info.get('uptime_in_seconds')}s")
            print(f"   Memory: {info.get('used_memory_human')}, Clients: {info.get('connected_clients')}")

            return True

        except redis.RedisError as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"{service} connection failed: {e}")
            return False
        except Exception as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"{service} health check failed: {e}")
            return False

    def check_prometheus_health(self) -> bool:
        """Check Prometheus monitoring health"""
        service = "prometheus"
        print(f"📊 Checking {service}...")

        try:
            # Check Prometheus health endpoint
            start_time = time.time()
            health_response = requests.get(
                f"{self.config['prometheus_endpoint']}/-/healthy",
                timeout=self.config["timeout"],
            )

            if health_response.status_code != 200:
                self.results[service] = {
                    "status": "unhealthy",
                    "error": f"Health endpoint returned HTTP {health_response.status_code}",
                }
                self.errors.append(f"{service} health endpoint failed")
                return False

            # Check if metrics are being collected
            metrics_response = requests.get(
                f"{self.config['prometheus_endpoint']}/api/v1/query",
                params={"query": "up"},
                timeout=self.config["timeout"],
            )

            response_time = time.time() - start_time

            if metrics_response.status_code == 200:
                metrics_data = metrics_response.json()
                num_targets = len(metrics_data.get("data", {}).get("result", []))

                self.results[service] = {
                    "status": "healthy",
                    "response_time": response_time,
                    "details": {
                        "targets_monitored": num_targets,
                        "metrics_endpoint_accessible": True,
                    },
                }

                print(f"✅ {service} is healthy (response time: {response_time:.3f}s)")
                print(f"   Monitoring {num_targets} targets")
                return True
            self.warnings.append(f"{service} metrics endpoint issues")
            return False

        except requests.exceptions.ConnectionError:
            self.results[service] = {
                "status": "unreachable",
                "error": "Connection refused",
            }
            self.errors.append(f"{service} is unreachable")
            return False
        except Exception as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"{service} health check failed: {e}")
            return False

    def check_grafana_health(self) -> bool:
        """Check Grafana dashboard health"""
        service = "grafana"
        print(f"📈 Checking {service}...")

        try:
            start_time = time.time()
            response = requests.get(
                f"{self.config['grafana_endpoint']}/api/health",
                timeout=self.config["timeout"],
            )

            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()

                self.results[service] = {
                    "status": "healthy",
                    "response_time": response_time,
                    "details": data,
                }

                print(f"✅ {service} is healthy (response time: {response_time:.3f}s)")
                print(f"   Version: {data.get('version', 'unknown')}")
                return True
            self.results[service] = {
                "status": "unhealthy",
                "error": f"HTTP {response.status_code}",
            }
            self.errors.append(f"{service} returned HTTP {response.status_code}")
            return False

        except requests.exceptions.ConnectionError:
            self.results[service] = {
                "status": "unreachable",
                "error": "Connection refused",
            }
            self.warnings.append(f"{service} is unreachable (optional service)")
            return False
        except Exception as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.warnings.append(f"{service} health check failed: {e}")
            return False

    def check_docker_services(self) -> bool:
        """Check Docker services status"""
        service = "docker-services"
        print(f"🐳 Checking {service}...")

        try:
            # Check if docker-compose services are running
            result = subprocess.run(
                [
                    "docker-compose",
                    "-f",
                    "docker-compose.production.yml",
                    "-p",
                    "leadfactory",
                    "ps",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")[2:]  # Skip header
                services_status = {}

                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 4:
                            container_name = parts[0]
                            state = parts[3] if len(parts) > 3 else "unknown"
                            services_status[container_name] = state

                running_services = sum(1 for state in services_status.values() if "Up" in state)
                total_services = len(services_status)

                self.results[service] = {
                    "status": "healthy" if running_services == total_services else "partial",
                    "details": {
                        "running_services": running_services,
                        "total_services": total_services,
                        "services_status": services_status,
                    },
                }

                print(f"✅ {service}: {running_services}/{total_services} services running")
                for container, state in services_status.items():
                    status_icon = "✅" if "Up" in state else "❌"
                    print(f"   {status_icon} {container}: {state}")

                return running_services == total_services

            self.results[service] = {"status": "error", "error": result.stderr}
            self.errors.append(f"Docker services check failed: {result.stderr}")
            return False

        except subprocess.TimeoutExpired:
            self.results[service] = {
                "status": "timeout",
                "error": "Docker command timed out",
            }
            self.errors.append(f"{service} check timed out")
            return False
        except Exception as e:
            self.results[service] = {"status": "error", "error": str(e)}
            self.errors.append(f"{service} check failed: {e}")
            return False

    def generate_report(self) -> dict[str, Any]:
        """Generate comprehensive health report"""
        healthy_services = sum(1 for result in self.results.values() if result.get("status") == "healthy")
        total_services = len(self.results)

        overall_status = "healthy" if healthy_services == total_services and not self.errors else "unhealthy"

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": overall_status,
            "summary": {
                "healthy_services": healthy_services,
                "total_services": total_services,
                "health_percentage": (healthy_services / total_services * 100) if total_services > 0 else 0,
            },
            "services": self.results,
            "errors": self.errors,
            "warnings": self.warnings,
        }

        return report

    def run_all_checks(self, services: list[str] = None) -> bool:
        """Run all health checks"""
        print("🚀 Starting LeadFactory Health Check")
        print("=" * 60)

        all_services = ["api", "database", "redis", "prometheus", "grafana", "docker"]

        services_to_check = services or all_services

        check_methods = {
            "api": self.check_api_health,
            "database": self.check_database_health,
            "redis": self.check_redis_health,
            "prometheus": self.check_prometheus_health,
            "grafana": self.check_grafana_health,
            "docker": self.check_docker_services,
        }

        results = []
        for service in services_to_check:
            if service in check_methods:
                try:
                    result = check_methods[service]()
                    results.append(result)
                except Exception as e:
                    self.errors.append(f"Unexpected error checking {service}: {e}")
                    results.append(False)
                print()  # Add spacing between checks

        return all(results)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="LeadFactory health checker")
    parser.add_argument("--endpoint", help="API endpoint to check")
    parser.add_argument(
        "--services",
        nargs="+",
        choices=["api", "database", "redis", "prometheus", "grafana", "docker"],
        help="Specific services to check",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")

    args = parser.parse_args()

    # Build configuration
    config = {}
    if args.endpoint:
        config["api_endpoint"] = args.endpoint
    if args.timeout:
        config["timeout"] = args.timeout

    # Initialize health checker
    checker = HealthChecker(config)

    # Run health checks
    success = checker.run_all_checks(args.services)

    # Generate report
    report = checker.generate_report()

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        # Print summary
        print("=" * 80)
        print("🎯 HEALTH CHECK REPORT")
        print("=" * 80)

        print(f"\n📅 Check Time: {report['timestamp']}")
        print(f"🏥 Overall Status: {report['overall_status'].upper()}")
        print(
            f"📊 Health: {report['summary']['healthy_services']}/{report['summary']['total_services']} services ({report['summary']['health_percentage']:.1f}%)"
        )

        if report["errors"]:
            print(f"\n❌ ERRORS ({len(report['errors'])}):")
            for i, error in enumerate(report["errors"], 1):
                print(f"   {i}. {error}")

        if report["warnings"]:
            print(f"\n⚠️  WARNINGS ({len(report['warnings'])}):")
            for i, warning in enumerate(report["warnings"], 1):
                print(f"   {i}. {warning}")

        if success and not report["errors"]:
            print("\n✅ ALL HEALTH CHECKS PASSED!")
        else:
            print("\n❌ SOME HEALTH CHECKS FAILED")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
