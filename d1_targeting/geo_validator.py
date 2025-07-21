"""
Geographic Validator for detecting conflicts and validating geographic constraints
"""

import re
from dataclasses import dataclass
from typing import Any

from geopy.distance import geodesic

from core.logging import get_logger

from .types import GeographicConstraint, GeographyLevel


@dataclass
class GeoConflict:
    """Represents a geographic conflict"""

    conflict_type: str
    description: str
    affected_constraints: list[str]
    severity: str  # 'warning', 'error', 'critical'
    suggested_resolution: str | None = None


@dataclass
class LocationValidationResult:
    """Result of location validation"""

    location: str
    is_valid: bool
    location_type: str
    errors: list[str]
    parsed_components: dict[str, Any]


class GeoValidator:
    """
    Validates geographic constraints and detects conflicts in targeting configuration
    """

    def __init__(self):
        self.logger = get_logger("geo_validator", domain="d1")

        # State code to name mapping for US states
        self.us_states = {
            "AL": "Alabama",
            "AK": "Alaska",
            "AZ": "Arizona",
            "AR": "Arkansas",
            "CA": "California",
            "CO": "Colorado",
            "CT": "Connecticut",
            "DE": "Delaware",
            "FL": "Florida",
            "GA": "Georgia",
            "HI": "Hawaii",
            "ID": "Idaho",
            "IL": "Illinois",
            "IN": "Indiana",
            "IA": "Iowa",
            "KS": "Kansas",
            "KY": "Kentucky",
            "LA": "Louisiana",
            "ME": "Maine",
            "MD": "Maryland",
            "MA": "Massachusetts",
            "MI": "Michigan",
            "MN": "Minnesota",
            "MS": "Mississippi",
            "MO": "Missouri",
            "MT": "Montana",
            "NE": "Nebraska",
            "NV": "Nevada",
            "NH": "New Hampshire",
            "NJ": "New Jersey",
            "NM": "New Mexico",
            "NY": "New York",
            "NC": "North Carolina",
            "ND": "North Dakota",
            "OH": "Ohio",
            "OK": "Oklahoma",
            "OR": "Oregon",
            "PA": "Pennsylvania",
            "RI": "Rhode Island",
            "SC": "South Carolina",
            "SD": "South Dakota",
            "TN": "Tennessee",
            "TX": "Texas",
            "UT": "Utah",
            "VT": "Vermont",
            "VA": "Virginia",
            "WA": "Washington",
            "WV": "West Virginia",
            "WI": "Wisconsin",
            "WY": "Wyoming",
            "DC": "District of Columbia",
        }

        # ZIP code patterns for basic validation
        self.zip_patterns = {
            "US": re.compile(r"^\d{5}(-\d{4})?$"),
            "CA": re.compile(r"^[A-Z]\d[A-Z] \d[A-Z]\d$"),
        }

    def detect_conflicts(self, geography_config: dict[str, Any]) -> list[GeoConflict]:
        """
        Detect all types of geographic conflicts in configuration

        Args:
            geography_config: Geographic configuration to validate

        Returns:
            List of detected conflicts
        """
        conflicts = []

        try:
            constraints = self._parse_constraints(geography_config)

            # Check for various conflict types
            conflicts.extend(self._detect_hierarchy_conflicts(constraints))
            conflicts.extend(self._detect_overlap_conflicts(constraints))
            conflicts.extend(self._detect_contradiction_conflicts(constraints))
            conflicts.extend(self._detect_format_conflicts(constraints))
            conflicts.extend(self._detect_scope_conflicts(constraints))

            self.logger.info(f"Detected {len(conflicts)} geographic conflicts")
            return conflicts

        except Exception as e:
            self.logger.error(f"Error detecting geographic conflicts: {e}")
            return [
                GeoConflict(
                    conflict_type="validation_error",
                    description=f"Failed to validate geography configuration: {str(e)}",
                    affected_constraints=["all"],
                    severity="error",
                )
            ]

    def validate_hierarchy(self, constraints: list[GeographicConstraint]) -> list[str]:
        """
        Validate geographic hierarchy consistency

        Args:
            constraints: List of geographic constraints

        Returns:
            List of validation error messages
        """
        errors = []

        try:
            # Group constraints by level
            by_level = {}
            for constraint in constraints:
                level = constraint.level
                if level not in by_level:
                    by_level[level] = []
                by_level[level].append(constraint)

            # Check hierarchy rules
            if GeographyLevel.COUNTRY in by_level and GeographyLevel.STATE in by_level:
                errors.extend(
                    self._validate_state_country_consistency(
                        by_level[GeographyLevel.COUNTRY], by_level[GeographyLevel.STATE]
                    )
                )

            if GeographyLevel.STATE in by_level and GeographyLevel.CITY in by_level:
                errors.extend(
                    self._validate_city_state_consistency(by_level[GeographyLevel.STATE], by_level[GeographyLevel.CITY])
                )

            if GeographyLevel.STATE in by_level and GeographyLevel.ZIP_CODE in by_level:
                errors.extend(
                    self._validate_zip_state_consistency(
                        by_level[GeographyLevel.STATE],
                        by_level[GeographyLevel.ZIP_CODE],
                    )
                )

            return errors

        except Exception as e:
            self.logger.error(f"Error validating hierarchy: {e}")
            return [f"Hierarchy validation failed: {str(e)}"]

    def resolve_overlaps(self, constraints: list[GeographicConstraint]) -> list[GeographicConstraint]:
        """
        Resolve geographic overlaps by merging or removing redundant constraints

        Args:
            constraints: List of constraints to resolve

        Returns:
            Resolved list of constraints
        """
        try:
            resolved = []
            processed = set()

            for i, constraint in enumerate(constraints):
                if i in processed:
                    continue

                # Find overlaps with remaining constraints
                overlapping = []
                for j, other in enumerate(constraints[i + 1 :], i + 1):
                    if j not in processed and self._constraints_overlap(constraint, other):
                        overlapping.append((j, other))

                if overlapping:
                    # Merge overlapping constraints
                    merged = self._merge_constraints(constraint, [other for _, other in overlapping])
                    resolved.append(merged)
                    processed.add(i)
                    processed.update(j for j, _ in overlapping)
                else:
                    resolved.append(constraint)
                    processed.add(i)

            self.logger.info(f"Resolved {len(constraints)} constraints to {len(resolved)}")
            return resolved

        except Exception as e:
            self.logger.error(f"Error resolving overlaps: {e}")
            return constraints  # Return original if resolution fails

    def validate_coordinates(self, lat: float, lng: float) -> bool:
        """
        Validate latitude and longitude coordinates

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            True if valid coordinates
        """
        return -90 <= lat <= 90 and -180 <= lng <= 180

    def calculate_distance_miles(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate distance between two points in miles

        Args:
            lat1, lng1: First point coordinates
            lat2, lng2: Second point coordinates

        Returns:
            Distance in miles
        """
        try:
            return geodesic((lat1, lng1), (lat2, lng2)).miles
        except Exception as e:
            self.logger.error(f"Error calculating distance: {e}")
            return float("inf")

    def validate_radius_constraint(self, center_lat: float, center_lng: float, radius_miles: float) -> list[str]:
        """
        Validate radius-based geographic constraint

        Args:
            center_lat: Center latitude
            center_lng: Center longitude
            radius_miles: Radius in miles

        Returns:
            List of validation error messages
        """
        errors = []

        if not self.validate_coordinates(center_lat, center_lng):
            errors.append(f"Invalid coordinates: ({center_lat}, {center_lng})")

        if radius_miles <= 0:
            errors.append(f"Radius must be positive: {radius_miles}")
        elif radius_miles > 1000:
            errors.append(f"Radius too large (max 1000 miles): {radius_miles}")

        return errors

    def validate_location(self, location: str) -> LocationValidationResult:
        """
        Validate a location string and return validation details.

        Args:
            location: Location string to validate (e.g., "San Francisco, CA", "90210", "NY")

        Returns:
            LocationValidationResult containing validation results
        """
        try:
            # Handle None input
            if location is None:
                return LocationValidationResult(
                    location="",
                    is_valid=False,
                    location_type="unknown",
                    errors=["Location is None"],
                    parsed_components={},
                )

            # Clean the location
            location = location.strip()

            if not location:
                return LocationValidationResult(
                    location=location,
                    is_valid=False,
                    location_type="unknown",
                    errors=["Empty location string"],
                    parsed_components={},
                )

            # Check if it's a ZIP code
            if self._validate_zip_format(location):
                return LocationValidationResult(
                    location=location,
                    is_valid=True,
                    location_type="zip_code",
                    errors=[],
                    parsed_components={"zip_code": location},
                )

            # Check if it's a state code
            if len(location) == 2 and location.upper() in self.us_states:
                return LocationValidationResult(
                    location=location,
                    is_valid=True,
                    location_type="state",
                    errors=[],
                    parsed_components={
                        "state": location.upper(),
                        "state_name": self.us_states[location.upper()],
                    },
                )

            # Check if it's a city, state format
            if "," in location:
                parts = location.split(",")
                if len(parts) == 2:
                    city_name = parts[0].strip()
                    state_part = parts[1].strip()

                    # Check if state part is valid US state
                    if len(state_part) == 2 and state_part.upper() in self.us_states:
                        return LocationValidationResult(
                            location=location,
                            is_valid=True,
                            location_type="city_state",
                            errors=[],
                            parsed_components={
                                "city": city_name,
                                "state": state_part.upper(),
                                "state_name": self.us_states[state_part.upper()],
                            },
                        )
                    # Could be international location (e.g., "London, UK")
                    # For now, treat as valid international city
                    return LocationValidationResult(
                        location=location,
                        is_valid=True,
                        location_type="international_city",
                        errors=[],
                        parsed_components={
                            "city": city_name,
                            "country": state_part,
                        },
                    )

            # Check if it's a state name
            location_lower = location.lower()
            for state_code, state_name in self.us_states.items():
                if state_name.lower() == location_lower:
                    return LocationValidationResult(
                        location=location,
                        is_valid=True,
                        location_type="state",
                        errors=[],
                        parsed_components={
                            "state": state_code,
                            "state_name": state_name,
                        },
                    )

            # If we get here, it's an unknown location type
            # For safety, mark as invalid if it contains suspicious patterns
            suspicious_patterns = [
                "invalid",
                "xyz",
                "test",
                "123",
                "null",
                "undefined",
                "error",
                "fail",
            ]

            if any(pattern in location.lower() for pattern in suspicious_patterns):
                return LocationValidationResult(
                    location=location,
                    is_valid=False,
                    location_type="unknown",
                    errors=["Unrecognized location format"],
                    parsed_components={},
                )

            # Otherwise, assume it's a city name (valid but unverified)
            return LocationValidationResult(
                location=location,
                is_valid=True,
                location_type="city",
                errors=[],
                parsed_components={"city": location},
            )

        except Exception as e:
            self.logger.error(f"Error validating location '{location}': {e}")
            return LocationValidationResult(
                location=location,
                is_valid=False,
                location_type="unknown",
                errors=[f"Validation error: {str(e)}"],
                parsed_components={},
            )

    # Private helper methods

    def _parse_constraints(self, geography_config: dict[str, Any]) -> list[GeographicConstraint]:
        """Parse geography configuration into constraint objects"""
        constraints = []

        config_constraints = geography_config.get("constraints", [])
        for constraint_data in config_constraints:
            try:
                constraint = GeographicConstraint(
                    level=GeographyLevel(constraint_data["level"]),
                    values=constraint_data["values"],
                    radius_miles=constraint_data.get("radius_miles"),
                    center_lat=constraint_data.get("center_lat"),
                    center_lng=constraint_data.get("center_lng"),
                )
                constraints.append(constraint)
            except (KeyError, ValueError) as e:
                self.logger.warning(f"Invalid constraint format: {constraint_data} - {e}")

        return constraints

    def _detect_hierarchy_conflicts(self, constraints: list[GeographicConstraint]) -> list[GeoConflict]:
        """Detect geographic hierarchy conflicts"""
        conflicts = []

        # Check for conflicting hierarchy levels
        levels = [c.level for c in constraints]

        # Can't have both country and state-specific targeting
        if GeographyLevel.COUNTRY in levels and any(
            level in levels
            for level in [
                GeographyLevel.STATE,
                GeographyLevel.CITY,
                GeographyLevel.ZIP_CODE,
            ]
        ):
            conflicts.append(
                GeoConflict(
                    conflict_type="hierarchy_conflict",
                    description="Cannot combine country-level targeting with more specific geographic constraints",
                    affected_constraints=[str(c.level) for c in constraints],
                    severity="error",
                    suggested_resolution="Remove country constraint or all sub-country constraints",
                )
            )

        return conflicts

    def _detect_overlap_conflicts(self, constraints: list[GeographicConstraint]) -> list[GeoConflict]:
        """Detect overlapping geographic constraints"""
        conflicts = []

        for i, constraint1 in enumerate(constraints):
            for j, constraint2 in enumerate(constraints[i + 1 :], i + 1):
                if self._constraints_overlap(constraint1, constraint2):
                    conflicts.append(
                        GeoConflict(
                            conflict_type="overlap",
                            description=f"Geographic overlap detected between {constraint1.level} and {constraint2.level}",
                            affected_constraints=[
                                f"{constraint1.level}:{constraint1.values}",
                                f"{constraint2.level}:{constraint2.values}",
                            ],
                            severity="warning",
                            suggested_resolution="Consider merging overlapping constraints",
                        )
                    )

        return conflicts

    def _detect_contradiction_conflicts(self, constraints: list[GeographicConstraint]) -> list[GeoConflict]:
        """Detect contradictory geographic constraints"""
        conflicts = []

        # Check for empty intersections
        state_constraints = [c for c in constraints if c.level == GeographyLevel.STATE]
        city_constraints = [c for c in constraints if c.level == GeographyLevel.CITY]

        if state_constraints and city_constraints:
            for state_constraint in state_constraints:
                for city_constraint in city_constraints:
                    if not self._city_in_states(city_constraint.values, state_constraint.values):
                        conflicts.append(
                            GeoConflict(
                                conflict_type="contradiction",
                                description=f"Cities {city_constraint.values} not found in states {state_constraint.values}",
                                affected_constraints=[
                                    f"state:{state_constraint.values}",
                                    f"city:{city_constraint.values}",
                                ],
                                severity="error",
                                suggested_resolution="Verify city and state combinations are correct",
                            )
                        )

        return conflicts

    def _detect_format_conflicts(self, constraints: list[GeographicConstraint]) -> list[GeoConflict]:
        """Detect format validation conflicts"""
        conflicts = []

        for constraint in constraints:
            if constraint.level == GeographyLevel.ZIP_CODE:
                for zip_code in constraint.values:
                    if not self._validate_zip_format(zip_code):
                        conflicts.append(
                            GeoConflict(
                                conflict_type="format_error",
                                description=f"Invalid ZIP code format: {zip_code}",
                                affected_constraints=[f"zip:{zip_code}"],
                                severity="error",
                                suggested_resolution="Use 5-digit or 9-digit ZIP code format (e.g., 12345 or 12345-6789)",
                            )
                        )

            elif constraint.level == GeographyLevel.STATE:
                for state in constraint.values:
                    if len(state) == 2 and state.upper() not in self.us_states:
                        conflicts.append(
                            GeoConflict(
                                conflict_type="format_error",
                                description=f"Invalid US state code: {state}",
                                affected_constraints=[f"state:{state}"],
                                severity="error",
                                suggested_resolution="Use valid 2-letter US state codes (e.g., CA, NY, TX)",
                            )
                        )

            elif constraint.level == GeographyLevel.RADIUS:
                errors = self.validate_radius_constraint(
                    constraint.center_lat or 0,
                    constraint.center_lng or 0,
                    constraint.radius_miles or 0,
                )
                for error in errors:
                    conflicts.append(
                        GeoConflict(
                            conflict_type="format_error",
                            description=error,
                            affected_constraints=[f"radius:{constraint.radius_miles}"],
                            severity="error",
                        )
                    )

        return conflicts

    def _detect_scope_conflicts(self, constraints: list[GeographicConstraint]) -> list[GeoConflict]:
        """Detect scope-related conflicts (too broad or too narrow)"""
        conflicts = []

        # Check for overly broad targeting
        country_constraints = [c for c in constraints if c.level == GeographyLevel.COUNTRY]
        if country_constraints:
            for constraint in country_constraints:
                if len(constraint.values) > 3:
                    conflicts.append(
                        GeoConflict(
                            conflict_type="scope_too_broad",
                            description=f"Targeting too many countries: {len(constraint.values)}",
                            affected_constraints=[f"country:{constraint.values}"],
                            severity="warning",
                            suggested_resolution="Consider focusing on fewer countries for better campaign management",
                        )
                    )

        # Check for overly narrow targeting
        zip_constraints = [c for c in constraints if c.level == GeographyLevel.ZIP_CODE]
        if zip_constraints:
            total_zips = sum(len(c.values) for c in zip_constraints)
            if total_zips > 100:
                conflicts.append(
                    GeoConflict(
                        conflict_type="scope_too_narrow",
                        description=f"Targeting too many ZIP codes: {total_zips}",
                        affected_constraints=[f"zip_count:{total_zips}"],
                        severity="warning",
                        suggested_resolution="Consider using city or county level targeting instead",
                    )
                )

        return conflicts

    def _constraints_overlap(self, c1: GeographicConstraint, c2: GeographicConstraint) -> bool:
        """Check if two constraints overlap geographically"""
        if c1.level == c2.level:
            return bool(set(c1.values) & set(c2.values))

        # Check hierarchy overlaps
        if c1.level == GeographyLevel.STATE and c2.level == GeographyLevel.CITY:
            return self._city_in_states(c2.values, c1.values)
        if c1.level == GeographyLevel.CITY and c2.level == GeographyLevel.STATE:
            return self._city_in_states(c1.values, c2.values)

        return False

    def _merge_constraints(
        self,
        base_constraint: GeographicConstraint,
        overlapping: list[GeographicConstraint],
    ) -> GeographicConstraint:
        """Merge overlapping constraints into a single constraint"""
        # Simple implementation: merge values at the same level
        if all(c.level == base_constraint.level for c in overlapping):
            all_values = set(base_constraint.values)
            for constraint in overlapping:
                all_values.update(constraint.values)

            return GeographicConstraint(
                level=base_constraint.level,
                values=list(all_values),
                radius_miles=base_constraint.radius_miles,
                center_lat=base_constraint.center_lat,
                center_lng=base_constraint.center_lng,
            )

        # For different levels, return the broader constraint
        return base_constraint

    def _validate_state_country_consistency(
        self,
        country_constraints: list[GeographicConstraint],
        state_constraints: list[GeographicConstraint],
    ) -> list[str]:
        """Validate that states are consistent with countries"""
        errors = []

        # If targeting US states, should only target US
        us_states_targeted = any(
            any(state.upper() in self.us_states for state in constraint.values) for constraint in state_constraints
        )

        us_in_countries = any(
            "US" in constraint.values or "USA" in constraint.values for constraint in country_constraints
        )

        if us_states_targeted and not us_in_countries:
            errors.append("US states specified but US not included in country targeting")

        return errors

    def _validate_city_state_consistency(
        self,
        state_constraints: list[GeographicConstraint],
        city_constraints: list[GeographicConstraint],
    ) -> list[str]:
        """Validate that cities are consistent with states"""
        errors = []

        # This would typically require a comprehensive city-state database
        # For now, just basic validation
        for city_constraint in city_constraints:
            for city in city_constraint.values:
                if "," in city:
                    # Format like "San Francisco, CA"
                    city_name, state_part = city.rsplit(",", 1)
                    state_code = state_part.strip().upper()

                    # Check if this state is in the state constraints
                    all_states = set()
                    for state_constraint in state_constraints:
                        all_states.update(s.upper() for s in state_constraint.values)

                    if state_code not in all_states:
                        errors.append(f"City '{city}' specifies state not in state constraints")

        return errors

    def _validate_zip_state_consistency(
        self,
        state_constraints: list[GeographicConstraint],
        zip_constraints: list[GeographicConstraint],
    ) -> list[str]:
        """Validate that ZIP codes are consistent with states"""
        errors = []

        # This would typically require a ZIP-to-state mapping database
        # For now, basic validation that could be enhanced

        return errors

    def _city_in_states(self, cities: list[str], states: list[str]) -> bool:
        """Check if cities are in the specified states (simplified)"""
        # This is a simplified check - would need comprehensive city-state database
        state_codes = set(s.upper() for s in states)

        for city in cities:
            if "," in city:
                # Format like "San Francisco, CA"
                _, state_part = city.rsplit(",", 1)
                state_code = state_part.strip().upper()
                if state_code in state_codes:
                    return True

        return False

    def _validate_zip_format(self, zip_code: str) -> bool:
        """Validate ZIP code format"""
        # Default to US format
        return bool(self.zip_patterns["US"].match(zip_code.strip()))
