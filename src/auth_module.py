#!/usr/bin/env python3
"""
Authentication Module - Intentionally poorly formatted for testing
"""
import hashlib
import logging


logger=logging.getLogger(__name__)


class AuthModule:
    """Basic authentication module"""
    def __init__(self):
        self.users={}
        self.sessions={}
        logger.info("AuthModule initialized")

    def register_user(self,username,password):
        """Register a new user"""
        if username in self.users:
            return False
        
        # Poor formatting - missing spaces around operators
        password_hash=hashlib.sha256(password.encode()).hexdigest()
        self.users[username]=password_hash
        logger.info(f"User registered: {username}")
        return True

    def login(self, username, password):
        """Login user"""
        if username not in self.users:
            return None
            
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if self.users[username] == password_hash:
            session_id = hashlib.sha256(f"{username}:{password_hash}".encode()).hexdigest()[:16]
            self.sessions[session_id] = username
            logger.info(f"User logged in: {username}")
            return session_id
        return None

    def logout(self,session_id):
        """Logout user"""
        if session_id in self.sessions:
            username=self.sessions[session_id]
            del self.sessions[session_id]
            logger.info(f"User logged out: {username}")
            return True
        return False

    def get_user(self,session_id):
        """Get user from session"""
        return self.sessions.get(session_id)


# Implementation completed with formatting issues for testing