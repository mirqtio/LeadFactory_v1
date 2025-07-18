"""
Unit tests for user preferences API endpoints
"""
import json
from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from account_management.models import AccountUser
from account_management.preference_models import PreferenceCategory, SearchType, UserPreference, SavedSearch
from main import app


class TestUserPreferencesAPI:
    """Test user preferences API endpoints"""

    def setup_method(self):
        """Set up test fixtures"""
        self.client = TestClient(app)
        self.mock_user = Mock(spec=AccountUser)
        self.mock_user.id = "test-user-123"
        self.mock_user.email = "test@example.com"
        self.mock_user.organization_id = "test-org-123"

    def test_create_user_preference_success(self, mocker):
        """Test successful user preference creation"""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None  # No existing preference
        
        # Mock preference creation
        mock_preference = Mock(spec=UserPreference)
        mock_preference.id = "pref-123"
        mock_preference.user_id = self.mock_user.id
        mock_preference.category = PreferenceCategory.DASHBOARD
        mock_preference.key = "theme"
        mock_preference.value = {"mode": "dark"}
        mock_preference.created_at = datetime.utcnow()
        mock_preference.updated_at = datetime.utcnow()
        
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Mock authentication
        mocker.patch("account_management.preference_api.get_current_user_dependency", return_value=self.mock_user)
        mocker.patch("account_management.preference_api.get_db", return_value=mock_db)
        
        # Make request
        response = self.client.post(
            "/api/v1/preferences/",
            json={
                "category": "dashboard",
                "key": "theme",
                "value": {"mode": "dark"},
                "description": "User theme preference"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 201
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_saved_search_success(self, mocker):
        """Test successful saved search creation"""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None  # No existing search
        
        # Mock search creation
        mock_search = Mock(spec=SavedSearch)
        mock_search.id = "search-123"
        mock_search.user_id = self.mock_user.id
        mock_search.name = "Test Search"
        mock_search.search_type = SearchType.LEAD_SEARCH
        mock_search.query_params = {"company_size": "small"}
        mock_search.created_at = datetime.utcnow()
        mock_search.updated_at = datetime.utcnow()
        
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Mock authentication
        mocker.patch("account_management.preference_api.get_current_user_dependency", return_value=self.mock_user)
        mocker.patch("account_management.preference_api.get_db", return_value=mock_db)
        
        # Make request
        response = self.client.post(
            "/api/v1/preferences/searches",
            json={
                "name": "Test Search",
                "search_type": "lead_search",
                "query_params": {"company_size": "small"},
                "description": "Search for small companies"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 201
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_list_user_preferences(self, mocker):
        """Test listing user preferences"""
        # Mock database session and query results
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = []
        
        # Mock distinct categories query
        mock_query.distinct.return_value.all.return_value = [(PreferenceCategory.DASHBOARD,)]
        
        # Mock authentication
        mocker.patch("account_management.preference_api.get_current_user_dependency", return_value=self.mock_user)
        mocker.patch("account_management.preference_api.get_db", return_value=mock_db)
        
        # Make request
        response = self.client.get(
            "/api/v1/preferences/",
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "preferences" in data
        assert "total" in data
        assert "categories" in data

    def test_track_user_activity(self, mocker):
        """Test activity tracking endpoint"""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None  # No existing activity
        
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        
        # Mock authentication
        mocker.patch("account_management.preference_api.get_current_user_dependency", return_value=self.mock_user)
        mocker.patch("account_management.preference_api.get_db", return_value=mock_db)
        
        # Make request
        response = self.client.post(
            "/api/v1/preferences/track-activity",
            params={
                "activity_type": "view",
                "resource_type": "lead",
                "resource_id": "lead-123"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Activity tracked successfully"

    def test_authentication_required(self):
        """Test that authentication is required for all endpoints"""
        # Test without Authorization header
        response = self.client.get("/api/v1/preferences/")
        assert response.status_code == 403  # Should require authentication

    def test_invalid_preference_category(self, mocker):
        """Test validation of preference category"""
        # Mock authentication
        mocker.patch("account_management.preference_api.get_current_user_dependency", return_value=self.mock_user)
        mocker.patch("account_management.preference_api.get_db", return_value=Mock())
        
        # Make request with invalid category
        response = self.client.post(
            "/api/v1/preferences/",
            json={
                "category": "invalid_category",
                "key": "test",
                "value": {"test": "value"}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Should return validation error
        assert response.status_code == 422

    def test_invalid_search_type(self, mocker):
        """Test validation of search type"""
        # Mock authentication
        mocker.patch("account_management.preference_api.get_current_user_dependency", return_value=self.mock_user)
        mocker.patch("account_management.preference_api.get_db", return_value=Mock())
        
        # Make request with invalid search type
        response = self.client.post(
            "/api/v1/preferences/searches",
            json={
                "name": "Test Search",
                "search_type": "invalid_type",
                "query_params": {"test": "value"}
            },
            headers={"Authorization": "Bearer test-token"}
        )
        
        # Should return validation error
        assert response.status_code == 422


class TestPreferenceModels:
    """Test preference model validations"""
    
    def test_preference_category_enum(self):
        """Test preference category enum values"""
        categories = [
            PreferenceCategory.DASHBOARD,
            PreferenceCategory.REPORTS,
            PreferenceCategory.NOTIFICATIONS,
            PreferenceCategory.SEARCH,
            PreferenceCategory.DISPLAY,
            PreferenceCategory.ANALYTICS,
            PreferenceCategory.EXPORT,
            PreferenceCategory.WORKFLOW,
        ]
        
        assert len(categories) == 8
        assert all(isinstance(cat, PreferenceCategory) for cat in categories)

    def test_search_type_enum(self):
        """Test search type enum values"""
        search_types = [
            SearchType.LEAD_SEARCH,
            SearchType.REPORT_SEARCH,
            SearchType.ANALYTICS_SEARCH,
            SearchType.CAMPAIGN_SEARCH,
            SearchType.ASSESSMENT_SEARCH,
        ]
        
        assert len(search_types) == 5
        assert all(isinstance(st, SearchType) for st in search_types)