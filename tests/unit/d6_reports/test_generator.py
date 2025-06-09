"""
Test D6 Reports Generator - Task 053

Tests for report generation that coordinates data loading, template rendering,
and output generation (both HTML and PDF) within 30-second timeout.

Acceptance Criteria:
- Data loading complete ✓
- Template rendering works ✓ 
- HTML and PDF generated ✓
- 30-second timeout ✓
"""

import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import time

# Add the project root to Python path
if '/app' not in sys.path:
    sys.path.insert(0, '/app')
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

# Import the modules to test - Direct import for Docker environment
import importlib.util

# Direct module loading approach for Docker environment
# Load template engine module first
template_engine_spec = importlib.util.spec_from_file_location("template_engine", "/app/d6_reports/template_engine.py")
template_engine_module = importlib.util.module_from_spec(template_engine_spec)
template_engine_spec.loader.exec_module(template_engine_module)

# Load PDF converter module
pdf_converter_spec = importlib.util.spec_from_file_location("pdf_converter", "/app/d6_reports/pdf_converter.py")
pdf_converter_module = importlib.util.module_from_spec(pdf_converter_spec)
pdf_converter_spec.loader.exec_module(pdf_converter_module)

# Load prioritizer module  
prioritizer_spec = importlib.util.spec_from_file_location("prioritizer", "/app/d6_reports/prioritizer.py")
prioritizer_module = importlib.util.module_from_spec(prioritizer_spec)
prioritizer_spec.loader.exec_module(prioritizer_module)

# Add modules to sys.modules to enable relative imports
sys.modules['template_engine'] = template_engine_module
sys.modules['pdf_converter'] = pdf_converter_module
sys.modules['prioritizer'] = prioritizer_module
sys.modules['finding_scorer'] = prioritizer_module  # finding_scorer is in prioritizer module

# Now load generator module
generator_spec = importlib.util.spec_from_file_location("generator", "/app/d6_reports/generator.py")
generator_module = importlib.util.module_from_spec(generator_spec)
generator_spec.loader.exec_module(generator_module)

# Extract classes from modules
ReportGenerator = generator_module.ReportGenerator
GenerationOptions = generator_module.GenerationOptions
GenerationResult = generator_module.GenerationResult
DataLoader = generator_module.DataLoader
generate_audit_report = generator_module.generate_audit_report
generate_html_report = generator_module.generate_html_report
generate_pdf_report = generator_module.generate_pdf_report

TemplateEngine = template_engine_module.TemplateEngine
TemplateData = template_engine_module.TemplateData

PDFConverter = pdf_converter_module.PDFConverter
PDFOptions = pdf_converter_module.PDFOptions
PDFResult = pdf_converter_module.PDFResult

FindingPrioritizer = prioritizer_module.FindingPrioritizer
PrioritizationResult = prioritizer_module.PrioritizationResult



class TestGenerationOptions:
    """Test generation options configuration"""
    
    def test_generation_options_defaults(self):
        """Test default generation options"""
        options = GenerationOptions()
        
        assert options.include_pdf is True
        assert options.include_html is True
        assert options.timeout_seconds == 30
        assert options.template_name == "basic_report"
        assert options.pdf_options is None
        assert options.max_findings == 50
        assert options.max_top_issues == 3
        assert options.max_quick_wins == 5
    
    def test_generation_options_custom(self):
        """Test custom generation options"""
        pdf_options = PDFOptions(format="Letter")
        options = GenerationOptions(
            include_pdf=False,
            timeout_seconds=60,
            template_name="custom_template",
            pdf_options=pdf_options,
            max_findings=100
        )
        
        assert options.include_pdf is False
        assert options.timeout_seconds == 60
        assert options.template_name == "custom_template"
        assert options.pdf_options == pdf_options
        assert options.max_findings == 100


