# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed
- Dropped yelp_id column and yelp_rating scoring rule
- Removed final Yelp references from documentation
- Removed Yelp provider implementation and all related code
- Removed YelpSearchFieldsAssessor from assessment stack
- Cleaned up Yelp references from configuration files
- Removed Yelp API methods from gateway facade
- Updated all provider lists to exclude Yelp

### Changed
- Force stub usage in CI environment (PR #2)
- CI always uses stubs, no live API calls
- Added provider_stub fixture to ensure tests use stubs
- Complete analysis workflow now requires explicit business_url parameter

### Fixed
- CI test configuration to always use stubs
- Test imports and references after Yelp removal

## [0.1.0] - 2025-07-10

### Added
- Initial LeadFactory MVP implementation
- Multi-domain architecture (D0-D11)
- External API gateway with circuit breakers
- Assessment pipeline with 7 assessors
- Scoring engine with configurable rules
- Email delivery system
- PDF report generation
- Stripe payment integration