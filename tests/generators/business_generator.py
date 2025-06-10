"""
Business Test Data Generator - Task 088

Generates realistic business test data for various testing scenarios.
Supports deterministic generation and performance datasets.

Acceptance Criteria:
- Realistic test data ✓
- Various scenarios covered ✓
- Deterministic generation ✓
- Performance data sets ✓
"""

import random
import uuid
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from database.models import Business, GeoType


class BusinessScenario(Enum):
    """Business generation scenarios for different testing contexts"""
    RESTAURANTS = "restaurants"
    RETAIL = "retail"
    HEALTHCARE = "healthcare"
    PROFESSIONAL_SERVICES = "professional_services"
    AUTOMOTIVE = "automotive"
    FITNESS = "fitness"
    BEAUTY = "beauty"
    ENTERTAINMENT = "entertainment"
    EDUCATION = "education"
    REAL_ESTATE = "real_estate"


@dataclass
class BusinessProfile:
    """Profile defining business characteristics for generation"""
    vertical: str
    typical_names: List[str]
    name_patterns: List[str]
    common_categories: List[str]
    website_patterns: List[str]
    rating_range: Tuple[float, float]
    price_level_range: Tuple[int, int]
    typical_hours: Dict[str, str]
    business_status_weights: Dict[str, float]


