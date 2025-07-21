#!/usr/bin/env python3
"""
Integration Agent Docker Performance Monitor
Tracks build times, image sizes, and CI performance metrics
"""

import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path


class DockerPerformanceMonitor:
    """Monitor Docker performance for Integration Agent optimization"""

    def __init__(self):
        self.metrics_file = Path(".claude/docker_metrics.json")
        self.metrics = self.load_metrics()

    def load_metrics(self):
        """Load existing metrics or create new"""
        if self.metrics_file.exists():
            with open(self.metrics_file) as f:
                return json.load(f)
        return {"builds": [], "optimizations": [], "ci_runs": []}

    def save_metrics(self):
        """Save metrics to file"""
        self.metrics_file.parent.mkdir(exist_ok=True)
        with open(self.metrics_file, "w") as f:
            json.dump(self.metrics, f, indent=2)

    def measure_build_time(self, dockerfile="Dockerfile.test", target="test"):
        """Measure Docker build time"""
        print(f"📏 Measuring build time for {dockerfile}:{target}")

        start_time = time.time()
        cmd = [
            "docker",
            "buildx",
            "build",
            "--target",
            target,
            "-f",
            dockerfile,
            "--load",
            "-t",
            f"leadfactory-test:{target}-perf",
            ".",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            build_time = time.time() - start_time

            # Get image size
            size_cmd = ["docker", "images", f"leadfactory-test:{target}-perf", "--format", "{{.Size}}"]
            size_result = subprocess.run(size_cmd, capture_output=True, text=True)
            image_size = size_result.stdout.strip()

            metric = {
                "timestamp": datetime.now(UTC).isoformat(),
                "dockerfile": dockerfile,
                "target": target,
                "build_time_seconds": round(build_time, 2),
                "image_size": image_size,
                "success": result.returncode == 0,
                "error": result.stderr if result.returncode != 0 else None,
            }

            self.metrics["builds"].append(metric)
            self.save_metrics()

            print(f"✅ Build completed in {build_time:.2f}s, size: {image_size}")
            return metric

        except subprocess.TimeoutExpired:
            print("⏰ Build timeout (>10 minutes)")
            return None
        except Exception as e:
            print(f"❌ Build failed: {e}")
            return None

    def compare_dockerfiles(self):
        """Compare current vs optimized Dockerfile performance"""
        print("🔄 Comparing Dockerfile performance...")

        # Test current Dockerfile
        current = self.measure_build_time("Dockerfile.test", "test")

        # Test optimized Dockerfile if it exists
        optimized_path = Path("Dockerfile.test.optimized")
        if optimized_path.exists():
            optimized = self.measure_build_time("Dockerfile.test.optimized", "ultra-fast")

            if current and optimized:
                improvement = (
                    (current["build_time_seconds"] - optimized["build_time_seconds"]) / current["build_time_seconds"]
                ) * 100

                print("\n📊 Performance Comparison:")
                print(f"Current:   {current['build_time_seconds']}s ({current['image_size']})")
                print(f"Optimized: {optimized['build_time_seconds']}s ({optimized['image_size']})")
                print(f"Improvement: {improvement:.1f}% faster")

                return improvement
        else:
            print("⚠️ Optimized Dockerfile not found")

        return None

    def check_cache_efficiency(self):
        """Check Docker cache efficiency"""
        print("🗂️ Checking Docker cache efficiency...")

        try:
            # Get cache info
            cache_cmd = ["docker", "system", "df"]
            result = subprocess.run(cache_cmd, capture_output=True, text=True)

            lines = result.stdout.split("\n")
            for line in lines:
                if "Build Cache" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        total_cache = parts[2]
                        reclaimable = parts[3].split("(")[1].split(")")[0]
                        print(f"Cache usage: {total_cache}, reclaimable: {reclaimable}")

                        # If >80% reclaimable, recommend cleanup
                        if "GB" in reclaimable and float(reclaimable.split("%")[0]) > 80:
                            print("⚠️ High cache waste detected - run docker_optimize.sh")
                            return False

            return True

        except Exception as e:
            print(f"❌ Cache check failed: {e}")
            return False

    def monitor_ci_performance(self, run_id=None):
        """Monitor CI performance via GitHub CLI"""
        print("🔍 Monitoring CI performance...")

        try:
            if run_id:
                cmd = ["gh", "run", "view", run_id, "--json", "conclusion,startedAt,updatedAt,jobs"]
            else:
                cmd = ["gh", "run", "list", "--limit", "1", "--json", "conclusion,startedAt,updatedAt,workflowName"]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if isinstance(data, list):
                    data = data[0]

                # Calculate duration
                started = datetime.fromisoformat(data["startedAt"].replace("Z", "+00:00"))
                updated = datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00"))
                duration = (updated - started).total_seconds()

                ci_metric = {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "run_id": run_id,
                    "duration_seconds": duration,
                    "conclusion": data["conclusion"],
                    "workflow": data.get("workflowName", "unknown"),
                }

                self.metrics["ci_runs"].append(ci_metric)
                self.save_metrics()

                print(f"CI Duration: {duration:.0f}s, Status: {data['conclusion']}")
                return ci_metric

        except Exception as e:
            print(f"❌ CI monitoring failed: {e}")

        return None

    def generate_report(self):
        """Generate optimization report"""
        print("\n📊 Integration Agent Docker Performance Report")
        print("=" * 60)

        # Recent builds
        recent_builds = self.metrics["builds"][-5:]
        if recent_builds:
            print(f"\n🏗️ Recent Builds ({len(recent_builds)}):")
            for build in recent_builds:
                status = "✅" if build["success"] else "❌"
                print(
                    f"  {status} {build['dockerfile']}:{build['target']} - {build['build_time_seconds']}s ({build['image_size']})"
                )

        # Recent CI runs
        recent_ci = self.metrics["ci_runs"][-3:]
        if recent_ci:
            print(f"\n🔄 Recent CI Runs ({len(recent_ci)}):")
            for ci in recent_ci:
                status = "✅" if ci["conclusion"] == "success" else "❌"
                print(f"  {status} {ci['workflow']} - {ci['duration_seconds']:.0f}s")

        # Recommendations
        print("\n💡 Optimization Recommendations:")

        if recent_builds:
            avg_build_time = sum(b["build_time_seconds"] for b in recent_builds if b["success"]) / len(
                [b for b in recent_builds if b["success"]]
            )
            if avg_build_time > 120:  # >2 minutes
                print("  🚨 Build times >2min - consider optimized Dockerfile")
            else:
                print("  ✅ Build times acceptable")

        if recent_ci:
            avg_ci_time = sum(ci["duration_seconds"] for ci in recent_ci) / len(recent_ci)
            if avg_ci_time > 300:  # >5 minutes
                print("  🚨 CI times >5min - optimize test selection")
            else:
                print("  ✅ CI times acceptable")

        # Cache check
        if not self.check_cache_efficiency():
            print("  🧹 Run docker_optimize.sh to clean cache")
        else:
            print("  ✅ Docker cache efficiency good")


if __name__ == "__main__":
    monitor = DockerPerformanceMonitor()

    # Run performance comparison
    improvement = monitor.compare_dockerfiles()

    # Monitor latest CI
    monitor.monitor_ci_performance()

    # Generate report
    monitor.generate_report()
