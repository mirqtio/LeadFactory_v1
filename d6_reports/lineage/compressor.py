"""
Data compression utilities for lineage storage
"""

import gzip
import json
import sys
from typing import Any, Dict


def compress_lineage_data(
    data: Dict[str, Any], max_size_mb: float = 2.0
) -> tuple[bytes, float]:
    """
    Compress lineage data with size limit

    Args:
        data: Dictionary of data to compress
        max_size_mb: Maximum size in megabytes (default 2MB)

    Returns:
        Tuple of (compressed_bytes, compression_ratio)
    """
    # Convert to JSON string
    json_str = json.dumps(data, default=str, separators=(",", ":"))
    original_size = len(json_str.encode("utf-8"))

    # Compress with gzip level 6 (balanced speed/compression)
    compressed = gzip.compress(json_str.encode("utf-8"), compresslevel=6)
    compressed_size = len(compressed)

    # Check size limit
    size_mb = compressed_size / (1024 * 1024)
    if size_mb > max_size_mb:
        # Truncate data and retry
        truncated_data = _truncate_lineage_data(data)
        return compress_lineage_data(truncated_data, max_size_mb)

    # Calculate compression ratio
    compression_ratio = (
        ((original_size - compressed_size) / original_size * 100) if original_size > 0 else 0
    )

    return compressed, round(compression_ratio, 2)


def decompress_lineage_data(compressed_data: bytes) -> Dict[str, Any]:
    """
    Decompress lineage data

    Args:
        compressed_data: Compressed bytes

    Returns:
        Original dictionary data
    """
    if not compressed_data:
        return {}

    try:
        decompressed = gzip.decompress(compressed_data)
        return json.loads(decompressed.decode("utf-8"))
    except Exception as e:
        # Log error and return empty dict
        print(f"Error decompressing lineage data: {e}")
        return {}


def _truncate_lineage_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Truncate lineage data to reduce size

    Priority order (keep most important):
    1. Lead ID, pipeline run ID, template version
    2. Pipeline start/end times
    3. Error information if present
    4. Summary statistics
    5. Truncate large logs and raw data
    """
    truncated = {
        "lead_id": data.get("lead_id"),
        "pipeline_run_id": data.get("pipeline_run_id"),
        "template_version_id": data.get("template_version_id"),
        "pipeline_start_time": data.get("pipeline_start_time"),
        "pipeline_end_time": data.get("pipeline_end_time"),
    }

    # Keep error information if present
    if "error" in data:
        truncated["error"] = data["error"]

    # Keep summary statistics
    if "summary" in data:
        truncated["summary"] = data["summary"]

    # Truncate logs if present
    if "pipeline_logs" in data and isinstance(data["pipeline_logs"], list):
        # Keep first and last 100 log entries
        logs = data["pipeline_logs"]
        if len(logs) > 200:
            truncated["pipeline_logs"] = logs[:100] + ["... truncated ..."] + logs[-100:]
            truncated["pipeline_logs_truncated"] = True
            truncated["pipeline_logs_total_count"] = len(logs)
        else:
            truncated["pipeline_logs"] = logs

    # Truncate raw inputs if present
    if "raw_inputs" in data:
        raw_inputs = data["raw_inputs"]
        if isinstance(raw_inputs, dict):
            # Keep only keys and sample values
            truncated["raw_inputs_keys"] = list(raw_inputs.keys())
            truncated["raw_inputs_truncated"] = True

            # Keep small values completely
            sample_inputs = {}
            for key, value in raw_inputs.items():
                if isinstance(value, (str, int, float, bool)) and len(str(value)) < 100:
                    sample_inputs[key] = value
                elif isinstance(value, list) and len(value) < 10:
                    sample_inputs[key] = value
                elif isinstance(value, dict) and len(str(value)) < 500:
                    sample_inputs[key] = value
                else:
                    sample_inputs[key] = f"<truncated: {type(value).__name__}>"

            truncated["raw_inputs_sample"] = sample_inputs
    
    # Check all other fields and truncate large ones
    for key, value in data.items():
        if key not in truncated and key not in ["pipeline_logs", "raw_inputs"]:
            # Truncate any other large field
            if isinstance(value, str) and len(value) > 1000:
                truncated[f"{key}_truncated"] = True
                truncated[f"{key}_size"] = len(value)
            elif isinstance(value, (list, dict)) and len(str(value)) > 1000:
                truncated[f"{key}_truncated"] = True
                truncated[f"{key}_type"] = type(value).__name__
            elif sys.getsizeof(value) < 1000:
                # Only keep small values
                truncated[key] = value

    return truncated