"""
Google Places API Mock Factory

Provides realistic mock responses for Google Places API testing.
"""
from typing import Any, Dict

from tests.fixtures.mock_factory import MockFactory


class GooglePlacesMockFactory(MockFactory):
    """Mock factory for Google Places API responses."""

    @classmethod
    def create_success_response(cls, **overrides) -> Dict[str, Any]:
        """
        Create a successful place search response.

        Args:
            **overrides: Override default values

        Returns:
            Dict representing Google Places API response
        """
        base_response = {
            "results": [
                {
                    "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
                    "name": "Test Business",
                    "formatted_address": "123 Test St, San Francisco, CA 94105",
                    "geometry": {"location": {"lat": 37.7749, "lng": -122.4194}},
                    "types": ["restaurant", "food", "establishment"],
                    "rating": 4.5,
                    "user_ratings_total": 150,
                    "price_level": 2,
                    "opening_hours": {
                        "open_now": True,
                        "weekday_text": [
                            "Monday: 9:00 AM – 9:00 PM",
                            "Tuesday: 9:00 AM – 9:00 PM",
                            "Wednesday: 9:00 AM – 9:00 PM",
                            "Thursday: 9:00 AM – 9:00 PM",
                            "Friday: 9:00 AM – 10:00 PM",
                            "Saturday: 10:00 AM – 10:00 PM",
                            "Sunday: 10:00 AM – 8:00 PM",
                        ],
                    },
                    "photos": [{"height": 1080, "width": 1920, "photo_reference": "mock_photo_ref_123"}],
                }
            ],
            "status": "OK",
            "next_page_token": None,
        }

        # Apply overrides
        if "results" in overrides:
            base_response["results"] = overrides["results"]
            del overrides["results"]
        base_response.update(overrides)

        return base_response

    @classmethod
    def create_error_response(cls, error_type: str, **overrides) -> Dict[str, Any]:
        """
        Create an error response for various Google Places API errors.

        Args:
            error_type: Type of error (ZERO_RESULTS, INVALID_REQUEST, etc.)
            **overrides: Additional fields to include

        Returns:
            Dict representing error response
        """
        error_responses = {
            "ZERO_RESULTS": {"results": [], "status": "ZERO_RESULTS", "error_message": "No results found"},
            "INVALID_REQUEST": {
                "results": [],
                "status": "INVALID_REQUEST",
                "error_message": "Invalid request. Missing required parameters.",
            },
            "REQUEST_DENIED": {
                "results": [],
                "status": "REQUEST_DENIED",
                "error_message": "The provided API key is invalid.",
            },
            "OVER_QUERY_LIMIT": {
                "results": [],
                "status": "OVER_QUERY_LIMIT",
                "error_message": "You have exceeded your daily request quota for this API.",
            },
        }

        response = error_responses.get(error_type, error_responses["INVALID_REQUEST"])
        response.update(overrides)
        return response

    @classmethod
    def create_place_details_response(cls, place_id: str, **overrides) -> Dict[str, Any]:
        """Create a place details API response."""
        base_response = {
            "result": {
                "place_id": place_id,
                "name": "Detailed Test Business",
                "formatted_address": "123 Test St, San Francisco, CA 94105",
                "formatted_phone_number": "(415) 555-0123",
                "international_phone_number": "+1 415-555-0123",
                "website": "https://testbusiness.com",
                "url": "https://maps.google.com/?cid=123456",
                "vicinity": "Financial District",
                "types": ["restaurant", "food", "establishment"],
                "geometry": {"location": {"lat": 37.7749, "lng": -122.4194}},
                "rating": 4.5,
                "user_ratings_total": 150,
                "reviews": [
                    {
                        "author_name": "Test User",
                        "rating": 5,
                        "text": "Great place!",
                        "time": 1640995200,
                        "relative_time_description": "a month ago",
                    }
                ],
                "photos": [{"height": 1080, "width": 1920, "photo_reference": "mock_photo_ref_123"}],
            },
            "status": "OK",
        }

        if "result" in overrides:
            base_response["result"].update(overrides["result"])
            del overrides["result"]
        base_response.update(overrides)

        return base_response

    @classmethod
    def create_multiple_results(cls, count: int = 3, **overrides) -> Dict[str, Any]:
        """Create a response with multiple place results."""
        results = []
        for i in range(count):
            results.append(
                {
                    "place_id": f"test_place_id_{i}",
                    "name": f"Test Business {i + 1}",
                    "formatted_address": f"{100 + i} Test St, San Francisco, CA 94105",
                    "geometry": {"location": {"lat": 37.7749 + (i * 0.001), "lng": -122.4194 + (i * 0.001)}},
                    "types": ["restaurant", "food", "establishment"],
                    "rating": 4.0 + (i * 0.2),
                    "user_ratings_total": 100 + (i * 50),
                }
            )

        return cls.create_success_response(results=results, **overrides)

    @classmethod
    def create_nearby_search_response(cls, lat: float, lng: float, radius: int = 1000, **overrides) -> Dict[str, Any]:
        """Create a nearby search response."""
        # Generate places within radius
        results = []
        for i in range(3):
            results.append(
                {
                    "place_id": f"nearby_place_{i}",
                    "name": f"Nearby Business {i + 1}",
                    "vicinity": f"{100 + i} Nearby St",
                    "geometry": {"location": {"lat": lat + (i * 0.001), "lng": lng + (i * 0.001)}},
                    "types": ["restaurant", "food", "establishment"],
                    "rating": 4.2,
                    "opening_hours": {"open_now": i % 2 == 0},
                }
            )

        return cls.create_success_response(results=results, **overrides)

    @classmethod
    def create_text_search_response(cls, query: str, **overrides) -> Dict[str, Any]:
        """Create a text search response based on query."""
        # Simulate finding businesses based on query
        words = query.lower().split()
        business_type = "restaurant" if "restaurant" in words else "establishment"

        results = [
            {
                "place_id": "text_search_result_1",
                "name": f"{query.title()} Result",
                "formatted_address": "456 Search St, San Francisco, CA 94105",
                "geometry": {"location": {"lat": 37.7749, "lng": -122.4194}},
                "types": [business_type, "food", "establishment"],
                "rating": 4.3,
                "user_ratings_total": 200,
            }
        ]

        return cls.create_success_response(results=results, **overrides)

    @classmethod
    def create_photo_response(cls, photo_reference: str) -> bytes:
        """Create a mock photo response (returns minimal valid JPEG)."""
        # Minimal valid JPEG file (1x1 pixel, red)
        return (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08"
            b"\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e"
            b"\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0"
            b"\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00"
            b"\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10"
            b"\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01"
            b'\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1'
            b"\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&"
            b"'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87"
            b"\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5"
            b"\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3"
            b"\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda"
            b"\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6"
            b"\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd0\xd3"
            b"\xff\xd9"
        )
