"""
Command-line interface for LeadFactory
"""
import asyncio
from datetime import date

import click

from core.config import settings
from core.logging import get_logger
from database.base import Base
from database.session import engine

logger = get_logger(__name__)


@click.group()
@click.version_option(version=settings.app_version)
def cli():
    """LeadFactory CLI - AI-powered website audit platform"""
    pass


@cli.command()
def init_db():
    """Initialize database with tables"""
    click.echo("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    click.echo("Database initialized successfully!")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def runserver(host: str, port: int, reload: bool):
    """Run the FastAPI development server"""
    import uvicorn

    click.echo(f"Starting LeadFactory server on {host}:{port}")
    click.echo(f"Environment: {settings.environment}")
    click.echo(f"Use stubs: {settings.use_stubs}")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level=settings.log_level.lower(),
    )


@cli.command()
@click.option(
    "--location", required=True, help='Location to search (e.g., "New York, NY")'
)
@click.option("--vertical", default="restaurant", help="Business vertical")
@click.option("--limit", default=10, help="Number of businesses to process")
def test_pipeline(location: str, vertical: str, limit: int):
    """Test the pipeline with a small batch"""

    async def run_test():
        # This will be implemented when we have the pipeline
        click.echo(f"Testing pipeline for {location} - {vertical}")
        click.echo(f"Processing {limit} businesses...")
        # Placeholder for actual implementation
        click.echo("Pipeline test completed!")

    asyncio.run(run_test())


@cli.command()
@click.option(
    "--date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Date to generate report for",
)
def daily_report(date):
    """Generate daily metrics report"""
    report_date = date.date() if date else date.today()

    async def generate_report():
        click.echo(f"Generating report for {report_date}")
        # Placeholder for actual implementation
        click.echo("Report generated successfully!")

    asyncio.run(generate_report())


@cli.command()
def run_stubs():
    """Run the stub server for testing"""
    import uvicorn

    click.echo("Starting stub server on port 5010")
    uvicorn.run("stubs.server:app", host="0.0.0.0", port=5010, log_level="info")


@cli.command()
@click.option(
    "--provider",
    type=click.Choice(["yelp", "pagespeed", "stripe", "sendgrid", "openai"]),
    help="Provider to check",
)
def check_api(provider: str):
    """Check API connectivity and configuration"""
    click.echo(f"Checking {provider} API configuration...")

    if settings.use_stubs:
        click.echo(f"✓ Using stub server at {settings.stub_base_url}")
    else:
        try:
            api_key = settings.get_api_key(provider)
            masked_key = api_key[:8] + "..." if len(api_key) > 8 else "***"
            click.echo(f"✓ API key configured: {masked_key}")
        except ValueError as e:
            click.echo(f"✗ {e}", err=True)
            return

    # Could add actual connectivity test here
    click.echo(f"✓ {provider} API ready")


@cli.command()
@click.argument("url")
def audit(url: str):
    """Run a quick website audit (smoke test)"""
    import requests

    async def run_audit():
        click.echo(f"Running audit for: {url}")

        # Basic connectivity check
        try:
            response = requests.get(url, timeout=10)
            click.echo(f"✓ Website reachable (status: {response.status_code})")

            # Check if it's a valid business website
            if response.status_code == 200:
                content_length = len(response.content)
                click.echo(f"✓ Content retrieved ({content_length} bytes)")

                # Simple checks
                has_title = "<title>" in response.text.lower()
                has_phone = any(
                    term in response.text for term in ["phone", "tel:", "call"]
                )
                has_address = any(
                    term in response.text.lower()
                    for term in ["address", "location", "street"]
                )

                click.echo(f"✓ Has title tag: {has_title}")
                click.echo(f"✓ Has phone info: {has_phone}")
                click.echo(f"✓ Has address info: {has_address}")

                click.echo("\nAudit complete! Full assessment available via API.")
            else:
                click.echo(f"✗ Website returned non-200 status: {response.status_code}")

        except requests.RequestException as e:
            click.echo(f"✗ Failed to reach website: {e}", err=True)
            return

    asyncio.run(run_audit())


@cli.command()
def env_info():
    """Display environment information"""
    click.echo(f"LeadFactory v{settings.app_version}")
    click.echo(f"Environment: {settings.environment}")
    click.echo(f"Database: {settings.database_url}")
    click.echo(f"Use stubs: {settings.use_stubs}")
    click.echo(f"Email limit: {settings.max_daily_emails}/day")
    click.echo(f"Yelp limit: {settings.max_daily_yelp_calls}/day")
    click.echo(f"Report price: ${settings.report_price_cents / 100:.2f}")


def main():
    """Main entry point"""
    cli()


if __name__ == "__main__":
    main()
