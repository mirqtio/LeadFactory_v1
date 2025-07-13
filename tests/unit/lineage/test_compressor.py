"""
Unit tests for lineage data compression
"""

import pytest

from d6_reports.lineage.compressor import (
    compress_lineage_data,
    decompress_lineage_data,
    _truncate_lineage_data,
)


class TestCompressor:
    """Test suite for lineage compression utilities"""

    @pytest.mark.asyncio
    async def test_compress_small_data(self):
        """Test compression of small data"""
        data = {
            "lead_id": "test-123",
            "pipeline_run_id": "run-456",
            "template_version_id": "v1.0.0",
            "pipeline_logs": ["log1", "log2", "log3"],
        }

        compressed, ratio = await compress_lineage_data(data)

        assert isinstance(compressed, bytes)
        assert len(compressed) > 0
        assert 0 <= ratio <= 100

        # Verify decompression works
        decompressed = decompress_lineage_data(compressed)
        assert decompressed == data

    @pytest.mark.asyncio
    async def test_compress_large_data(self):
        """Test compression of large data"""
        # Create large data with repetitive content (compresses well)
        large_data = {
            "lead_id": "test-123",
            "pipeline_logs": [f"Log entry {i % 10}" for i in range(1000)],
            "raw_inputs": {f"field_{i}": f"value_{i % 20}" for i in range(500)},
        }

        compressed, ratio = await compress_lineage_data(large_data)

        # Should achieve good compression on repetitive data
        assert ratio > 50  # At least 50% compression

        # Verify decompression
        decompressed = decompress_lineage_data(compressed)
        assert decompressed["lead_id"] == large_data["lead_id"]
        assert len(decompressed["pipeline_logs"]) == 1000

    @pytest.mark.asyncio
    async def test_compress_size_limit(self):
        """Test compression respects size limit"""
        import random
        import string

        # Create data that's hard to compress and exceeds 2MB
        # Use random data that doesn't compress well
        random_data = ''.join(random.choices(string.ascii_letters + string.digits, k=3*1024*1024))

        huge_data = {
            "lead_id": "test-123",
            "pipeline_run_id": "run-456",
            "template_version_id": "v1.0.0",
            "huge_field": random_data,  # 3MB of random data
            "another_huge": ''.join(random.choices(string.printable, k=2*1024*1024)),  # 2MB more
        }

        compressed, ratio = await compress_lineage_data(huge_data, max_size_mb=2.0)

        # Should be under 2MB
        size_mb = len(compressed) / (1024 * 1024)
        assert size_mb <= 2.0

        # Verify truncation occurred
        decompressed = decompress_lineage_data(compressed)
        assert "huge_field" not in decompressed  # Large field should be truncated
        assert "another_huge" not in decompressed  # Also truncated
        assert decompressed["lead_id"] == "test-123"  # Essential fields preserved
        assert "huge_field_truncated" in decompressed  # Truncation noted

    def test_decompress_empty_data(self):
        """Test decompression of empty data"""
        result = decompress_lineage_data(b"")
        assert result == {}

    def test_decompress_invalid_data(self):
        """Test decompression of invalid data"""
        result = decompress_lineage_data(b"invalid gzip data")
        assert result == {}

    def test_truncate_lineage_data(self):
        """Test data truncation logic"""
        data = {
            "lead_id": "test-123",
            "pipeline_run_id": "run-456",
            "template_version_id": "v1.0.0",
            "error": {"message": "Test error", "code": 500},
            "summary": {"total": 100, "failed": 5},
            "pipeline_logs": [f"Log {i}" for i in range(300)],
            "raw_inputs": {
                "small_field": "value",
                "large_field": "x" * 1000,
                "list_field": list(range(100)),
                "dict_field": {f"key_{i}": f"value_{i}" for i in range(50)},
            },
        }

        truncated = _truncate_lineage_data(data)

        # Essential fields preserved
        assert truncated["lead_id"] == "test-123"
        assert truncated["pipeline_run_id"] == "run-456"
        assert truncated["template_version_id"] == "v1.0.0"

        # Error and summary preserved
        assert truncated["error"] == data["error"]
        assert truncated["summary"] == data["summary"]

        # Logs truncated
        assert len(truncated["pipeline_logs"]) == 201  # 100 + truncation message + 100
        assert truncated["pipeline_logs"][100] == "... truncated ..."
        assert truncated["pipeline_logs_truncated"] is True

        # Raw inputs handled
        assert truncated["raw_inputs_keys"] == list(data["raw_inputs"].keys())
        assert truncated["raw_inputs_truncated"] is True
        assert truncated["raw_inputs_sample"]["small_field"] == "value"
        assert truncated["raw_inputs_sample"]["large_field"] == "<truncated: str>"
        assert truncated["raw_inputs_sample"]["list_field"] == "<truncated: list>"

    @pytest.mark.asyncio
    async def test_compress_with_special_characters(self):
        """Test compression handles special characters"""
        data = {
            "lead_id": "test-123",
            "unicode": "Hello 世界 🌍",
            "special": "Line1\nLine2\tTab",
            "quotes": 'He said "Hello"',
        }

        compressed, ratio = await compress_lineage_data(data)
        decompressed = decompress_lineage_data(compressed)

        assert decompressed == data

    @pytest.mark.asyncio
    async def test_compression_ratio_calculation(self):
        """Test compression ratio calculation"""
        # Highly compressible data
        data = {"repeated": "a" * 1000}
        compressed, ratio = await compress_lineage_data(data)
        assert ratio > 90  # Should achieve >90% compression

        # Less compressible data (random)
        import random
        import string

        random_data = {
            "random": "".join(random.choices(string.ascii_letters, k=1000))
        }
        compressed2, ratio2 = await compress_lineage_data(random_data)
        assert ratio2 < ratio  # Random data compresses less
