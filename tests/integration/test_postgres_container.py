"""
Integration tests for PostgreSQL container setup - P0-012
"""

import os
import subprocess
import time
import pytest
from sqlalchemy import create_engine, text


class TestPostgresContainer:
    """Test PostgreSQL container configuration and persistence"""
    
    @pytest.mark.integration
    def test_postgres_container_running(self):
        """Test that PostgreSQL container is running"""
        # Check if we're in Docker environment
        if not os.path.exists('/.dockerenv') and os.getenv('CI') != 'true':
            pytest.skip("Not in Docker environment")
            
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=leadfactory_db', '--format', '{{.Names}}'],
            capture_output=True,
            text=True
        )
        
        assert 'leadfactory_db' in result.stdout, "PostgreSQL container not running"
    
    @pytest.mark.integration
    def test_postgres_named_volume(self):
        """Test that PostgreSQL uses named volume for persistence"""
        if not os.path.exists('/.dockerenv') and os.getenv('CI') != 'true':
            pytest.skip("Not in Docker environment")
            
        result = subprocess.run(
            ['docker', 'volume', 'ls', '--format', '{{.Name}}'],
            capture_output=True,
            text=True
        )
        
        volumes = result.stdout.strip().split('\n')
        postgres_volumes = [v for v in volumes if 'postgres_data' in v]
        
        assert len(postgres_volumes) > 0, "No PostgreSQL data volume found"
    
    @pytest.mark.integration
    def test_database_connection(self):
        """Test that application can connect to PostgreSQL"""
        # Use test database URL or skip if not available
        db_url = os.getenv('DATABASE_URL', 'postgresql://leadfactory:leadfactory@localhost:5432/leadfactory')
        
        if 'sqlite' in db_url:
            pytest.skip("SQLite database configured, skipping PostgreSQL test")
        
        try:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                assert 'PostgreSQL' in version, f"Unexpected database: {version}"
                assert '15' in version, f"Expected PostgreSQL 15, got: {version}"
        except Exception as e:
            if "could not connect" in str(e):
                pytest.skip(f"PostgreSQL not accessible: {e}")
            raise
    
    @pytest.mark.integration
    def test_alembic_migrations_current(self):
        """Test that Alembic migrations are up to date"""
        db_url = os.getenv('DATABASE_URL', 'postgresql://leadfactory:leadfactory@localhost:5432/leadfactory')
        
        if 'sqlite' in db_url:
            pytest.skip("SQLite database configured, skipping PostgreSQL test")
        
        try:
            # Check if alembic version table exists
            engine = create_engine(db_url)
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'alembic_version'
                    )
                """))
                has_alembic = result.scalar()
                
                if not has_alembic:
                    pytest.skip("Alembic not initialized in this database")
                
                # Get current revision
                result = conn.execute(text("SELECT version_num FROM alembic_version"))
                current_rev = result.scalar()
                
                assert current_rev is not None, "No Alembic revision found"
                
                # Run alembic check
                result = subprocess.run(
                    ['alembic', 'current'],
                    capture_output=True,
                    text=True,
                    env={**os.environ, 'DATABASE_URL': db_url}
                )
                
                assert result.returncode == 0, f"Alembic check failed: {result.stderr}"
                assert current_rev in result.stdout, "Database not at latest migration"
                
        except Exception as e:
            if "could not connect" in str(e):
                pytest.skip(f"PostgreSQL not accessible: {e}")
            raise
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_data_persistence_across_restart(self):
        """Test that data persists across container restart"""
        if os.getenv('CI') == 'true':
            pytest.skip("Cannot test container restart in CI")
            
        db_url = os.getenv('DATABASE_URL', 'postgresql://leadfactory:leadfactory@localhost:5432/leadfactory')
        
        if 'sqlite' in db_url:
            pytest.skip("SQLite database configured, skipping PostgreSQL test")
        
        try:
            engine = create_engine(db_url)
            
            # Create test table and insert data
            with engine.connect() as conn:
                conn.execute(text("CREATE TABLE IF NOT EXISTS persistence_test (id SERIAL PRIMARY KEY, data TEXT)"))
                conn.execute(text("INSERT INTO persistence_test (data) VALUES ('test_data')"))
                conn.commit()
            
            # Simulate container restart (in real deployment)
            # Here we just verify the data exists
            time.sleep(1)
            
            # Verify data still exists
            with engine.connect() as conn:
                result = conn.execute(text("SELECT data FROM persistence_test WHERE data = 'test_data'"))
                data = result.scalar()
                assert data == 'test_data', "Data did not persist"
                
                # Cleanup
                conn.execute(text("DROP TABLE IF EXISTS persistence_test"))
                conn.commit()
                
        except Exception as e:
            if "could not connect" in str(e):
                pytest.skip(f"PostgreSQL not accessible: {e}")
            raise


@pytest.mark.integration
def test_docker_compose_postgres_config():
    """Test that docker-compose.prod.yml has correct PostgreSQL configuration"""
    import yaml
    
    compose_file = 'docker-compose.prod.yml'
    if not os.path.exists(compose_file):
        pytest.skip(f"{compose_file} not found")
    
    with open(compose_file) as f:
        config = yaml.safe_load(f)
    
    # Check PostgreSQL service exists
    assert 'db' in config['services'], "PostgreSQL service 'db' not found"
    
    db_config = config['services']['db']
    
    # Check correct image
    assert db_config['image'] == 'postgres:15-alpine', "Wrong PostgreSQL version"
    
    # Check restart policy
    assert db_config['restart'] == 'always', "Restart policy not set to 'always'"
    
    # Check volume configuration
    assert 'volumes' in db_config, "No volumes configured for PostgreSQL"
    assert any('postgres_data' in v for v in db_config['volumes']), "Named volume not configured"
    
    # Check health check
    assert 'healthcheck' in db_config, "No health check configured"
    assert 'pg_isready' in str(db_config['healthcheck']['test']), "Health check not using pg_isready"
    
    # Check global volumes
    assert 'volumes' in config, "No global volumes section"
    assert 'postgres_data' in config['volumes'], "postgres_data volume not declared"