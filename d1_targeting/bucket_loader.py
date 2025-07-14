"""
Bucket feature loader for Phase 0.5
Task TG-06: Load CSV seed data for bucket assignment
"""
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BucketFeatureLoader:
    """Load and manage bucket features from CSV seed files"""

    def __init__(self, seed_dir: Optional[Path] = None):
        """
        Initialize bucket feature loader

        Args:
            seed_dir: Directory containing CSV seed files
        """
        if seed_dir is None:
            # Default to data/seed relative to project root
            seed_dir = Path(__file__).parent.parent / "data" / "seed"

        self.seed_dir = Path(seed_dir)
        self.geo_features: Dict[str, Dict[str, str]] = {}
        self.vertical_features: Dict[str, Dict[str, str]] = {}

        # Load features on initialization
        self._load_geo_features()
        self._load_vertical_features()

    def _load_geo_features(self) -> None:
        """Load geographic features from CSV"""
        geo_file = self.seed_dir / "geo_features.csv"

        if not geo_file.exists():
            logger.warning(f"Geo features file not found: {geo_file}")
            return

        try:
            with open(geo_file, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    zip_code = row["zip_code"]
                    self.geo_features[zip_code] = {
                        "city": row["city"],
                        "state": row["state"],
                        "affluence": row["affluence"],
                        "agency_density": row["agency_density"],
                        "broadband_quality": row["broadband_quality"],
                    }

            logger.info(f"Loaded {len(self.geo_features)} geo features")

        except Exception as e:
            logger.error(f"Failed to load geo features: {e}")

    def _load_vertical_features(self) -> None:
        """Load vertical features from CSV"""
        vert_file = self.seed_dir / "vertical_features.csv"

        if not vert_file.exists():
            logger.warning(f"Vertical features file not found: {vert_file}")
            return

        try:
            with open(vert_file, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    category = row["yelp_category"]
                    self.vertical_features[category] = {
                        "business_vertical": row["business_vertical"],
                        "urgency": row["urgency"],
                        "ticket_size": row["ticket_size"],
                        "maturity": row["maturity"],
                    }

            logger.info(f"Loaded {len(self.vertical_features)} vertical features")

        except Exception as e:
            logger.error(f"Failed to load vertical features: {e}")

    def get_geo_bucket(self, zip_code: str) -> Optional[str]:
        """
        Get geo bucket for a ZIP code

        Args:
            zip_code: 5-digit ZIP code

        Returns:
            Geo bucket string or None if not found
        """
        features = self.geo_features.get(zip_code)
        if not features:
            return None

        return f"{features['affluence']}-{features['agency_density']}-{features['broadband_quality']}"

    def get_vertical_bucket(self, categories: List[str]) -> Optional[str]:
        """
        Get vertical bucket for a list of Yelp categories

        Uses the first matching category found

        Args:
            categories: List of Yelp category slugs

        Returns:
            Vertical bucket string or None if no match
        """
        for category in categories:
            features = self.vertical_features.get(category)
            if features:
                return f"{features['urgency']}-{features['ticket_size']}-{features['maturity']}"

        return None

    def get_business_buckets(self, zip_code: str, categories: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Get both geo and vertical buckets for a business

        Args:
            zip_code: Business ZIP code
            categories: List of business categories

        Returns:
            Tuple of (geo_bucket, vertical_bucket)
        """
        geo_bucket = self.get_geo_bucket(zip_code)
        vert_bucket = self.get_vertical_bucket(categories)

        return geo_bucket, vert_bucket

    def enrich_business(self, business: Dict) -> Dict:
        """
        Add bucket fields to a business dictionary

        Args:
            business: Business data with zip_code and categories

        Returns:
            Business dict with geo_bucket and vert_bucket added
        """
        zip_code = business.get("zip_code", "")
        categories = business.get("categories", [])

        # Handle categories that might be a string
        if isinstance(categories, str):
            categories = [categories]

        geo_bucket, vert_bucket = self.get_business_buckets(zip_code, categories)

        business["geo_bucket"] = geo_bucket
        business["vert_bucket"] = vert_bucket

        return business

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about loaded features"""
        # Count unique buckets
        unique_geo_buckets = set()
        for features in self.geo_features.values():
            bucket = f"{features['affluence']}-{features['agency_density']}-{features['broadband_quality']}"
            unique_geo_buckets.add(bucket)

        unique_vert_buckets = set()
        for features in self.vertical_features.values():
            bucket = f"{features['urgency']}-{features['ticket_size']}-{features['maturity']}"
            unique_vert_buckets.add(bucket)

        return {
            "total_zip_codes": len(self.geo_features),
            "total_categories": len(self.vertical_features),
            "unique_geo_buckets": len(unique_geo_buckets),
            "unique_vert_buckets": len(unique_vert_buckets),
            "geo_bucket_list": sorted(unique_geo_buckets),
            "vert_bucket_list": sorted(unique_vert_buckets),
        }


# Singleton instance
_bucket_loader: Optional[BucketFeatureLoader] = None


def get_bucket_loader() -> BucketFeatureLoader:
    """Get or create the singleton bucket loader instance"""
    global _bucket_loader
    if _bucket_loader is None:
        _bucket_loader = BucketFeatureLoader()
    return _bucket_loader