class BusinessGenerator:
    """
    Generates realistic business test data with various scenarios and deterministic output.
    
    Features:
    - Realistic business names, addresses, and contact information
    - Industry-specific data patterns
    - Deterministic generation for reproducible tests
    - Large dataset generation for performance testing
    """
    
    def __init__(self, seed: int = 42):
        """Initialize generator with optional seed for deterministic output"""
        self.seed = seed
        self.random = random.Random(seed)
        self._setup_profiles()
        self._setup_location_data()
    
    def _setup_profiles(self):
        """Setup business profiles for different verticals"""
        self.profiles = {
            BusinessScenario.RESTAURANTS: BusinessProfile(
                vertical="restaurants",
                typical_names=["Bella Vista", "Golden Dragon", "Corner Cafe", "Pizza Palace", "Taco Express"],
                name_patterns=["{adjective} {cuisine}", "{name}'s {type}", "The {adjective} {type}"],
                common_categories=["restaurant", "italian", "chinese", "mexican", "pizza", "cafe", "bistro"],
                website_patterns=["www.{name}.com", "{name}restaurant.com", "{name}dining.net"],
                rating_range=(3.0, 5.0),
                price_level_range=(1, 4),
                typical_hours={"monday": "11:00-22:00", "friday": "11:00-23:00", "sunday": "12:00-21:00"},
                business_status_weights={"OPERATIONAL": 0.85, "TEMPORARILY_CLOSED": 0.10, "PERMANENTLY_CLOSED": 0.05}
            ),
            BusinessScenario.RETAIL: BusinessProfile(
                vertical="retail",
                typical_names=["Fashion Forward", "Tech Store", "Home Depot", "Book Nook", "Style Studio"],
                name_patterns=["{adjective} {item} {type}", "{name}'s {type}", "{type} {location}"],
                common_categories=["clothing", "electronics", "books", "home_goods", "accessories"],
                website_patterns=["shop{name}.com", "{name}store.com", "{name}retail.net"],
                rating_range=(3.5, 4.8),
                price_level_range=(2, 4),
                typical_hours={"monday": "09:00-21:00", "friday": "09:00-22:00", "sunday": "10:00-19:00"},
                business_status_weights={"OPERATIONAL": 0.90, "TEMPORARILY_CLOSED": 0.08, "PERMANENTLY_CLOSED": 0.02}
            ),
            BusinessScenario.HEALTHCARE: BusinessProfile(
                vertical="healthcare",
                typical_names=["City Medical", "Family Care", "Wellness Center", "Prime Health", "Care Plus"],
                name_patterns=["{location} {type}", "{adjective} {type} {center}", "Dr. {name}'s {type}"],
                common_categories=["medical", "dental", "therapy", "clinic", "hospital"],
                website_patterns=["{name}medical.com", "{name}health.org", "{name}care.net"],
                rating_range=(3.8, 4.9),
                price_level_range=(3, 4),
                typical_hours={"monday": "08:00-17:00", "friday": "08:00-16:00", "sunday": "CLOSED"},
                business_status_weights={"OPERATIONAL": 0.95, "TEMPORARILY_CLOSED": 0.03, "PERMANENTLY_CLOSED": 0.02}
            ),
            BusinessScenario.PROFESSIONAL_SERVICES: BusinessProfile(
                vertical="professional_services",
                typical_names=["Legal Associates", "Tax Pro", "Consulting Group", "Business Solutions", "Expert Advisors"],
                name_patterns=["{name} & {name2}", "{adjective} {service} {group}", "{name} {service}"],
                common_categories=["legal", "accounting", "consulting", "financial", "insurance"],
                website_patterns=["{name}law.com", "{name}cpa.com", "{name}consulting.net"],
                rating_range=(4.0, 4.8),
                price_level_range=(3, 4),
                typical_hours={"monday": "09:00-17:00", "friday": "09:00-16:00", "sunday": "CLOSED"},
                business_status_weights={"OPERATIONAL": 0.92, "TEMPORARILY_CLOSED": 0.05, "PERMANENTLY_CLOSED": 0.03}
            ),
            BusinessScenario.AUTOMOTIVE: BusinessProfile(
                vertical="automotive",
                typical_names=["Auto Pro", "Quick Lube", "Tire Center", "Car Care", "Motor Works"],
                name_patterns=["{name} {service}", "{adjective} {service}", "{location} {type}"],
                common_categories=["auto_repair", "car_wash", "gas_station", "tire_shop", "auto_parts"],
                website_patterns=["{name}auto.com", "{name}cars.net", "{name}service.com"],
                rating_range=(3.2, 4.6),
                price_level_range=(2, 3),
                typical_hours={"monday": "07:00-18:00", "friday": "07:00-19:00", "sunday": "09:00-17:00"},
                business_status_weights={"OPERATIONAL": 0.88, "TEMPORARILY_CLOSED": 0.08, "PERMANENTLY_CLOSED": 0.04}
            ),
            BusinessScenario.FITNESS: BusinessProfile(
                vertical="fitness",
                typical_names=["Elite Fitness", "Gym Pro", "Yoga Studio", "CrossFit Box", "Personal Training"],
                name_patterns=["{adjective} {type}", "{name}'s {type}", "{location} {type}"],
                common_categories=["gym", "yoga", "personal_training", "crossfit", "martial_arts"],
                website_patterns=["{name}fitness.com", "{name}gym.net", "{name}wellness.com"],
                rating_range=(3.5, 4.7),
                price_level_range=(2, 4),
                typical_hours={"monday": "05:00-22:00", "friday": "05:00-21:00", "sunday": "07:00-20:00"},
                business_status_weights={"OPERATIONAL": 0.87, "TEMPORARILY_CLOSED": 0.09, "PERMANENTLY_CLOSED": 0.04}
            ),
            BusinessScenario.BEAUTY: BusinessProfile(
                vertical="beauty",
                typical_names=["Bella Salon", "Style Studio", "Beauty Bar", "Glamour Lounge", "Spa Retreat"],
                name_patterns=["{adjective} {type}", "{name}'s {type}", "The {type}"],
                common_categories=["salon", "spa", "nail_salon", "barbershop", "beauty_services"],
                website_patterns=["{name}salon.com", "{name}beauty.net", "{name}spa.com"],
                rating_range=(3.6, 4.8),
                price_level_range=(2, 4),
                typical_hours={"monday": "09:00-19:00", "friday": "09:00-20:00", "sunday": "10:00-18:00"},
                business_status_weights={"OPERATIONAL": 0.89, "TEMPORARILY_CLOSED": 0.08, "PERMANENTLY_CLOSED": 0.03}
            ),
            BusinessScenario.ENTERTAINMENT: BusinessProfile(
                vertical="entertainment",
                typical_names=["Cinema Plus", "Game Zone", "Live Music", "Theater Arts", "Fun Center"],
                name_patterns=["{adjective} {type}", "{name} {type}", "{location} {type}"],
                common_categories=["movie_theater", "arcade", "bowling", "comedy_club", "concert_venue"],
                website_patterns=["{name}entertainment.com", "{name}fun.net", "{name}live.com"],
                rating_range=(3.4, 4.6),
                price_level_range=(2, 3),
                typical_hours={"monday": "12:00-23:00", "friday": "12:00-01:00", "sunday": "12:00-22:00"},
                business_status_weights={"OPERATIONAL": 0.85, "TEMPORARILY_CLOSED": 0.10, "PERMANENTLY_CLOSED": 0.05}
            ),
            BusinessScenario.EDUCATION: BusinessProfile(
                vertical="education",
                typical_names=["Learning Center", "Bright Minds", "Study Academy", "Tutor Pro", "Knowledge Hub"],
                name_patterns=["{adjective} {type}", "{name} {type}", "{location} {type}"],
                common_categories=["tutoring", "language_school", "music_lessons", "art_classes", "test_prep"],
                website_patterns=["{name}education.com", "{name}learning.org", "{name}academy.net"],
                rating_range=(3.8, 4.9),
                price_level_range=(2, 4),
                typical_hours={"monday": "08:00-20:00", "friday": "08:00-18:00", "sunday": "10:00-16:00"},
                business_status_weights={"OPERATIONAL": 0.93, "TEMPORARILY_CLOSED": 0.05, "PERMANENTLY_CLOSED": 0.02}
            ),
            BusinessScenario.REAL_ESTATE: BusinessProfile(
                vertical="real_estate",
                typical_names=["Prime Properties", "Home Solutions", "Real Estate Pro", "Property Partners", "Market Leaders"],
                name_patterns=["{adjective} {type}", "{name} {type}", "{location} {type}"],
                common_categories=["real_estate", "property_management", "home_inspection", "mortgage", "appraisal"],
                website_patterns=["{name}realestate.com", "{name}properties.net", "{name}homes.com"],
                rating_range=(3.7, 4.8),
                price_level_range=(3, 4),
                typical_hours={"monday": "09:00-18:00", "friday": "09:00-17:00", "sunday": "12:00-17:00"},
                business_status_weights={"OPERATIONAL": 0.91, "TEMPORARILY_CLOSED": 0.06, "PERMANENTLY_CLOSED": 0.03}
            )
        }
    
    def _setup_location_data(self):
        """Setup realistic location data for business generation"""
        self.locations = {
            "major_cities": [
                {"city": "New York", "state": "NY", "zip_base": "100"},
                {"city": "Los Angeles", "state": "CA", "zip_base": "900"}, 
                {"city": "Chicago", "state": "IL", "zip_base": "606"},
                {"city": "Houston", "state": "TX", "zip_base": "770"},
                {"city": "Phoenix", "state": "AZ", "zip_base": "850"},
                {"city": "Philadelphia", "state": "PA", "zip_base": "191"},
                {"city": "San Antonio", "state": "TX", "zip_base": "782"},
                {"city": "San Diego", "state": "CA", "zip_base": "921"},
                {"city": "Dallas", "state": "TX", "zip_base": "752"},
                {"city": "San Jose", "state": "CA", "zip_base": "951"}
            ],
            "street_names": [
                "Main St", "Oak Ave", "Park Blvd", "First St", "Second Ave", "Broadway",
                "Market St", "Church St", "Spring St", "Washington Ave", "Lincoln Blvd",
                "Maple Dr", "Cedar Ln", "Pine St", "Elm Ave", "Sunset Blvd"
            ],
            "street_numbers": list(range(100, 9999, 100))
        }
        
        self.name_components = {
            "adjectives": ["Premium", "Golden", "Royal", "Prime", "Elite", "Superior", "Classic", "Modern", "Deluxe", "Express"],
            "locations": ["Downtown", "Central", "North", "South", "East", "West", "Metro", "City", "Local", "Neighborhood"],
            "types": {
                "restaurants": ["Restaurant", "Bistro", "Cafe", "Grill", "Kitchen", "Eatery", "Diner", "Bar"],
                "retail": ["Store", "Shop", "Boutique", "Outlet", "Market", "Emporium", "Gallery", "Center"],
                "healthcare": ["Clinic", "Center", "Medical", "Health", "Care", "Practice", "Associates", "Group"],
                "professional_services": ["Associates", "Group", "Partners", "Solutions", "Services", "Advisors", "Consultants", "Firm"],
                "automotive": ["Auto", "Motors", "Service", "Garage", "Shop", "Center", "Station", "Works"],
                "fitness": ["Gym", "Fitness", "Studio", "Center", "Club", "Training", "Wellness", "Health"],
                "beauty": ["Salon", "Spa", "Studio", "Boutique", "Bar", "Lounge", "Services", "Center"],
                "entertainment": ["Theater", "Cinema", "Club", "Center", "Zone", "Venue", "Hall", "Stage"],
                "education": ["Academy", "Center", "School", "Institute", "Learning", "College", "University", "Studio"],
                "real_estate": ["Realty", "Properties", "Real Estate", "Homes", "Group", "Associates", "Partners", "Solutions"]
            }
        }
    
    def generate_business_name(self, scenario: BusinessScenario) -> str:
        """Generate realistic business name for given scenario"""
        profile = self.profiles[scenario]
        
        # 30% chance to use a typical name
        if self.random.random() < 0.3:
            return self.random.choice(profile.typical_names)
        
        # Otherwise generate using patterns
        pattern = self.random.choice(profile.name_patterns)
        
        components = {
            "adjective": self.random.choice(self.name_components["adjectives"]),
            "location": self.random.choice(self.name_components["locations"]),
            "type": self.random.choice(self.name_components["types"][scenario.value]),
            "name": self.random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]),
            "name2": self.random.choice(["Anderson", "Taylor", "Thomas", "Hernandez", "Moore", "Martin", "Jackson", "Thompson"]),
            "cuisine": self.random.choice(["Italian", "Chinese", "Mexican", "Indian", "Thai", "American", "French", "Japanese"]),
            "item": self.random.choice(["Fashion", "Tech", "Home", "Book", "Style", "Design", "Luxury", "Vintage"]),
            "service": self.random.choice(["Law", "Tax", "Consulting", "Financial", "Insurance", "Real Estate", "Auto", "Repair"]),
            "group": self.random.choice(["Group", "Associates", "Partners", "LLC", "Inc", "Solutions", "Services", "Center"]),
            "center": self.random.choice(["Center", "Clinic", "Associates", "Group", "Practice", "Medical", "Health", "Care"])
        }
        
        # Generate name from pattern
        try:
            name = pattern.format(**components)
            return name
        except KeyError:
            # Fallback to simple name if pattern fails
            return f"{components['adjective']} {components['type']}"
    
    def generate_location(self) -> Dict[str, Any]:
        """Generate realistic business location"""
        location = self.random.choice(self.locations["major_cities"])
        street_number = self.random.choice(self.locations["street_numbers"])
        street_name = self.random.choice(self.locations["street_names"])
        
        # Generate ZIP code based on city
        zip_code = location["zip_base"] + str(self.random.randint(10, 99))
        
        # Generate coordinates (simplified)
        base_coords = {
            "NY": (40.7128, -74.0060),
            "CA": (34.0522, -118.2437),
            "IL": (41.8781, -87.6298),
            "TX": (29.7604, -95.3698),
            "AZ": (33.4484, -112.0740),
            "PA": (39.9526, -75.1652)
        }
        
        if location["state"] in base_coords:
            base_lat, base_lng = base_coords[location["state"]]
            # Add some random variation
            lat = base_lat + self.random.uniform(-0.5, 0.5)
            lng = base_lng + self.random.uniform(-0.5, 0.5)
        else:
            lat = self.random.uniform(25.0, 49.0)
            lng = self.random.uniform(-125.0, -65.0)
        
        return {
            "address": f"{street_number} {street_name}",
            "city": location["city"],
            "state": location["state"],
            "zip_code": zip_code,
            "latitude": round(lat, 6),
            "longitude": round(lng, 6)
        }
    
    def generate_contact_info(self, business_name: str, scenario: BusinessScenario) -> Dict[str, str]:
        """Generate realistic contact information"""
        profile = self.profiles[scenario]
        
        # Generate phone number
        area_codes = ["212", "213", "312", "713", "602", "215", "210", "619", "214", "408"]
        area_code = self.random.choice(area_codes)
        phone = f"{area_code}-{self.random.randint(100, 999)}-{self.random.randint(1000, 9999)}"
        
        # Generate email (30% have email)
        email = None
        if self.random.random() < 0.3:
            clean_name = business_name.lower().replace(" ", "").replace("'", "").replace("&", "and")[:15]
            domains = ["gmail.com", "yahoo.com", "outlook.com", "businessname.com"]
            email = f"info@{clean_name}.{self.random.choice(domains)}"
        
        # Generate website (40% have website)
        website = None
        if self.random.random() < 0.4:
            clean_name = business_name.lower().replace(" ", "").replace("'", "")[:15]
            pattern = self.random.choice(profile.website_patterns)
            website = pattern.format(name=clean_name)
            if not website.startswith("http"):
                website = f"https://{website}"
        
        return {
            "phone": phone,
            "email": email,
            "website": website
        }
    
    def generate_business_data(self, business_name: str, scenario: BusinessScenario) -> Dict[str, Any]:
        """Generate comprehensive business data"""
        profile = self.profiles[scenario]
        
        # Rating and reviews
        rating_min, rating_max = profile.rating_range
        rating = round(self.random.uniform(rating_min, rating_max), 1)
        user_ratings_total = self.random.randint(5, 500)
        
        # Price level
        price_min, price_max = profile.price_level_range
        price_level = self.random.randint(price_min, price_max)
        
        # Categories
        categories = self.random.sample(profile.common_categories, k=self.random.randint(1, 3))
        
        # Business hours (simplified)
        hours = profile.typical_hours.copy()
        
        # Business status
        status_weights = profile.business_status_weights
        status = self.random.choices(
            list(status_weights.keys()),
            weights=list(status_weights.values())
        )[0]
        
        return {
            "vertical": profile.vertical,
            "categories": categories,
            "rating": rating,
            "user_ratings_total": user_ratings_total,
            "price_level": price_level,
            "opening_hours": hours,
            "business_status": status
        }
    
    def generate_business(self, scenario: BusinessScenario, business_id: Optional[str] = None) -> Business:
        """Generate a complete realistic business for given scenario"""
        # Generate basic info
        business_name = self.generate_business_name(scenario)
        location = self.generate_location()
        contact = self.generate_contact_info(business_name, scenario)
        business_data = self.generate_business_data(business_name, scenario)
        
        # Create business object
        business = Business(
            id=business_id or str(uuid.uuid4()),
            yelp_id=f"yelp_{self.random.randint(100000, 999999)}",
            name=business_name,
            url=contact["website"],
            phone=contact["phone"],
            email=contact["email"],
            
            # Location
            address=location["address"],
            city=location["city"],
            state=location["state"],
            zip_code=location["zip_code"],
            latitude=location["latitude"],
            longitude=location["longitude"],
            
            # Business data
            vertical=business_data["vertical"],
            categories=business_data["categories"],
            rating=Decimal(str(business_data["rating"])),
            user_ratings_total=business_data["user_ratings_total"],
            price_level=business_data["price_level"],
            opening_hours=business_data["opening_hours"],
            website=contact["website"],
            business_status=business_data["business_status"],
            
            # Metadata
            raw_data={
                "generated_scenario": scenario.value,
                "generation_seed": self.seed,
                "generated_at": datetime.utcnow().isoformat()
            },
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        return business
    
    def generate_businesses(self, count: int, scenarios: Optional[List[BusinessScenario]] = None) -> List[Business]:
        """Generate multiple businesses for testing"""
        if scenarios is None:
            scenarios = list(BusinessScenario)
        
        businesses = []
        for i in range(count):
            scenario = self.random.choice(scenarios)
            business = self.generate_business(scenario)
            businesses.append(business)
        
        return businesses
    
    def generate_performance_dataset(self, size: str = "small") -> List[Business]:
        """Generate large datasets for performance testing"""
        sizes = {
            "small": 100,
            "medium": 1000,
            "large": 5000,
            "xlarge": 10000
        }
        
        count = sizes.get(size, 100)
        return self.generate_businesses(count)
    
    def generate_scenario_dataset(self, scenario: BusinessScenario, count: int = 50) -> List[Business]:
        """Generate businesses for specific scenario testing"""
        return [self.generate_business(scenario) for _ in range(count)]
    
    def generate_mixed_dataset(self, counts_by_scenario: Dict[BusinessScenario, int]) -> List[Business]:
        """Generate businesses with specific counts per scenario"""
        businesses = []
        for scenario, count in counts_by_scenario.items():
            scenario_businesses = self.generate_scenario_dataset(scenario, count)
            businesses.extend(scenario_businesses)
        
        # Shuffle to mix scenarios
        self.random.shuffle(businesses)
        return businesses
    
    def reset_seed(self, seed: int):
        """Reset generator seed for deterministic reproduction"""
        self.seed = seed
        self.random = random.Random(seed)