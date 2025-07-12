"""
Performance tests for template preview rendering
"""

import time
from unittest.mock import Mock, patch

import pytest

from d6_reports.template_manager import TemplateManager


class TestTemplatePreviewPerformance:
    """Test suite for template preview performance requirements"""
    
    @pytest.fixture
    def manager(self):
        """Create template manager instance"""
        return TemplateManager()
    
    @pytest.fixture
    def complex_template(self):
        """Create a complex template that tests performance"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>{{ business.name }} - Audit Report</title>
            <style>
                {% for style in custom_styles %}
                    {{ style }}
                {% endfor %}
            </style>
        </head>
        <body>
            <header>
                <h1>{{ business.name }}</h1>
                <p>Generated on {{ metadata.generated_at }}</p>
            </header>
            
            <section class="scores">
                <h2>Assessment Scores</h2>
                <div class="score-grid">
                    <div>Overall: {{ assessment.score }}/100</div>
                    <div>Performance: {{ assessment.performance_score }}/100</div>
                    <div>SEO: {{ assessment.seo_score }}/100</div>
                    <div>Mobile: {{ assessment.mobile_score }}/100</div>
                </div>
            </section>
            
            <section class="findings">
                <h2>Key Findings</h2>
                {% for finding in findings %}
                <article class="finding">
                    <h3>{{ finding.title }}</h3>
                    <p>{{ finding.description }}</p>
                    <div class="metrics">
                        <span>Impact: {{ finding.impact }}</span>
                        <span>Effort: {{ finding.effort }}</span>
                    </div>
                </article>
                {% endfor %}
            </section>
            
            <section class="recommendations">
                <h2>Recommendations</h2>
                {% for category, items in recommendations.items() %}
                <div class="category">
                    <h3>{{ category }}</h3>
                    <ul>
                    {% for item in items %}
                        <li>{{ item }}</li>
                    {% endfor %}
                    </ul>
                </div>
                {% endfor %}
            </section>
            
            <footer>
                <p>© {{ metadata.year }} LeadFactory. All rights reserved.</p>
            </footer>
        </body>
        </html>
        """
    
    def test_preview_renders_under_500ms(self, manager, complex_template):
        """Test that template preview renders in < 500ms as per requirement"""
        # Create sample data with many items
        sample_data = manager.get_sample_lead_data(lead_id=1)
        
        # Add more complex data
        sample_data["custom_styles"] = [
            f".style-{i} {{ color: #{i:06x}; }}" for i in range(50)
        ]
        sample_data["findings"] = [
            {
                "title": f"Finding {i}",
                "description": f"Description for finding {i} " * 10,
                "impact": "high" if i % 3 == 0 else "medium",
                "effort": "low" if i % 2 == 0 else "high",
            }
            for i in range(20)
        ]
        sample_data["recommendations"] = {
            f"Category {i}": [f"Recommendation {j}" for j in range(10)]
            for i in range(5)
        }
        sample_data["metadata"]["year"] = 2024
        
        # Create sandboxed environment
        env = manager.create_safe_environment()
        template = env.from_string(complex_template)
        
        # Measure rendering time
        start_time = time.perf_counter()
        rendered = template.render(**sample_data)
        end_time = time.perf_counter()
        
        render_time_ms = (end_time - start_time) * 1000
        
        # Assert requirement is met
        assert render_time_ms < 500, f"Preview took {render_time_ms:.1f}ms, exceeds 500ms limit"
        
        # Verify output is valid
        assert len(rendered) > 1000  # Should produce substantial output
        assert "{{ business.name }}" not in rendered  # Variables should be replaced
        assert sample_data["business"]["name"] in rendered
    
    def test_multiple_previews_performance(self, manager, complex_template):
        """Test that multiple consecutive previews maintain performance"""
        sample_data = manager.get_sample_lead_data(lead_id=1)
        env = manager.create_safe_environment()
        template = env.from_string(complex_template)
        
        render_times = []
        
        # Render multiple times
        for i in range(10):
            start_time = time.perf_counter()
            rendered = template.render(**sample_data)
            end_time = time.perf_counter()
            
            render_time_ms = (end_time - start_time) * 1000
            render_times.append(render_time_ms)
        
        # All renders should be under 500ms
        assert all(t < 500 for t in render_times), f"Some renders exceeded 500ms: {render_times}"
        
        # Average should be well under 500ms
        avg_time = sum(render_times) / len(render_times)
        assert avg_time < 400, f"Average render time {avg_time:.1f}ms is too high"
    
    def test_preview_with_minimal_data(self, manager):
        """Test preview performance with minimal data"""
        simple_template = "<h1>{{ title }}</h1><p>{{ content }}</p>"
        simple_data = {"title": "Test", "content": "Simple content"}
        
        env = manager.create_safe_environment()
        template = env.from_string(simple_template)
        
        start_time = time.perf_counter()
        rendered = template.render(**simple_data)
        end_time = time.perf_counter()
        
        render_time_ms = (end_time - start_time) * 1000
        
        # Simple templates should be very fast
        assert render_time_ms < 50, f"Simple preview took {render_time_ms:.1f}ms"
    
    def test_preview_caching_benefit(self, manager, complex_template):
        """Test that template compilation provides caching benefit"""
        sample_data = manager.get_sample_lead_data(lead_id=1)
        env = manager.create_safe_environment()
        
        # First render (includes compilation)
        template = env.from_string(complex_template)
        start_time = time.perf_counter()
        first_render = template.render(**sample_data)
        first_time = (time.perf_counter() - start_time) * 1000
        
        # Subsequent renders (template already compiled)
        subsequent_times = []
        for _ in range(5):
            start_time = time.perf_counter()
            rendered = template.render(**sample_data)
            subsequent_times.append((time.perf_counter() - start_time) * 1000)
        
        # Subsequent renders should be faster on average
        avg_subsequent = sum(subsequent_times) / len(subsequent_times)
        assert avg_subsequent <= first_time, "Template caching not providing benefit"
    
    def test_preview_with_large_data_lists(self, manager):
        """Test preview performance with large data lists"""
        template_str = """
        {% for item in large_list %}
            <div>{{ item.id }}: {{ item.value }}</div>
        {% endfor %}
        """
        
        # Create large dataset
        large_data = {
            "large_list": [
                {"id": i, "value": f"Value {i}"}
                for i in range(1000)
            ]
        }
        
        env = manager.create_safe_environment()
        template = env.from_string(template_str)
        
        start_time = time.perf_counter()
        rendered = template.render(**large_data)
        end_time = time.perf_counter()
        
        render_time_ms = (end_time - start_time) * 1000
        
        # Even with 1000 items, should stay under 500ms
        assert render_time_ms < 500, f"Large list preview took {render_time_ms:.1f}ms"
        
        # Verify all items were rendered
        assert "Value 999" in rendered