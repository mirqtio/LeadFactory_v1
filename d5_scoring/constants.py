"""Constants for scoring configuration validation and processing."""

# Weight sum validation thresholds
WEIGHT_SUM_WARNING_THRESHOLD = 0.005  # Warning if |Σ-1.0| > 0.005 AND ≤ 0.05
WEIGHT_SUM_ERROR_THRESHOLD = 0.05  # Error if |Σ-1.0| > 0.05

# Default configuration path
DEFAULT_SCORING_RULES_PATH = "config/scoring_rules.yaml"

# Tier labels for metrics
VALID_TIER_LABELS = ["A", "B", "C", "D"]

# Maximum formula evaluation timeout (seconds)
FORMULA_EVALUATION_TIMEOUT = 5.0

# Cache settings
FORMULA_CACHE_SIZE = 100
FORMULA_CACHE_TTL_SECONDS = 300  # 5 minutes
