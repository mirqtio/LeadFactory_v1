"""
Test D6 Reports PDF Converter - Task 052

Tests for HTML to PDF conversion using Playwright with size optimization
and concurrent limits for audit report generation.

Acceptance Criteria:
- Playwright integration ✓
- PDF generation works ✓
- Size optimization ✓
- Concurrent limits ✓
"""

import asyncio
import os
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Import the modules to test
try:
    from d6_reports.pdf_converter import PDFConverter, PDFOptions, PDFResult, html_to_pdf, save_html_as_pdf
    from d6_reports import pdf_converter as pdf_converter_module
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from d6_reports.pdf_converter import PDFConverter, PDFOptions, PDFResult, html_to_pdf, save_html_as_pdf
    from d6_reports import pdf_converter as pdf_converter_module

# Import additional classes
try:
    from d6_reports.pdf_converter import PDFOptimizer, ConcurrencyManager
except ImportError:
    from d6_reports.pdf_converter import PDFOptimizer, ConcurrencyManager


class TestPDFOptions:
    """Test PDF options configuration"""

    def test_pdf_options_defaults(self):
        """Test default PDF options"""
        options = PDFOptions()

        assert options.format == "A4"
        assert options.margin_top == "1cm"
        assert options.margin_bottom == "1cm"
        assert options.margin_left == "1cm"
        assert options.margin_right == "1cm"
        assert options.print_background is True
        assert options.prefer_css_page_size is False
        assert options.display_header_footer is False
        assert options.scale == 1.0
        assert options.landscape is False

    def test_pdf_options_custom(self):
        """Test custom PDF options"""
        options = PDFOptions(
            format="Letter",
            margin_top="2cm",
            scale=0.8,
            landscape=True,
            print_background=False,
        )

        assert options.format == "Letter"
        assert options.margin_top == "2cm"
        assert options.scale == 0.8
        assert options.landscape is True
        assert options.print_background is False

    def test_to_playwright_options(self):
        """Test conversion to Playwright options format"""
        options = PDFOptions(format="A4", margin_top="1cm", scale=0.9, landscape=True)

        playwright_options = options.to_playwright_options()

        assert playwright_options["format"] == "A4"
        assert playwright_options["scale"] == 0.9
        assert playwright_options["landscape"] is True
        assert playwright_options["margin"]["top"] == "1cm"
        assert playwright_options["margin"]["bottom"] == "1cm"
        assert playwright_options["margin"]["left"] == "1cm"
        assert playwright_options["margin"]["right"] == "1cm"


