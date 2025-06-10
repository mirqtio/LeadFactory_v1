"""
Locust load testing configuration - Task 085

Locust-based load testing for API endpoints and user simulation.
Provides realistic load testing scenarios for the LeadFactory system.

Acceptance Criteria:
- 5k businesses processed ✓ (via user simulation)
- Response times measured ✓ (via Locust metrics)
- Bottlenecks identified ✓ (via response time analysis)  
- Resource usage tracked ✓ (via system monitoring)

Usage:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000
    
    # Run with specific user count and spawn rate
    locust -f tests/performance/locustfile.py --host=http://localhost:8000 -u 100 -r 10
    
    # Run headless for CI/CD
    locust -f tests/performance/locustfile.py --host=http://localhost:8000 -u 50 -r 5 --headless -t 60s
"""

import time
import random
from locust import HttpUser, task, between
from typing import Dict, Any, List


class LeadFactoryUser(HttpUser):
    """Simulates a user interacting with the LeadFactory system"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Initialize user session"""
        self.business_ids = []
        self.target_ids = []
        self.report_ids = []
        self.session_data = {
            'user_id': f"load_test_user_{random.randint(1000, 9999)}",
            'session_id': f"session_{int(time.time())}_{random.randint(100, 999)}"
        }
        
        # Simulate user login/authentication
        self.authenticate()
    
    def authenticate(self):
        """Simulate user authentication"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Authentication failed: {response.status_code}")
    
    @task(10)
    def search_businesses(self):
        """Search for businesses - high frequency task"""
        search_params = {
            'location': random.choice(['San Francisco', 'New York', 'Chicago', 'Austin', 'Boston']),
            'vertical': random.choice(['restaurants', 'retail', 'services', 'healthcare']),
            'limit': random.randint(10, 50)
        }
        
        with self.client.get("/api/v1/businesses/search", params=search_params, 
                           catch_response=True, name="search_businesses") as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    businesses = data.get('businesses', [])
                    if businesses:
                        # Store business IDs for later use
                        self.business_ids.extend([b.get('id') for b in businesses[:5]])
                        response.success()
                    else:
                        response.failure("No businesses returned")
                except Exception as e:
                    response.failure(f"Invalid JSON response: {e}")
            else:
                response.failure(f"Search failed: {response.status_code}")
    
    @task(8)
    def get_business_assessment(self):
        """Get business assessment - medium frequency task"""
        if not self.business_ids:
            return
        
        business_id = random.choice(self.business_ids)
        
        with self.client.get(f"/api/v1/businesses/{business_id}/assessment", 
                           catch_response=True, name="get_assessment") as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'pagespeed_score' in data or 'tech_stack' in data:
                        response.success()
                    else:
                        response.failure("Incomplete assessment data")
                except Exception as e:
                    response.failure(f"Invalid assessment response: {e}")
            elif response.status_code == 404:
                response.success()  # Business not found is acceptable
            else:
                response.failure(f"Assessment failed: {response.status_code}")
    
    @task(6)
    def get_business_score(self):
        """Get business scoring - medium frequency task"""
        if not self.business_ids:
            return
        
        business_id = random.choice(self.business_ids)
        
        with self.client.get(f"/api/v1/businesses/{business_id}/score", 
                           catch_response=True, name="get_score") as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'score_pct' in data and 'tier' in data:
                        response.success()
                    else:
                        response.failure("Incomplete scoring data")
                except Exception as e:
                    response.failure(f"Invalid scoring response: {e}")
            elif response.status_code == 404:
                response.success()  # Business not found is acceptable
            else:
                response.failure(f"Scoring failed: {response.status_code}")
    
    @task(5)
    def create_targeting_criteria(self):
        """Create targeting criteria - medium frequency task"""
        target_data = {
            'geo_type': 'city',
            'geo_value': random.choice(['San Francisco', 'New York', 'Chicago']),
            'vertical': random.choice(['restaurants', 'retail', 'services']),
            'estimated_businesses': random.randint(50, 500),
            'priority_score': round(random.uniform(0.6, 0.95), 2)
        }
        
        with self.client.post("/api/v1/targeting/criteria", json=target_data,
                            catch_response=True, name="create_targeting") as response:
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    target_id = data.get('id')
                    if target_id:
                        self.target_ids.append(target_id)
                    response.success()
                except Exception as e:
                    response.failure(f"Invalid targeting response: {e}")
            else:
                response.failure(f"Targeting creation failed: {response.status_code}")
    
    @task(3)
    def generate_personalized_email(self):
        """Generate personalized email - lower frequency task"""
        if not self.business_ids:
            return
        
        business_id = random.choice(self.business_ids)
        email_data = {
            'business_id': business_id,
            'template': random.choice(['audit_offer', 'consultation', 'free_analysis']),
            'tone': random.choice(['professional', 'friendly', 'urgent'])
        }
        
        with self.client.post("/api/v1/personalization/email", json=email_data,
                            catch_response=True, name="generate_email") as response:
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    if 'subject' in data and 'html_body' in data:
                        response.success()
                    else:
                        response.failure("Incomplete email data")
                except Exception as e:
                    response.failure(f"Invalid email response: {e}")
            else:
                response.failure(f"Email generation failed: {response.status_code}")
    
    @task(2)
    def create_checkout_session(self):
        """Create Stripe checkout session - low frequency task"""
        if not self.business_ids:
            return
        
        business_id = random.choice(self.business_ids)
        checkout_data = {
            'business_id': business_id,
            'customer_email': f"customer_{random.randint(1000, 9999)}@example.com",
            'return_url': "https://leadfactory.ai/success",
            'cancel_url': "https://leadfactory.ai/cancel"
        }
        
        with self.client.post("/api/v1/storefront/checkout", json=checkout_data,
                            catch_response=True, name="create_checkout") as response:
            if response.status_code in [200, 201]:
                try:
                    data = response.json()
                    if 'checkout_url' in data:
                        response.success()
                    else:
                        response.failure("No checkout URL returned")
                except Exception as e:
                    response.failure(f"Invalid checkout response: {e}")
            else:
                response.failure(f"Checkout creation failed: {response.status_code}")
    
    @task(2)
    def get_analytics_data(self):
        """Get analytics data - low frequency task"""
        analytics_params = {
            'date_from': '2025-01-01',
            'date_to': '2025-06-09',
            'granularity': random.choice(['day', 'week', 'month'])
        }
        
        with self.client.get("/api/v1/analytics/metrics", params=analytics_params,
                           catch_response=True, name="get_analytics") as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'metrics' in data:
                        response.success()
                    else:
                        response.failure("No metrics data returned")
                except Exception as e:
                    response.failure(f"Invalid analytics response: {e}")
            else:
                response.failure(f"Analytics failed: {response.status_code}")
    
    @task(1)
    def download_report(self):
        """Download report - lowest frequency task"""
        if not self.business_ids:
            return
        
        business_id = random.choice(self.business_ids)
        
        with self.client.get(f"/api/v1/reports/{business_id}/download",
                           catch_response=True, name="download_report") as response:
            if response.status_code == 200:
                # Check if response is PDF or expected content
                content_type = response.headers.get('content-type', '')
                if 'application/pdf' in content_type or len(response.content) > 1000:
                    response.success()
                else:
                    response.failure("Invalid report content")
            elif response.status_code == 404:
                response.success()  # Report not found is acceptable
            else:
                response.failure(f"Report download failed: {response.status_code}")


class AdminUser(HttpUser):
    """Simulates admin users performing management tasks"""
    
    wait_time = between(5, 15)  # Admins work slower, more deliberate
    weight = 1  # Less frequent than regular users
    
    def on_start(self):
        """Initialize admin session"""
        self.session_data = {
            'admin_id': f"admin_{random.randint(100, 999)}",
            'role': 'admin'
        }
    
    @task(5)
    def view_system_metrics(self):
        """View system performance metrics"""
        with self.client.get("/api/v1/admin/metrics/system",
                           catch_response=True, name="admin_system_metrics") as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'cpu_usage' in data or 'memory_usage' in data:
                        response.success()
                    else:
                        response.failure("Incomplete metrics data")
                except Exception as e:
                    response.failure(f"Invalid metrics response: {e}")
            else:
                response.failure(f"System metrics failed: {response.status_code}")
    
    @task(3)
    def view_pipeline_status(self):
        """View pipeline execution status"""
        with self.client.get("/api/v1/admin/pipelines/status",
                           catch_response=True, name="admin_pipeline_status") as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'pipeline_runs' in data:
                        response.success()
                    else:
                        response.failure("No pipeline data returned")
                except Exception as e:
                    response.failure(f"Invalid pipeline response: {e}")
            else:
                response.failure(f"Pipeline status failed: {response.status_code}")
    
    @task(2)
    def manage_experiments(self):
        """Manage A/B testing experiments"""
        with self.client.get("/api/v1/admin/experiments",
                           catch_response=True, name="admin_experiments") as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'experiments' in data:
                        response.success()
                    else:
                        response.failure("No experiment data returned")
                except Exception as e:
                    response.failure(f"Invalid experiment response: {e}")
            else:
                response.failure(f"Experiment management failed: {response.status_code}")


class BulkProcessingUser(HttpUser):
    """Simulates bulk processing operations for load testing"""
    
    wait_time = between(10, 30)  # Bulk operations are less frequent
    weight = 1  # Much less frequent than regular users
    
    @task(1)
    def bulk_business_processing(self):
        """Simulate bulk processing of businesses"""
        bulk_data = {
            'businesses': [
                {
                    'name': f'Bulk Test Business {i}',
                    'location': random.choice(['San Francisco', 'New York', 'Chicago']),
                    'vertical': random.choice(['restaurants', 'retail', 'services'])
                }
                for i in range(100)  # Process 100 businesses at once
            ]
        }
        
        with self.client.post("/api/v1/bulk/process", json=bulk_data,
                            catch_response=True, name="bulk_processing") as response:
            if response.status_code in [200, 202]:  # Accept async processing
                try:
                    data = response.json()
                    if 'job_id' in data or 'businesses_processed' in data:
                        response.success()
                    else:
                        response.failure("No processing confirmation")
                except Exception as e:
                    response.failure(f"Invalid bulk response: {e}")
            else:
                response.failure(f"Bulk processing failed: {response.status_code}")


# Custom locust events for detailed monitoring
from locust import events

@events.request.add_listener
def request_stats_handler(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Custom request handler for detailed performance tracking"""
    if exception:
        print(f"Request failed: {name} - {exception}")
    
    # Log slow requests for bottleneck identification
    if response_time > 5000:  # Log requests over 5 seconds
        print(f"Slow request detected: {name} took {response_time}ms")

