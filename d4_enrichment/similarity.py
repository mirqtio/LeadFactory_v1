"""
Similarity algorithms for fuzzy matching - Task 041

Core similarity algorithms for matching business data across different sources.
Handles variations in business names, addresses, phone numbers, and other attributes.

Acceptance Criteria:
- Phone matching works
- Name/ZIP matching accurate
- Address similarity scoring
- Weighted combination logic
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Any


class SimilarityAlgorithm(Enum):
    """Available similarity algorithms"""

    EXACT = "exact"
    JACCARD = "jaccard"
    JARO_WINKLER = "jaro_winkler"
    LEVENSHTEIN = "levenshtein"
    SOUNDEX = "soundex"
    METAPHONE = "metaphone"
    NGRAM = "ngram"


@dataclass
class SimilarityResult:
    """Result of similarity comparison"""

    score: float
    algorithm: SimilarityAlgorithm
    normalized_input: str
    normalized_target: str
    metadata: dict[str, Any]


class PhoneSimilarity:
    """
    Phone number similarity scoring

    Acceptance Criteria: Phone matching works
    """

    @staticmethod
    def normalize_phone(phone: str) -> str:
        """Normalize phone number to digits only"""
        if not phone:
            return ""

        # Remove all non-digit characters
        digits = re.sub(r"[^\d]", "", phone)

        # Handle US numbers - remove leading 1 if 11 digits
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]

        return digits

    @staticmethod
    def extract_formats(phone: str) -> dict[str, str]:
        """Extract different phone number formats"""
        normalized = PhoneSimilarity.normalize_phone(phone)

        if len(normalized) == 10:
            return {
                "normalized": normalized,
                "area_code": normalized[:3],
                "exchange": normalized[3:6],
                "number": normalized[6:],
                "formatted": f"({normalized[:3]}) {normalized[3:6]}-{normalized[6:]}",
            }
        if len(normalized) >= 7:
            # Handle shorter numbers
            return {
                "normalized": normalized,
                "area_code": "",
                "exchange": normalized[:3] if len(normalized) >= 7 else "",
                "number": normalized[3:] if len(normalized) >= 7 else normalized,
                "formatted": normalized,
            }
        return {
            "normalized": normalized,
            "area_code": "",
            "exchange": "",
            "number": normalized,
            "formatted": normalized,
        }

    @classmethod
    def calculate_similarity(cls, phone1: str, phone2: str) -> SimilarityResult:
        """Calculate phone number similarity"""
        if not phone1 or not phone2:
            return SimilarityResult(
                score=0.0,
                algorithm=SimilarityAlgorithm.EXACT,
                normalized_input=phone1 or "",
                normalized_target=phone2 or "",
                metadata={"reason": "empty_input"},
            )

        norm1 = cls.normalize_phone(phone1)
        norm2 = cls.normalize_phone(phone2)

        # Exact match
        if norm1 == norm2:
            return SimilarityResult(
                score=1.0,
                algorithm=SimilarityAlgorithm.EXACT,
                normalized_input=norm1,
                normalized_target=norm2,
                metadata={"match_type": "exact"},
            )

        # Extract formats for partial matching
        fmt1 = cls.extract_formats(phone1)
        fmt2 = cls.extract_formats(phone2)

        # Check if one is substring of another (handles extensions, etc.)
        if norm1 in norm2 or norm2 in norm1:
            longer = max(norm1, norm2, key=len)
            shorter = min(norm1, norm2, key=len)
            score = len(shorter) / len(longer)
            return SimilarityResult(
                score=score,
                algorithm=SimilarityAlgorithm.EXACT,
                normalized_input=norm1,
                normalized_target=norm2,
                metadata={
                    "match_type": "substring",
                    "longer": longer,
                    "shorter": shorter,
                },
            )

        # Partial matching on components
        matches = 0
        total_components = 0

        if fmt1["area_code"] and fmt2["area_code"]:
            total_components += 1
            if fmt1["area_code"] == fmt2["area_code"]:
                matches += 1

        if fmt1["exchange"] and fmt2["exchange"]:
            total_components += 1
            if fmt1["exchange"] == fmt2["exchange"]:
                matches += 1

        if fmt1["number"] and fmt2["number"]:
            total_components += 1
            if fmt1["number"] == fmt2["number"]:
                matches += 1

        if total_components > 0:
            partial_score = matches / total_components
            return SimilarityResult(
                score=partial_score,
                algorithm=SimilarityAlgorithm.EXACT,
                normalized_input=norm1,
                normalized_target=norm2,
                metadata={
                    "match_type": "partial",
                    "matches": matches,
                    "total_components": total_components,
                    "components": {"phone1": fmt1, "phone2": fmt2},
                },
            )

        # No similarity
        return SimilarityResult(
            score=0.0,
            algorithm=SimilarityAlgorithm.EXACT,
            normalized_input=norm1,
            normalized_target=norm2,
            metadata={"match_type": "no_match"},
        )


class NameSimilarity:
    """
    Business name similarity scoring

    Acceptance Criteria: Name/ZIP matching accurate
    """

    # Common business suffix patterns
    BUSINESS_SUFFIXES = {
        "inc",
        "inc.",
        "incorporated",
        "llc",
        "l.l.c.",
        "l.l.c",
        "corp",
        "corp.",
        "corporation",
        "ltd",
        "ltd.",
        "limited",
        "co",
        "co.",
        "company",
        "plc",
        "p.l.c.",
        "public limited company",
        "lp",
        "l.p.",
        "limited partnership",
        "pllc",
        "p.l.l.c.",
        "professional limited liability company",
    }

    # Common business words that can be normalized
    BUSINESS_WORD_MAPPINGS = {
        "and": "&",
        "restaurant": "rest",
        "company": "co",
        "corporation": "corp",
        "incorporated": "inc",
        "limited": "ltd",
        "professional": "prof",
        "services": "svc",
        "service": "svc",
        "consulting": "consulting",
        "solutions": "sol",
    }

    @classmethod
    def normalize_name(cls, name: str) -> str:
        """Normalize business name for comparison"""
        if not name:
            return ""

        # Convert to lowercase and remove extra whitespace
        name = " ".join(name.lower().split())

        # Remove unicode accents
        name = unicodedata.normalize("NFKD", name)
        name = "".join(c for c in name if not unicodedata.combining(c))

        # Remove common punctuation but keep alphanumeric and spaces
        name = re.sub(r"[^\w\s&]", " ", name)

        # Split into words
        words = name.split()

        # Remove business suffixes
        filtered_words = []
        for word in words:
            if word not in cls.BUSINESS_SUFFIXES:
                # Apply word mappings
                word = cls.BUSINESS_WORD_MAPPINGS.get(word, word)
                filtered_words.append(word)

        # Rejoin and clean up
        normalized = " ".join(filtered_words)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        return normalized

    @classmethod
    def extract_name_tokens(cls, name: str) -> set[str]:
        """Extract meaningful tokens from business name"""
        normalized = cls.normalize_name(name)
        words = normalized.split()

        tokens = set()

        # Add individual words
        for word in words:
            if len(word) > 2:  # Skip very short words
                tokens.add(word)

        # Add bigrams for better matching
        for i in range(len(words) - 1):
            if len(words[i]) > 1 and len(words[i + 1]) > 1:
                bigram = f"{words[i]} {words[i + 1]}"
                tokens.add(bigram)

        return tokens

    @classmethod
    def calculate_similarity(cls, name1: str, name2: str) -> SimilarityResult:
        """Calculate business name similarity using multiple algorithms"""
        if not name1 or not name2:
            return SimilarityResult(
                score=0.0,
                algorithm=SimilarityAlgorithm.EXACT,
                normalized_input=name1 or "",
                normalized_target=name2 or "",
                metadata={"reason": "empty_input"},
            )

        norm1 = cls.normalize_name(name1)
        norm2 = cls.normalize_name(name2)

        # Exact match after normalization
        if norm1 == norm2:
            return SimilarityResult(
                score=1.0,
                algorithm=SimilarityAlgorithm.EXACT,
                normalized_input=norm1,
                normalized_target=norm2,
                metadata={"match_type": "exact_normalized"},
            )

        # Token-based Jaccard similarity
        tokens1 = cls.extract_name_tokens(name1)
        tokens2 = cls.extract_name_tokens(name2)

        if tokens1 or tokens2:
            intersection = tokens1.intersection(tokens2)
            union = tokens1.union(tokens2)
            jaccard_score = len(intersection) / len(union) if union else 0.0

            return SimilarityResult(
                score=jaccard_score,
                algorithm=SimilarityAlgorithm.JACCARD,
                normalized_input=norm1,
                normalized_target=norm2,
                metadata={
                    "match_type": "token_jaccard",
                    "tokens1": list(tokens1),
                    "tokens2": list(tokens2),
                    "intersection": list(intersection),
                    "union_size": len(union),
                    "intersection_size": len(intersection),
                },
            )

        # Fallback to character-level similarity
        char_score = cls._character_similarity(norm1, norm2)
        return SimilarityResult(
            score=char_score,
            algorithm=SimilarityAlgorithm.LEVENSHTEIN,
            normalized_input=norm1,
            normalized_target=norm2,
            metadata={"match_type": "character_similarity"},
        )

    @staticmethod
    def _character_similarity(s1: str, s2: str) -> float:
        """Calculate character-level similarity using Levenshtein distance"""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        # Simplified Levenshtein distance
        len1, len2 = len(s1), len(s2)
        if len1 < len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1

        if len2 == 0:
            return 0.0

        # Create distance matrix
        previous_row = list(range(len2 + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        distance = previous_row[-1]
        max_len = max(len1, len2)
        return 1.0 - (distance / max_len)


class AddressSimilarity:
    """
    Address similarity scoring

    Acceptance Criteria: Address similarity scoring
    """

    # Address component weights
    COMPONENT_WEIGHTS = {
        "street_number": 0.15,
        "street_name": 0.35,
        "city": 0.25,
        "state": 0.15,
        "zip": 0.10,
    }

    # Common street suffixes and their abbreviations
    STREET_SUFFIXES = {
        "street": ["st", "str"],
        "avenue": ["ave", "av"],
        "boulevard": ["blvd", "boul"],
        "drive": ["dr"],
        "lane": ["ln"],
        "road": ["rd"],
        "court": ["ct"],
        "place": ["pl"],
        "way": ["wy"],
        "circle": ["cir"],
        "square": ["sq"],
        "parkway": ["pkwy", "pky"],
    }

    @classmethod
    def normalize_address_component(cls, component: str, component_type: str = "general") -> str:
        """Normalize address component"""
        if not component:
            return ""

        # Basic normalization
        component = component.lower().strip()
        component = re.sub(r"[^\w\s]", " ", component)
        component = re.sub(r"\s+", " ", component)

        if component_type == "street":
            # Normalize street suffixes
            words = component.split()
            if words:
                last_word = words[-1]
                for full_suffix, abbreviations in cls.STREET_SUFFIXES.items():
                    if last_word == full_suffix or last_word in abbreviations:
                        words[-1] = full_suffix
                        break
                component = " ".join(words)

        return component

    @classmethod
    def parse_address(cls, address: str) -> dict[str, str]:
        """Parse address into components"""
        if not address:
            return {}

        # Simple address parsing (would be more sophisticated in production)
        address = address.strip()

        # Extract ZIP code (last 5 digits)
        zip_match = re.search(r"\b(\d{5}(?:-\d{4})?)\b", address)
        zip_code = zip_match.group(1) if zip_match else ""

        # Remove ZIP from address for further parsing
        if zip_code:
            address = address.replace(zip_code, "").strip()

        # Extract state (2-letter code before ZIP)
        state_match = re.search(r"\b([A-Z]{2})\s*$", address.upper())
        state = state_match.group(1) if state_match else ""

        # Remove state from address
        if state:
            address = re.sub(r"\b" + re.escape(state) + r"\s*$", "", address, flags=re.IGNORECASE).strip()

        # Split remaining into parts (very basic parsing)
        parts = [p.strip() for p in address.split(",")]

        if len(parts) >= 2:
            street = parts[0]
            city = parts[1]
        elif len(parts) == 1:
            # Assume it's all street if no comma
            street = parts[0]
            city = ""
        else:
            street = ""
            city = ""

        # Extract street number from street
        street_num_match = re.match(r"^(\d+)\s+(.+)", street)
        if street_num_match:
            street_number = street_num_match.group(1)
            street_name = street_num_match.group(2)
        else:
            street_number = ""
            street_name = street

        return {
            "street_number": street_number,
            "street_name": cls.normalize_address_component(street_name, "street"),
            "city": cls.normalize_address_component(city),
            "state": state.upper() if state else "",
            "zip": zip_code,
        }

    @classmethod
    def calculate_similarity(cls, address1: str, address2: str) -> SimilarityResult:
        """Calculate address similarity"""
        if not address1 or not address2:
            return SimilarityResult(
                score=0.0,
                algorithm=SimilarityAlgorithm.EXACT,
                normalized_input=address1 or "",
                normalized_target=address2 or "",
                metadata={"reason": "empty_input"},
            )

        parsed1 = cls.parse_address(address1)
        parsed2 = cls.parse_address(address2)

        component_scores = {}
        total_weight = 0.0
        weighted_score = 0.0

        for component, weight in cls.COMPONENT_WEIGHTS.items():
            val1 = parsed1.get(component, "")
            val2 = parsed2.get(component, "")

            if val1 or val2:
                total_weight += weight

                if val1 == val2:
                    component_score = 1.0
                elif val1 and val2:
                    # Use string similarity for non-exact matches
                    if component == "street_name" or component == "city":
                        component_score = NameSimilarity._character_similarity(val1, val2)
                    else:
                        component_score = 1.0 if val1 == val2 else 0.0
                else:
                    component_score = 0.0

                component_scores[component] = component_score
                weighted_score += component_score * weight

        final_score = weighted_score / total_weight if total_weight > 0 else 0.0

        return SimilarityResult(
            score=final_score,
            algorithm=SimilarityAlgorithm.EXACT,
            normalized_input=str(parsed1),
            normalized_target=str(parsed2),
            metadata={
                "match_type": "weighted_components",
                "parsed1": parsed1,
                "parsed2": parsed2,
                "component_scores": component_scores,
                "total_weight": total_weight,
                "weighted_score": weighted_score,
            },
        )


class ZipSimilarity:
    """
    ZIP code similarity scoring

    Acceptance Criteria: Name/ZIP matching accurate
    """

    @staticmethod
    def normalize_zip(zip_code: str) -> str:
        """Normalize ZIP code"""
        if not zip_code:
            return ""

        # Extract digits only
        digits = re.sub(r"[^\d]", "", zip_code)

        # Return first 5 digits for US ZIP codes
        return digits[:5] if len(digits) >= 5 else digits

    @classmethod
    def calculate_similarity(cls, zip1: str, zip2: str) -> SimilarityResult:
        """Calculate ZIP code similarity"""
        if not zip1 or not zip2:
            return SimilarityResult(
                score=0.0,
                algorithm=SimilarityAlgorithm.EXACT,
                normalized_input=zip1 or "",
                normalized_target=zip2 or "",
                metadata={"reason": "empty_input"},
            )

        norm1 = cls.normalize_zip(zip1)
        norm2 = cls.normalize_zip(zip2)

        if norm1 == norm2:
            return SimilarityResult(
                score=1.0,
                algorithm=SimilarityAlgorithm.EXACT,
                normalized_input=norm1,
                normalized_target=norm2,
                metadata={"match_type": "exact"},
            )

        # Check for partial matches (first 3 digits = same area)
        if len(norm1) >= 3 and len(norm2) >= 3:
            if norm1[:3] == norm2[:3]:
                return SimilarityResult(
                    score=0.7,
                    algorithm=SimilarityAlgorithm.EXACT,
                    normalized_input=norm1,
                    normalized_target=norm2,
                    metadata={"match_type": "area_match", "area": norm1[:3]},
                )

        return SimilarityResult(
            score=0.0,
            algorithm=SimilarityAlgorithm.EXACT,
            normalized_input=norm1,
            normalized_target=norm2,
            metadata={"match_type": "no_match"},
        )


class WeightedSimilarity:
    """
    Weighted combination of similarity scores

    Acceptance Criteria: Weighted combination logic
    """

    # Default weights for different attributes
    DEFAULT_WEIGHTS = {
        "business_name": 0.40,
        "phone": 0.25,
        "address": 0.20,
        "zip": 0.10,
        "domain": 0.05,
    }

    @classmethod
    def calculate_combined_similarity(
        cls,
        data1: dict[str, Any],
        data2: dict[str, Any],
        weights: dict[str, float] | None = None,
    ) -> SimilarityResult:
        """
        Calculate weighted combination of multiple similarity scores

        Acceptance Criteria: Weighted combination logic
        """
        if weights is None:
            weights = cls.DEFAULT_WEIGHTS.copy()

        component_results = {}
        total_weight = 0.0
        weighted_score = 0.0

        # Business name similarity
        if "business_name" in weights and weights["business_name"] > 0:
            name1 = data1.get("business_name", "") or data1.get("name", "")
            name2 = data2.get("business_name", "") or data2.get("name", "")

            if name1 or name2:
                name_result = NameSimilarity.calculate_similarity(name1, name2)
                component_results["business_name"] = name_result
                weight = weights["business_name"]
                total_weight += weight
                weighted_score += name_result.score * weight

        # Phone similarity
        if "phone" in weights and weights["phone"] > 0:
            phone1 = data1.get("phone", "")
            phone2 = data2.get("phone", "")

            if phone1 or phone2:
                phone_result = PhoneSimilarity.calculate_similarity(phone1, phone2)
                component_results["phone"] = phone_result
                weight = weights["phone"]
                total_weight += weight
                weighted_score += phone_result.score * weight

        # Address similarity
        if "address" in weights and weights["address"] > 0:
            addr1 = data1.get("address", "") or data1.get("full_address", "")
            addr2 = data2.get("address", "") or data2.get("full_address", "")

            if addr1 or addr2:
                addr_result = AddressSimilarity.calculate_similarity(addr1, addr2)
                component_results["address"] = addr_result
                weight = weights["address"]
                total_weight += weight
                weighted_score += addr_result.score * weight

        # ZIP code similarity
        if "zip" in weights and weights["zip"] > 0:
            zip1 = data1.get("zip", "") or data1.get("postal_code", "")
            zip2 = data2.get("zip", "") or data2.get("postal_code", "")

            if zip1 or zip2:
                zip_result = ZipSimilarity.calculate_similarity(zip1, zip2)
                component_results["zip"] = zip_result
                weight = weights["zip"]
                total_weight += weight
                weighted_score += zip_result.score * weight

        # Domain similarity (simple exact match for now)
        if "domain" in weights and weights["domain"] > 0:
            domain1 = data1.get("domain", "") or data1.get("website", "")
            domain2 = data2.get("domain", "") or data2.get("website", "")

            if domain1 or domain2:
                # Extract domain from URL if needed
                domain1 = cls._extract_domain(domain1)
                domain2 = cls._extract_domain(domain2)

                domain_score = 1.0 if domain1 == domain2 and domain1 else 0.0
                domain_result = SimilarityResult(
                    score=domain_score,
                    algorithm=SimilarityAlgorithm.EXACT,
                    normalized_input=domain1,
                    normalized_target=domain2,
                    metadata={"match_type": "domain_exact"},
                )
                component_results["domain"] = domain_result
                weight = weights["domain"]
                total_weight += weight
                weighted_score += domain_score * weight

        # Calculate final score
        final_score = weighted_score / total_weight if total_weight > 0 else 0.0

        return SimilarityResult(
            score=final_score,
            algorithm=SimilarityAlgorithm.EXACT,
            normalized_input=str(data1),
            normalized_target=str(data2),
            metadata={
                "match_type": "weighted_combination",
                "component_results": {k: v.score for k, v in component_results.items()},
                "weights": weights,
                "total_weight": total_weight,
                "weighted_score": weighted_score,
                "component_details": component_results,
            },
        )

    @staticmethod
    def _extract_domain(url_or_domain: str) -> str:
        """Extract domain from URL or return domain as-is"""
        if not url_or_domain:
            return ""

        # Remove protocol
        domain = re.sub(r"^https?://", "", url_or_domain.lower())

        # Remove www
        domain = re.sub(r"^www\.", "", domain)

        # Remove path and query parameters
        domain = domain.split("/")[0].split("?")[0]

        return domain.strip()