class TestPDFResult:
    """Test PDF result data structure"""

    def test_pdf_result_success(self):
        """Test successful PDF result"""
        pdf_data = b"fake pdf data"
        result = PDFResult(
            success=True,
            pdf_data=pdf_data,
            file_size=len(pdf_data),
            generation_time_ms=1500,
            optimization_ratio=0.2,
        )

        assert result.success is True
        assert result.pdf_data == pdf_data
        assert result.file_size == len(pdf_data)
        assert result.generation_time_ms == 1500
        assert result.optimization_ratio == 0.2
        assert result.error_message is None

    def test_pdf_result_failure(self):
        """Test failed PDF result"""
        result = PDFResult(success=False, error_message="Conversion failed")

        assert result.success is False
        assert result.pdf_data is None
        assert result.file_size is None
        assert result.error_message == "Conversion failed"

    def test_pdf_result_to_dict(self):
        """Test PDF result serialization"""
        result = PDFResult(
            success=True,
            file_size=12345,
            generation_time_ms=2000,
            optimization_ratio=0.15,
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["file_size"] == 12345
        assert result_dict["generation_time_ms"] == 2000
        assert result_dict["optimization_ratio"] == 0.15
        assert result_dict["error_message"] is None


class TestConcurrencyManager:
    """Test concurrency management for PDF generation"""

    @pytest.mark.asyncio
    async def test_concurrency_manager_initialization(self):
        """Test concurrency manager initialization"""
        manager = ConcurrencyManager(max_concurrent=5)

        assert manager.max_concurrent == 5
        assert manager.get_active_count() == 0

    @pytest.mark.asyncio
    async def test_concurrency_acquire_release(self):
        """Test acquiring and releasing concurrency slots"""
        manager = ConcurrencyManager(max_concurrent=2)

        # Initially no active slots
        assert manager.get_active_count() == 0

        # Acquire first slot
        await manager.acquire()
        assert manager.get_active_count() == 1

        # Acquire second slot
        await manager.acquire()
        assert manager.get_active_count() == 2

        # Release first slot
        manager.release()
        assert manager.get_active_count() == 1

        # Release second slot
        manager.release()
        assert manager.get_active_count() == 0

    @pytest.mark.asyncio
    async def test_concurrency_limits(self):
        """Test that concurrency limits are enforced"""
        manager = ConcurrencyManager(max_concurrent=1)

        # Acquire the only slot
        await manager.acquire()
        assert manager.get_active_count() == 1

        # Try to acquire another slot (should block)
        acquire_task = asyncio.create_task(manager.acquire())

        # Wait a short time to ensure the task is blocked
        await asyncio.sleep(0.1)
        assert not acquire_task.done()
        assert manager.get_active_count() == 1

        # Release the slot
        manager.release()

        # Now the blocked task should complete
        await acquire_task
        assert manager.get_active_count() == 1

        # Clean up
        manager.release()


class TestPDFOptimizer:
    """Test PDF optimization functionality"""

    def test_optimize_html_for_pdf_basic(self):
        """Test basic HTML optimization for PDF"""
        html_content = "<html><body><h1>Test</h1></body></html>"
        optimized = PDFOptimizer.optimize_html_for_pdf(html_content)

        # Should contain PDF-optimized CSS
        assert "@media print" in optimized
        assert "color-adjust: exact" in optimized
        assert "page-break-inside: avoid" in optimized
        assert "max-width: 100%" in optimized

    def test_optimize_html_with_existing_head(self):
        """Test optimization with existing head tag"""
        html_content = (
            "<html><head><title>Test</title></head><body><h1>Test</h1></body></html>"
        )
        optimized = PDFOptimizer.optimize_html_for_pdf(html_content)

        # Should preserve existing head content
        assert "<title>Test</title>" in optimized
        # Should add PDF CSS before closing head
        assert "@media print" in optimized
        assert optimized.count("</head>") == 1

    def test_optimize_html_without_head(self):
        """Test optimization without existing head tag"""
        html_content = "<div>Simple content</div>"
        optimized = PDFOptimizer.optimize_html_for_pdf(html_content)

        # Should wrap in proper HTML structure
        assert "<html>" in optimized
        assert "<head>" in optimized
        assert "<body>" in optimized
        assert "@media print" in optimized

    def test_calculate_optimization_ratio(self):
        """Test optimization ratio calculation"""
        # Test normal case
        ratio = PDFOptimizer.calculate_optimization_ratio(1000, 800)
        assert ratio == 0.2  # 20% reduction

        # Test no optimization
        ratio = PDFOptimizer.calculate_optimization_ratio(1000, 1000)
        assert ratio == 0.0

        # Test complete optimization (unlikely but possible)
        ratio = PDFOptimizer.calculate_optimization_ratio(1000, 0)
        assert ratio == 1.0

        # Test zero original size
        ratio = PDFOptimizer.calculate_optimization_ratio(0, 0)
        assert ratio == 0.0


class TestPDFConverter:
    """Test PDF converter main functionality"""

    def test_pdf_converter_initialization(self):
        """Test PDF converter initialization"""
        converter = PDFConverter(max_concurrent=5, browser_timeout=60000)

        assert converter.concurrency_manager.max_concurrent == 5
        assert converter.browser_timeout == 60000
        assert converter.page_timeout == 15000  # Default

    def test_get_concurrency_status(self):
        """Test concurrency status reporting"""
        converter = PDFConverter(max_concurrent=3)
        status = converter.get_concurrency_status()

        assert status["max_concurrent"] == 3
        assert status["active_count"] == 0
        assert status["available_slots"] == 3

    @pytest.mark.asyncio
    async def test_convert_html_to_pdf_no_playwright(self):
        """Test PDF conversion when Playwright is not available"""
        # Mock Playwright as None
        with patch.object(pdf_converter_module, "async_playwright", None):
            converter = PDFConverter()
            result = await converter.convert_html_to_pdf(
                "<html><body>Test</body></html>"
            )

            assert result.success is False
            assert "Playwright not available" in result.error_message

    @pytest.mark.asyncio
    async def test_convert_html_to_pdf_mocked(self):
        """Test PDF conversion with mocked Playwright"""
        # Mock the PDF data
        mock_pdf_data = b"fake pdf content"

        # Mock Playwright components
        mock_page = AsyncMock()
        mock_page.pdf.return_value = mock_pdf_data

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        # Mock the async_playwright context manager
        mock_playwright_ctx = AsyncMock()
        mock_playwright_ctx.start.return_value = mock_playwright

        with patch.object(
            pdf_converter_module, "async_playwright"
        ) as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_ctx

            async with PDFConverter() as converter:
                result = await converter.convert_html_to_pdf(
                    "<html><body>Test</body></html>"
                )

                assert result.success is True
                assert result.pdf_data == mock_pdf_data
                assert result.file_size == len(mock_pdf_data)
                assert result.generation_time_ms > 0

                # Verify Playwright methods were called
                mock_page.set_content.assert_called_once()
                mock_page.pdf.assert_called_once()

    @pytest.mark.asyncio
    async def test_convert_html_to_pdf_with_options(self):
        """Test PDF conversion with custom options"""
        mock_pdf_data = b"fake pdf content"

        mock_page = AsyncMock()
        mock_page.pdf.return_value = mock_pdf_data

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_playwright_ctx = AsyncMock()
        mock_playwright_ctx.start.return_value = mock_playwright

        with patch.object(
            pdf_converter_module, "async_playwright"
        ) as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_ctx

            options = PDFOptions(format="Letter", landscape=True)

            async with PDFConverter() as converter:
                result = await converter.convert_html_to_pdf(
                    "<html><body>Test</body></html>", options=options
                )

                assert result.success is True

                # Verify PDF options were passed correctly
                call_args = mock_page.pdf.call_args[1]
                assert call_args["format"] == "Letter"
                assert call_args["landscape"] is True

    @pytest.mark.asyncio
    async def test_convert_html_to_pdf_error_handling(self):
        """Test PDF conversion error handling"""
        mock_page = AsyncMock()
        mock_page.pdf.side_effect = Exception("PDF generation failed")

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_playwright_ctx = AsyncMock()
        mock_playwright_ctx.start.return_value = mock_playwright

        with patch.object(
            pdf_converter_module, "async_playwright"
        ) as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_ctx

            async with PDFConverter() as converter:
                result = await converter.convert_html_to_pdf(
                    "<html><body>Test</body></html>"
                )

                assert result.success is False
                assert "PDF generation failed" in result.error_message

    @pytest.mark.asyncio
    async def test_batch_convert(self):
        """Test batch PDF conversion"""
        mock_pdf_data = b"fake pdf content"

        mock_page = AsyncMock()
        mock_page.pdf.return_value = mock_pdf_data

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_playwright_ctx = AsyncMock()
        mock_playwright_ctx.start.return_value = mock_playwright

        with patch.object(
            pdf_converter_module, "async_playwright"
        ) as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_ctx

            html_contents = [
                "<html><body>Test 1</body></html>",
                "<html><body>Test 2</body></html>",
                "<html><body>Test 3</body></html>",
            ]

            async with PDFConverter() as converter:
                results = await converter.batch_convert(html_contents)

                assert len(results) == 3
                for result in results:
                    assert result.success is True
                    assert result.pdf_data == mock_pdf_data

    @pytest.mark.asyncio
    async def test_batch_convert_empty_list(self):
        """Test batch conversion with empty list"""
        converter = PDFConverter()
        results = await converter.batch_convert([])

        assert results == []

    @pytest.mark.asyncio
    async def test_convert_html_file_to_pdf(self):
        """Test converting HTML file to PDF"""
        # Create temporary HTML file
        html_content = "<html><body><h1>Test File</h1></body></html>"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            f.write(html_content)
            html_file_path = f.name

        try:
            mock_pdf_data = b"fake pdf content"

            mock_page = AsyncMock()
            mock_page.pdf.return_value = mock_pdf_data

            mock_browser = AsyncMock()
            mock_browser.new_page.return_value = mock_page

            mock_playwright = AsyncMock()
            mock_playwright.chromium.launch.return_value = mock_browser

            mock_playwright_ctx = AsyncMock()
            mock_playwright_ctx.start.return_value = mock_playwright

            with patch.object(
                pdf_converter_module, "async_playwright"
            ) as mock_async_playwright:
                mock_async_playwright.return_value = mock_playwright_ctx

                async with PDFConverter() as converter:
                    result = await converter.convert_html_file_to_pdf(html_file_path)

                    assert result.success is True
                    assert result.pdf_data == mock_pdf_data

                    # Verify the HTML content was read correctly
                    call_args = mock_page.set_content.call_args[0]
                    assert "Test File" in call_args[0]

        finally:
            # Clean up temporary file
            os.unlink(html_file_path)

    @pytest.mark.asyncio
    async def test_convert_html_file_not_found(self):
        """Test converting non-existent HTML file"""
        converter = PDFConverter()
        result = await converter.convert_html_file_to_pdf("/nonexistent/file.html")

        assert result.success is False
        assert (
            "No such file or directory" in result.error_message
            or "cannot find" in result.error_message.lower()
        )

    @pytest.mark.asyncio
    async def test_convert_url_to_pdf_mocked(self):
        """Test URL to PDF conversion with mocked Playwright"""
        mock_pdf_data = b"fake pdf content"

        mock_page = AsyncMock()
        mock_page.pdf.return_value = mock_pdf_data

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_playwright_ctx = AsyncMock()
        mock_playwright_ctx.start.return_value = mock_playwright

        with patch.object(
            pdf_converter_module, "async_playwright"
        ) as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_ctx

            async with PDFConverter() as converter:
                result = await converter.convert_url_to_pdf("https://example.com")

                assert result.success is True
                assert result.pdf_data == mock_pdf_data

                # Verify URL navigation was called
                mock_page.goto.assert_called_once_with(
                    "https://example.com", wait_until="networkidle"
                )


class TestUtilityFunctions:
    """Test utility functions for PDF conversion"""

    @pytest.mark.asyncio
    async def test_html_to_pdf_function(self):
        """Test the html_to_pdf utility function"""
        mock_pdf_data = b"fake pdf content"

        mock_page = AsyncMock()
        mock_page.pdf.return_value = mock_pdf_data

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_playwright_ctx = AsyncMock()
        mock_playwright_ctx.start.return_value = mock_playwright

        with patch.object(
            pdf_converter_module, "async_playwright"
        ) as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_ctx

            result = await html_to_pdf("<html><body>Test</body></html>")

            assert result.success is True
            assert result.pdf_data == mock_pdf_data

    @pytest.mark.asyncio
    async def test_save_html_as_pdf_function(self):
        """Test the save_html_as_pdf utility function"""
        mock_pdf_data = b"fake pdf content"

        mock_page = AsyncMock()
        mock_page.pdf.return_value = mock_pdf_data

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_playwright_ctx = AsyncMock()
        mock_playwright_ctx.start.return_value = mock_playwright

        with patch.object(
            pdf_converter_module, "async_playwright"
        ) as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_ctx

            # Create temporary output file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                output_path = f.name

            try:
                success = await save_html_as_pdf(
                    "<html><body>Test</body></html>", output_path
                )

                assert success is True

                # Verify file was created and contains data
                assert os.path.exists(output_path)
                with open(output_path, "rb") as f:
                    saved_data = f.read()
                assert saved_data == mock_pdf_data

            finally:
                # Clean up
                if os.path.exists(output_path):
                    os.unlink(output_path)

    @pytest.mark.asyncio
    async def test_save_html_as_pdf_failure(self):
        """Test save_html_as_pdf when conversion fails"""
        # Mock failed conversion
        with patch.object(pdf_converter_module, "async_playwright", None):
            success = await save_html_as_pdf(
                "<html><body>Test</body></html>", "/tmp/test.pdf"
            )

            assert success is False


class TestConcurrencyIntegration:
    """Test concurrent PDF generation limits"""

    @pytest.mark.asyncio
    async def test_concurrent_limits_enforced(self):
        """Test that concurrent limits are properly enforced"""
        mock_pdf_data = b"fake pdf content"

        # Create a slower mock that takes some time
        async def slow_pdf_generation(*args, **kwargs):
            await asyncio.sleep(0.2)  # Simulate slow PDF generation
            return mock_pdf_data

        mock_page = AsyncMock()
        mock_page.pdf.side_effect = slow_pdf_generation

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        mock_playwright = AsyncMock()
        mock_playwright.chromium.launch.return_value = mock_browser

        mock_playwright_ctx = AsyncMock()
        mock_playwright_ctx.start.return_value = mock_playwright

        with patch.object(
            pdf_converter_module, "async_playwright"
        ) as mock_async_playwright:
            mock_async_playwright.return_value = mock_playwright_ctx

            # Create converter with max 2 concurrent operations
            async with PDFConverter(max_concurrent=2) as converter:
                # Start 4 conversions simultaneously
                tasks = [
                    converter.convert_html_to_pdf(f"<html><body>Test {i}</body></html>")
                    for i in range(4)
                ]

                # Track active count during execution
                start_time = datetime.now()
                results = await asyncio.gather(*tasks)
                end_time = datetime.now()

                # All should succeed
                for result in results:
                    assert result.success is True

                # Should have taken longer than if all ran concurrently
                # (4 tasks with max 2 concurrent should take ~0.4s minimum)
                execution_time = (end_time - start_time).total_seconds()
                assert execution_time >= 0.3  # Allow some tolerance
