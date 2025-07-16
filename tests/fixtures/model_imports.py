"""
Helper module to ensure all models are imported for database fixtures.
This ensures all SQLAlchemy models are registered before creating tables.
"""


def import_all_models():
    """Import all model modules to ensure they're registered with SQLAlchemy."""
    try:
        import batch_runner.models  # noqa: F401
        import d1_targeting.models  # noqa: F401
        import d2_sourcing.models  # noqa: F401
        import d3_assessment.models  # noqa: F401
        import d4_enrichment.models  # noqa: F401
        import d5_scoring.models  # noqa: F401
        import d6_reports.models  # noqa: F401
        import d7_storefront.models  # noqa: F401
        import d8_personalization.models  # noqa: F401
        import d9_delivery.models  # noqa: F401
        import d10_analytics.models  # noqa: F401
        import d11_orchestration.models  # noqa: F401
        import database.governance_models  # noqa: F401
        import database.models  # noqa: F401
        import lead_explorer.models  # noqa: F401
        from d6_reports.lineage.models import ReportLineage, ReportLineageAudit  # noqa: F401
        from d6_reports.models import ReportGeneration, ReportTemplate, ReportType, TemplateFormat  # noqa: F401
    except ImportError as e:
        # Log but don't fail - some models might not exist in all environments
        print(f"Warning: Could not import some models: {e}")