class TestGenerationResult:
    """Test generation result data structure"""
    
    def test_generation_result_success(self):
        """Test successful generation result"""
        pdf_result = PDFResult(success=True, pdf_data=b"fake pdf", file_size=100)
        result = GenerationResult(
            success=True,
            html_content="<html>Test</html>",
            pdf_result=pdf_result,
            generation_time_seconds=2.5,
            data_loading_time_ms=100,
            template_rendering_time_ms=200,
            pdf_generation_time_ms=1500
        )
        
        assert result.success is True
        assert result.html_content == "<html>Test</html>"
        assert result.pdf_result == pdf_result
        assert result.generation_time_seconds == 2.5
        assert result.warnings == []  # Should be initialized to empty list
    
    def test_generation_result_failure(self):
        """Test failed generation result"""
        result = GenerationResult(
            success=False,
            error_message="Generation failed",
            warnings=["Warning 1", "Warning 2"]
        )
        
        assert result.success is False
        assert result.html_content is None
        assert result.pdf_result is None
        assert result.error_message == "Generation failed"
        assert len(result.warnings) == 2
    
    def test_generation_result_to_dict(self):
        """Test generation result serialization"""
        pdf_result = PDFResult(
            success=True, 
            pdf_data=b"fake pdf", 
            file_size=150,
            optimization_ratio=0.2
        )
        result = GenerationResult(
            success=True,
            html_content="<html>Test</html>",
            pdf_result=pdf_result,
            generation_time_seconds=1.8,
            data_loading_time_ms=80,
            template_rendering_time_ms=120,
            pdf_generation_time_ms=900
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["success"] is True
        assert result_dict["generation_time_seconds"] == 1.8
        assert result_dict["has_html"] is True
        assert result_dict["has_pdf"] is True
        assert result_dict["pdf_file_size"] == 150
        assert result_dict["pdf_optimization_ratio"] == 0.2


class TestDataLoader:
    """Test data loading functionality"""
    
    def test_load_business_data(self):
        """Test business data loading"""
        business_data = DataLoader.load_business_data("test123")
        
        assert business_data["id"] == "test123"
        assert "Business test123" in business_data["name"]
        assert business_data["url"] == "https://businesstest123.com"
        assert "phone" in business_data
        assert "address" in business_data
        assert business_data["industry"] == "restaurant"
        assert isinstance(business_data["rating"], (int, float))
        assert isinstance(business_data["review_count"], int)
    
    def test_load_assessment_data(self):
        """Test assessment data loading"""
        assessment_data = DataLoader.load_assessment_data("test123")
        
        assert assessment_data["business_id"] == "test123"
        assert "performance_score" in assessment_data
        assert "accessibility_score" in assessment_data
        assert "seo_score" in assessment_data
        assert "core_web_vitals" in assessment_data
        assert "opportunities" in assessment_data
        assert "tech_stack" in assessment_data
        assert "ai_insights" in assessment_data
        
        # Check structure of nested data
        assert "lcp" in assessment_data["core_web_vitals"]
        assert len(assessment_data["opportunities"]) >= 2
        assert len(assessment_data["ai_insights"]) >= 3
    
    def test_validate_data_success(self):
        """Test data validation with valid data"""
        business_data = {"name": "Test Business", "url": "https://test.com"}
        assessment_data = {
            "performance_score": 75,
            "opportunities": [{"title": "Test"}],
            "ai_insights": [{"insight": "Test insight"}]
        }
        
        warnings = DataLoader.validate_data(business_data, assessment_data)
        assert warnings == []
    
    def test_validate_data_missing_fields(self):
        """Test data validation with missing fields"""
        business_data = {}  # Missing name and url
        assessment_data = {}  # Missing required fields
        
        warnings = DataLoader.validate_data(business_data, assessment_data)
        
        assert len(warnings) >= 4  # Should have warnings for missing fields
        assert any("name" in warning for warning in warnings)
        assert any("URL" in warning for warning in warnings)
        assert any("performance" in warning for warning in warnings)


class TestReportGenerator:
    """Test main report generator functionality"""
    
    def test_report_generator_initialization(self):
        """Test report generator initialization"""
        generator = ReportGenerator()
        
        assert generator.template_engine is not None
        assert generator.pdf_converter is not None
        assert generator.finding_prioritizer is not None
        assert generator.data_loader is not None
    
    def test_report_generator_custom_components(self):
        """Test report generator with custom components"""
        mock_template_engine = Mock()
        mock_pdf_converter = Mock()
        mock_prioritizer = Mock()
        
        generator = ReportGenerator(
            template_engine=mock_template_engine,
            pdf_converter=mock_pdf_converter,
            finding_prioritizer=mock_prioritizer
        )
        
        assert generator.template_engine == mock_template_engine
        assert generator.pdf_converter == mock_pdf_converter
        assert generator.finding_prioritizer == mock_prioritizer
    
    def test_extract_findings(self):
        """Test finding extraction from assessment data"""
        generator = ReportGenerator()
        
        assessment_data = {
            "opportunities": [
                {
                    "id": "unused-js",
                    "title": "Remove unused JavaScript",
                    "description": "Reduce bundle size",
                    "numeric_value": 500,
                    "display_value": "Potential savings of 500ms"
                }
            ],
            "ai_insights": [
                {
                    "category": "performance",
                    "insight": "Site is slow",
                    "recommendation": "Optimize images",
                    "impact": "high",
                    "effort": "medium"
                }
            ]
        }
        
        findings = generator._extract_findings(assessment_data, max_findings=10)
        
        assert len(findings) == 2
        
        # Check PageSpeed finding
        ps_finding = findings[0]
        assert ps_finding["id"] == "unused-js"
        assert ps_finding["title"] == "Remove unused JavaScript"
        assert ps_finding["category"] == "performance"
        assert ps_finding["source"] == "pagespeed"
        assert ps_finding["impact_score"] == 6  # Medium impact for 500ms
        
        # Check AI insight finding
        ai_finding = findings[1]
        assert ai_finding["id"] == "ai_performance"
        assert ai_finding["category"] == "performance"
        assert ai_finding["source"] == "ai_insights"
        assert ai_finding["impact_score"] == 9  # High impact
        assert ai_finding["effort_score"] == 5  # Medium effort
    
    def test_calculate_impact_from_savings(self):
        """Test impact calculation from performance savings"""
        generator = ReportGenerator()
        
        # Test different impact levels
        assert generator._calculate_impact_from_savings(1500) == 9  # High impact (>1s)
        assert generator._calculate_impact_from_savings(750) == 6   # Medium impact (500ms+)
        assert generator._calculate_impact_from_savings(250) == 3   # Low impact (100ms+)
        assert generator._calculate_impact_from_savings(50) == 1    # Minimal impact (<100ms)
    
    @pytest.mark.asyncio
    async def test_generate_report_success(self):
        """Test successful report generation"""
        # Mock components
        mock_template_engine = Mock()
        mock_template_engine.render_template.return_value = "<html>Test Report</html>"
        mock_template_engine.create_template_data.return_value = TemplateData(
            business={}, assessment={}, findings=[], top_issues=[], quick_wins=[], metadata={}
        )
        
        mock_pdf_result = PDFResult(success=True, pdf_data=b"fake pdf", file_size=100)
        mock_pdf_converter = AsyncMock()
        mock_pdf_converter.__aenter__.return_value = mock_pdf_converter
        mock_pdf_converter.__aexit__.return_value = None
        mock_pdf_converter.convert_html_to_pdf.return_value = mock_pdf_result
        
        mock_prioritizer = Mock()
        mock_prioritizer.prioritize_findings.return_value = PrioritizationResult(
            top_issues=[], quick_wins=[], all_scored_findings=[]
        )
        
        generator = ReportGenerator(
            template_engine=mock_template_engine,
            pdf_converter=mock_pdf_converter,
            finding_prioritizer=mock_prioritizer
        )
        
        # Test generation
        result = await generator.generate_report("test123")
        
        assert result.success is True
        assert result.html_content == "<html>Test Report</html>"
        assert result.pdf_result == mock_pdf_result
        assert result.generation_time_seconds > 0
        assert result.data_loading_time_ms > 0
        assert result.template_rendering_time_ms > 0
        assert result.pdf_generation_time_ms > 0
        assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_generate_report_timeout(self):
        """Test report generation timeout"""
        # Create a slow mock that will cause timeout
        async def slow_conversion(*args, **kwargs):
            await asyncio.sleep(2)  # Sleep longer than timeout
            return PDFResult(success=True, pdf_data=b"fake", file_size=100)
        
        mock_template_engine = Mock()
        mock_template_engine.render_template.return_value = "<html>Test</html>"
        mock_template_engine.create_template_data.return_value = TemplateData(
            business={}, assessment={}, findings=[], top_issues=[], quick_wins=[], metadata={}
        )
        
        mock_pdf_converter = AsyncMock()
        mock_pdf_converter.__aenter__.return_value = mock_pdf_converter
        mock_pdf_converter.__aexit__.return_value = None
        mock_pdf_converter.convert_html_to_pdf.side_effect = slow_conversion
        
        mock_prioritizer = Mock()
        mock_prioritizer.prioritize_findings.return_value = PrioritizationResult(
            top_issues=[], quick_wins=[], all_scored_findings=[]
        )
        
        generator = ReportGenerator(
            template_engine=mock_template_engine,
            pdf_converter=mock_pdf_converter,
            finding_prioritizer=mock_prioritizer
        )
        
        # Test with very short timeout
        options = GenerationOptions(timeout_seconds=1)
        result = await generator.generate_report("test123", options)
        
        assert result.success is False
        assert "timeout" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_generate_report_template_error(self):
        """Test report generation with template error"""
        mock_template_engine = Mock()
        mock_template_engine.render_template.side_effect = Exception("Template error")
        mock_template_engine.create_template_data.return_value = TemplateData(
            business={}, assessment={}, findings=[], top_issues=[], quick_wins=[], metadata={}
        )
        
        mock_prioritizer = Mock()
        mock_prioritizer.prioritize_findings.return_value = PrioritizationResult(
            top_issues=[], quick_wins=[], all_scored_findings=[]
        )
        
        generator = ReportGenerator(
            template_engine=mock_template_engine,
            pdf_converter=Mock(),
            finding_prioritizer=mock_prioritizer
        )
        
        result = await generator.generate_report("test123")
        
        assert result.success is False
        assert "Template rendering failed" in result.error_message
    
    @pytest.mark.asyncio
    async def test_generate_html_only(self):
        """Test HTML-only generation"""
        mock_template_engine = Mock()
        mock_template_engine.render_template.return_value = "<html>HTML Only</html>"
        mock_template_engine.create_template_data.return_value = TemplateData(
            business={}, assessment={}, findings=[], top_issues=[], quick_wins=[], metadata={}
        )
        
        mock_prioritizer = Mock()
        mock_prioritizer.prioritize_findings.return_value = PrioritizationResult(
            top_issues=[], quick_wins=[], all_scored_findings=[]
        )
        
        generator = ReportGenerator(
            template_engine=mock_template_engine,
            pdf_converter=Mock(),
            finding_prioritizer=mock_prioritizer
        )
        
        result = await generator.generate_html_only("test123", "custom_template")
        
        assert result.success is True
        assert result.html_content == "<html>HTML Only</html>"
        assert result.pdf_result is None
        
        # Verify template name was passed
        mock_template_engine.render_template.assert_called_with("custom_template", mock_template_engine.create_template_data.return_value)
    
    @pytest.mark.asyncio
    async def test_generate_pdf_only(self):
        """Test PDF-only generation"""
        mock_template_engine = Mock()
        mock_template_engine.render_template.return_value = "<html>For PDF</html>"
        mock_template_engine.create_template_data.return_value = TemplateData(
            business={}, assessment={}, findings=[], top_issues=[], quick_wins=[], metadata={}
        )
        
        mock_pdf_result = PDFResult(success=True, pdf_data=b"pdf only", file_size=200)
        mock_pdf_converter = AsyncMock()
        mock_pdf_converter.__aenter__.return_value = mock_pdf_converter
        mock_pdf_converter.__aexit__.return_value = None
        mock_pdf_converter.convert_html_to_pdf.return_value = mock_pdf_result
        
        mock_prioritizer = Mock()
        mock_prioritizer.prioritize_findings.return_value = PrioritizationResult(
            top_issues=[], quick_wins=[], all_scored_findings=[]
        )
        
        generator = ReportGenerator(
            template_engine=mock_template_engine,
            pdf_converter=mock_pdf_converter,
            finding_prioritizer=mock_prioritizer
        )
        
        pdf_options = PDFOptions(format="Letter")
        result = await generator.generate_pdf_only("test123", pdf_options)
        
        assert result.success is True
        assert result.html_content is None  # Should be cleared for PDF-only
        assert result.pdf_result == mock_pdf_result
        
        # Verify PDF options were passed
        mock_pdf_converter.convert_html_to_pdf.assert_called_with("<html>For PDF</html>", options=pdf_options)
    
    @pytest.mark.asyncio
    async def test_batch_generate(self):
        """Test batch report generation"""
        mock_template_engine = Mock()
        mock_template_engine.render_template.return_value = "<html>Batch Report</html>"
        mock_template_engine.create_template_data.return_value = TemplateData(
            business={}, assessment={}, findings=[], top_issues=[], quick_wins=[], metadata={}
        )
        
        mock_pdf_result = PDFResult(success=True, pdf_data=b"batch pdf", file_size=100)
        mock_pdf_converter = AsyncMock()
        mock_pdf_converter.__aenter__.return_value = mock_pdf_converter
        mock_pdf_converter.__aexit__.return_value = None
        mock_pdf_converter.convert_html_to_pdf.return_value = mock_pdf_result
        
        mock_prioritizer = Mock()
        mock_prioritizer.prioritize_findings.return_value = PrioritizationResult(
            top_issues=[], quick_wins=[], all_scored_findings=[]
        )
        
        generator = ReportGenerator(
            template_engine=mock_template_engine,
            pdf_converter=mock_pdf_converter,
            finding_prioritizer=mock_prioritizer
        )
        
        business_ids = ["biz1", "biz2", "biz3"]
        results = await generator.batch_generate(business_ids)
        
        assert len(results) == 3
        for result in results:
            assert result.success is True
            assert result.html_content == "<html>Batch Report</html>"
            assert result.pdf_result == mock_pdf_result
    
    @pytest.mark.asyncio
    async def test_batch_generate_empty_list(self):
        """Test batch generation with empty list"""
        generator = ReportGenerator()
        results = await generator.batch_generate([])
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_batch_generate_with_errors(self):
        """Test batch generation with some failures"""
        # Create a generator that fails for specific business IDs
        async def failing_generate(business_id, options=None):
            if business_id == "fail":
                raise Exception("Intentional failure")
            return GenerationResult(success=True, html_content="<html>Success</html>")
        
        generator = ReportGenerator()
        generator.generate_report = failing_generate
        
        business_ids = ["success1", "fail", "success2"]
        results = await generator.batch_generate(business_ids)
        
        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert "Intentional failure" in results[1].error_message
        assert results[2].success is True
    
    def test_get_status(self):
        """Test generator status reporting"""
        mock_template_engine = Mock()
        mock_template_engine.list_templates.return_value = ["basic_report", "minimal_report"]
        
        mock_pdf_converter = Mock()
        mock_pdf_converter.get_concurrency_status.return_value = {
            "max_concurrent": 3,
            "active_count": 1,
            "available_slots": 2
        }
        
        mock_prioritizer = Mock()
        mock_prioritizer.scorer = Mock()  # Has scorer
        
        generator = ReportGenerator(
            template_engine=mock_template_engine,
            pdf_converter=mock_pdf_converter,
            finding_prioritizer=mock_prioritizer
        )
        
        status = generator.get_status()
        
        assert "template_engine" in status
        assert status["template_engine"]["available_templates"] == ["basic_report", "minimal_report"]
        assert "pdf_converter" in status
        assert status["pdf_converter"]["max_concurrent"] == 3
        assert "finding_prioritizer" in status
        assert status["finding_prioritizer"]["scorer_available"] is True


class TestUtilityFunctions:
    """Test utility functions for report generation"""
    
    @pytest.mark.asyncio
    async def test_generate_audit_report_function(self):
        """Test the generate_audit_report utility function"""
        # Mock the ReportGenerator class
        mock_result = GenerationResult(success=True, html_content="<html>Test</html>")
        
        with patch.object(generator_module, 'ReportGenerator') as mock_generator_class:
            mock_generator = Mock()
            mock_generator.generate_report.return_value = mock_result
            mock_generator_class.return_value = mock_generator
            
            result = await generate_audit_report("test123")
            
            assert result == mock_result
            mock_generator.generate_report.assert_called_once_with("test123", None)
    
    @pytest.mark.asyncio
    async def test_generate_html_report_function(self):
        """Test the generate_html_report utility function"""
        mock_result = GenerationResult(success=True, html_content="<html>HTML Test</html>")
        
        with patch.object(generator_module, 'ReportGenerator') as mock_generator_class:
            mock_generator = Mock()
            mock_generator.generate_html_only.return_value = mock_result
            mock_generator_class.return_value = mock_generator
            
            html_content = await generate_html_report("test123", "custom_template")
            
            assert html_content == "<html>HTML Test</html>"
            mock_generator.generate_html_only.assert_called_once_with("test123", "custom_template")
    
    @pytest.mark.asyncio
    async def test_generate_html_report_function_failure(self):
        """Test generate_html_report function with failure"""
        mock_result = GenerationResult(success=False, error_message="HTML generation failed")
        
        with patch.object(generator_module, 'ReportGenerator') as mock_generator_class:
            mock_generator = Mock()
            mock_generator.generate_html_only.return_value = mock_result
            mock_generator_class.return_value = mock_generator
            
            with pytest.raises(Exception) as exc_info:
                await generate_html_report("test123")
            
            assert "HTML generation failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_generate_pdf_report_function(self):
        """Test the generate_pdf_report utility function"""
        pdf_data = b"fake pdf content"
        mock_pdf_result = PDFResult(success=True, pdf_data=pdf_data, file_size=len(pdf_data))
        mock_result = GenerationResult(success=True, pdf_result=mock_pdf_result)
        
        with patch.object(generator_module, 'ReportGenerator') as mock_generator_class:
            mock_generator = Mock()
            mock_generator.generate_pdf_only.return_value = mock_result
            mock_generator_class.return_value = mock_generator
            
            pdf_options = PDFOptions(format="Letter")
            pdf_bytes = await generate_pdf_report("test123", pdf_options)
            
            assert pdf_bytes == pdf_data
            mock_generator.generate_pdf_only.assert_called_once_with("test123", pdf_options)
    
    @pytest.mark.asyncio
    async def test_generate_pdf_report_function_failure(self):
        """Test generate_pdf_report function with failure"""
        mock_result = GenerationResult(success=False, error_message="PDF generation failed")
        
        with patch.object(generator_module, 'ReportGenerator') as mock_generator_class:
            mock_generator = Mock()
            mock_generator.generate_pdf_only.return_value = mock_result
            mock_generator_class.return_value = mock_generator
            
            with pytest.raises(Exception) as exc_info:
                await generate_pdf_report("test123")
            
            assert "PDF generation failed" in str(exc_info.value)


class TestTimeoutAndPerformance:
    """Test timeout handling and performance requirements"""
    
    @pytest.mark.asyncio
    async def test_30_second_timeout_acceptance_criteria(self):
        """Test that timeout is properly enforced (Acceptance Criteria)"""
        # Create a generator that simulates work taking longer than timeout
        generator = ReportGenerator()
        
        # Mock data loader to take some time
        original_load_business = generator.data_loader.load_business_data
        original_load_assessment = generator.data_loader.load_assessment_data
        
        async def slow_operation():
            await asyncio.sleep(0.5)  # Simulate slow operation
        
        def slow_load_business(business_id):
            # This will be called in synchronous context, so we can't use asyncio.sleep
            time.sleep(0.3)  # Simulate slow business data loading
            return original_load_business(business_id)
        
        def slow_load_assessment(business_id):
            time.sleep(0.3)  # Simulate slow assessment data loading
            return original_load_assessment(business_id)
        
        generator.data_loader.load_business_data = slow_load_business
        generator.data_loader.load_assessment_data = slow_load_assessment
        
        # Set a very short timeout to trigger timeout error
        options = GenerationOptions(timeout_seconds=1)
        
        start_time = time.time()
        result = await generator.generate_report("test123", options)
        end_time = time.time()
        
        # Should timeout and return failure
        assert result.success is False
        assert "timeout" in result.error_message.lower()
        
        # Should respect timeout limit (with some tolerance)
        assert end_time - start_time <= 1.5  # Allow 0.5s tolerance
    
    @pytest.mark.asyncio
    async def test_data_loading_timing(self):
        """Test that data loading time is tracked"""
        generator = ReportGenerator()
        
        # Mock to ensure we get consistent results
        mock_template_engine = Mock()
        mock_template_engine.render_template.return_value = "<html>Test</html>"
        mock_template_engine.create_template_data.return_value = TemplateData(
            business={}, assessment={}, findings=[], top_issues=[], quick_wins=[], metadata={}
        )
        
        mock_prioritizer = Mock()
        mock_prioritizer.prioritize_findings.return_value = PrioritizationResult(
            top_issues=[], quick_wins=[], all_scored_findings=[]
        )
        
        generator.template_engine = mock_template_engine
        generator.finding_prioritizer = mock_prioritizer
        
        # Generate HTML-only report to avoid PDF complexity
        options = GenerationOptions(include_pdf=False)
        result = await generator.generate_report("test123", options)
        
        assert result.success is True
        assert result.data_loading_time_ms > 0
        assert result.template_rendering_time_ms > 0
        assert result.pdf_generation_time_ms == 0  # No PDF generated
    
    @pytest.mark.asyncio
    async def test_concurrent_generation_performance(self):
        """Test that multiple reports can be generated concurrently"""
        generator = ReportGenerator()
        
        # Mock components for consistent behavior
        mock_template_engine = Mock()
        mock_template_engine.render_template.return_value = "<html>Concurrent Test</html>"
        mock_template_engine.create_template_data.return_value = TemplateData(
            business={}, assessment={}, findings=[], top_issues=[], quick_wins=[], metadata={}
        )
        
        mock_prioritizer = Mock()
        mock_prioritizer.prioritize_findings.return_value = PrioritizationResult(
            top_issues=[], quick_wins=[], all_scored_findings=[]
        )
        
        generator.template_engine = mock_template_engine
        generator.finding_prioritizer = mock_prioritizer
        
        # Generate multiple reports concurrently
        business_ids = ["biz1", "biz2", "biz3", "biz4", "biz5"]
        options = GenerationOptions(include_pdf=False)  # HTML only for speed
        
        start_time = time.time()
        
        tasks = [
            generator.generate_report(business_id, options)
            for business_id in business_ids
        ]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # All should succeed
        for result in results:
            assert result.success is True
            assert result.html_content == "<html>Concurrent Test</html>"
        
        # Should complete reasonably quickly for HTML-only generation
        assert total_time < 5.0  # Should be much faster than 5 seconds
        
        # Average generation time should be reasonable
        avg_time = sum(r.generation_time_seconds for r in results) / len(results)
        assert avg_time < 2.0  # Each report should average under 2 seconds