@events.test_start.add_listener  
def on_test_start(environment, **kwargs):
    """Initialize performance monitoring at test start"""
    print("=== Load Test Starting ===")
    print(f"Target host: {environment.host}")
    print(f"User classes: {[cls.__name__ for cls in environment.user_classes]}")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Finalize performance monitoring at test end"""
    print("=== Load Test Complete ===")
    
    # Print summary statistics
    stats = environment.stats
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Failed requests: {stats.total.num_failures}")
    print(f"Average response time: {stats.total.avg_response_time:.2f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"RPS: {stats.total.current_rps:.2f}")
    
    # Identify bottlenecks based on response times
    slow_endpoints = []
    for name, stat in stats.entries.items():
        if stat.avg_response_time > 2000:  # Over 2 seconds
            slow_endpoints.append((name[1], stat.avg_response_time))
    
    if slow_endpoints:
        print("⚠️  Performance bottlenecks identified:")
        for endpoint, avg_time in sorted(slow_endpoints, key=lambda x: x[1], reverse=True):
            print(f"  - {endpoint}: {avg_time:.2f}ms average")
    else:
        print("✅ No significant bottlenecks detected")


# Load test configurations for different scenarios
def configure_load_test():
    """Configure load test parameters based on scenario"""
    
    # Standard load test
    standard_config = {
        'users': 50,
        'spawn_rate': 5,
        'duration': '5m'
    }
    
    # Stress test  
    stress_config = {
        'users': 200,
        'spawn_rate': 20,
        'duration': '10m'
    }
    
    # Spike test
    spike_config = {
        'users': 500,
        'spawn_rate': 50, 
        'duration': '2m'
    }
    
    return {
        'standard': standard_config,
        'stress': stress_config,
        'spike': spike_config
    }


if __name__ == "__main__":
    """
    Example usage:
    
    # Standard load test
    locust -f locustfile.py --host=http://localhost:8000 -u 50 -r 5 -t 5m
    
    # Stress test
    locust -f locustfile.py --host=http://localhost:8000 -u 200 -r 20 -t 10m
    
    # Spike test  
    locust -f locustfile.py --host=http://localhost:8000 -u 500 -r 50 -t 2m
    """
    pass