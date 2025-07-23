#!/usr/bin/env python3
"""
Test AuthModule - with formatting issues
"""
import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from auth_module import AuthModule


class TestAuthModule:
    """Test auth module functionality"""

    def test_register_user(self):
        """Test user registration"""
        auth=AuthModule()
        result=auth.register_user("testuser","password123")
        assert result==True
        assert "testuser" in auth.users

    def test_duplicate_registration(self):
        """Test duplicate user registration fails"""
        auth = AuthModule()
        auth.register_user("testuser", "password123")
        result = auth.register_user("testuser", "password456")
        assert result == False

    def test_login_success(self):
        """Test successful login"""
        auth=AuthModule()
        auth.register_user("testuser","password123")
        session_id=auth.login("testuser","password123")
        assert session_id is not None
        assert len(session_id)==16

    def test_login_failure(self):
        """Test login with wrong password"""
        auth = AuthModule()
        auth.register_user("testuser", "password123")
        session_id = auth.login("testuser", "wrongpassword")
        assert session_id is None

    def test_logout(self):
        """Test user logout"""
        auth=AuthModule()
        auth.register_user("testuser","password123")
        session_id=auth.login("testuser","password123")
        result=auth.logout(session_id)
        assert result==True
        assert session_id not in auth.sessions

    def test_get_user(self):
        """Test getting user from session"""
        auth = AuthModule()
        auth.register_user("testuser", "password123")
        session_id = auth.login("testuser", "password123")
        username = auth.get_user(session_id)
        assert username == "testuser"