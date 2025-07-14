"""Base class for SQLAlchemy models"""
import uuid

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import String, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PostgreSQL_UUID
from sqlalchemy.orm import declarative_base


class UUID(TypeDecorator):
    """
    Database-agnostic UUID type.
    Uses PostgreSQL UUID for PostgreSQL, String for other databases.
    """

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQL_UUID())
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(value)
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value


Base = declarative_base()


class DatabaseAgnosticEnum(TypeDecorator):
    """
    Database-agnostic Enum type.
    Uses native ENUM for PostgreSQL, String for other databases.
    """

    impl = String
    cache_ok = True

    def __init__(self, enum_class, *args, **kwargs):
        self.enum_class = enum_class
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            # For PostgreSQL, use native ENUM
            return dialect.type_descriptor(SQLEnum(self.enum_class, create_type=False))
        else:
            # For other databases, use String
            max_len = max(len(item.value) for item in self.enum_class)
            return dialect.type_descriptor(String(max_len))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, self.enum_class):
            return value.value
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return self.enum_class(value)
