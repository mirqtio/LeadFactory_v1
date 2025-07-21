"""
Validation Engine - P2-040 Dynamic Report Designer

Comprehensive validation system for report templates and components.
Provides real-time validation, error detection, and improvement suggestions.

Features:
- Component validation
- Template structure validation
- Data source validation
- Cross-component dependency validation
- Performance validation
- Accessibility validation
- Best practice recommendations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from .component_library import ComponentConfig, ComponentType
from .template_engine import TemplateConfig


class ValidationLevel(str, Enum):
    """Validation level enumeration"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUGGESTION = "suggestion"


class ValidationCategory(str, Enum):
    """Validation category enumeration"""

    STRUCTURE = "structure"
    DATA = "data"
    LAYOUT = "layout"
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    BEST_PRACTICES = "best_practices"
    COMPATIBILITY = "compatibility"


@dataclass
class ValidationIssue:
    """Individual validation issue"""

    level: ValidationLevel
    category: ValidationCategory
    message: str
    component_id: str | None = None
    component_type: ComponentType | None = None
    field: str | None = None
    suggestion: str | None = None
    code: str | None = None


class ValidationResult(BaseModel):
    """Result of validation operation"""

    is_valid: bool
    score: float = Field(ge=0, le=100, description="Validation score (0-100)")
    issues: list[ValidationIssue] = Field(default=[])
    errors: list[str] = Field(default=[])
    warnings: list[str] = Field(default=[])
    suggestions: list[str] = Field(default=[])

    # Category scores
    structure_score: float = Field(default=100)
    data_score: float = Field(default=100)
    layout_score: float = Field(default=100)
    performance_score: float = Field(default=100)
    accessibility_score: float = Field(default=100)
    best_practices_score: float = Field(default=100)

    # Metadata
    template_id: str | None = None
    component_count: int = 0
    data_source_count: int = 0
    validation_time_ms: int = 0

    def add_issue(self, issue: ValidationIssue):
        """Add a validation issue"""
        self.issues.append(issue)

        # Update appropriate lists
        if issue.level == ValidationLevel.ERROR:
            self.errors.append(issue.message)
        elif issue.level == ValidationLevel.WARNING:
            self.warnings.append(issue.message)
        elif issue.level == ValidationLevel.SUGGESTION:
            self.suggestions.append(issue.message)

    def calculate_score(self):
        """Calculate overall validation score"""
        # Count issues by level
        error_count = sum(1 for issue in self.issues if issue.level == ValidationLevel.ERROR)
        warning_count = sum(1 for issue in self.issues if issue.level == ValidationLevel.WARNING)
        suggestion_count = sum(1 for issue in self.issues if issue.level == ValidationLevel.SUGGESTION)

        # Calculate score (100 - penalties)
        score = 100.0
        score -= error_count * 20  # 20 points per error
        score -= warning_count * 10  # 10 points per warning
        score -= suggestion_count * 2  # 2 points per suggestion

        self.score = max(0, score)
        self.is_valid = error_count == 0

        # Calculate category scores
        self._calculate_category_scores()

    def _calculate_category_scores(self):
        """Calculate category-specific scores"""
        categories = {
            ValidationCategory.STRUCTURE: 0,
            ValidationCategory.DATA: 0,
            ValidationCategory.LAYOUT: 0,
            ValidationCategory.PERFORMANCE: 0,
            ValidationCategory.ACCESSIBILITY: 0,
            ValidationCategory.BEST_PRACTICES: 0,
        }

        # Count issues by category
        for issue in self.issues:
            if issue.category in categories:
                penalty = (
                    20 if issue.level == ValidationLevel.ERROR else 10 if issue.level == ValidationLevel.WARNING else 2
                )
                categories[issue.category] += penalty

        # Calculate scores
        self.structure_score = max(0, 100 - categories[ValidationCategory.STRUCTURE])
        self.data_score = max(0, 100 - categories[ValidationCategory.DATA])
        self.layout_score = max(0, 100 - categories[ValidationCategory.LAYOUT])
        self.performance_score = max(0, 100 - categories[ValidationCategory.PERFORMANCE])
        self.accessibility_score = max(0, 100 - categories[ValidationCategory.ACCESSIBILITY])
        self.best_practices_score = max(0, 100 - categories[ValidationCategory.BEST_PRACTICES])


class ValidationRule(ABC):
    """Abstract base class for validation rules"""

    def __init__(self, name: str, description: str, category: ValidationCategory):
        self.name = name
        self.description = description
        self.category = category

    @abstractmethod
    def validate(self, template: TemplateConfig) -> list[ValidationIssue]:
        """Validate template and return issues"""


class ComponentValidationRule(ValidationRule):
    """Base class for component validation rules"""

    def __init__(
        self, name: str, description: str, category: ValidationCategory, component_types: list[ComponentType] = None
    ):
        super().__init__(name, description, category)
        self.component_types = component_types or []

    def applies_to_component(self, component: ComponentConfig) -> bool:
        """Check if rule applies to component"""
        return not self.component_types or component.type in self.component_types

    @abstractmethod
    def validate_component(self, component: ComponentConfig, template: TemplateConfig) -> list[ValidationIssue]:
        """Validate component and return issues"""

    def validate(self, template: TemplateConfig) -> list[ValidationIssue]:
        """Validate template components"""
        issues = []

        for component in template.components:
            if self.applies_to_component(component):
                component_issues = self.validate_component(component, template)
                issues.extend(component_issues)

        return issues


# Specific validation rules


class RequiredFieldsRule(ComponentValidationRule):
    """Validate that required fields are present"""

    def __init__(self):
        super().__init__(
            name="required_fields",
            description="Check that required fields are present",
            category=ValidationCategory.STRUCTURE,
        )

    def validate_component(self, component: ComponentConfig, template: TemplateConfig) -> list[ValidationIssue]:
        issues = []

        # Check required fields
        if not component.id:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category=self.category,
                    message="Component ID is required",
                    component_id=component.id,
                    component_type=component.type,
                    field="id",
                    code="MISSING_ID",
                )
            )

        if not component.title:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category=self.category,
                    message="Component title is required",
                    component_id=component.id,
                    component_type=component.type,
                    field="title",
                    code="MISSING_TITLE",
                )
            )

        return issues


class DataSourceValidationRule(ComponentValidationRule):
    """Validate data source requirements"""

    def __init__(self):
        super().__init__(
            name="data_source_validation",
            description="Check data source requirements",
            category=ValidationCategory.DATA,
            component_types=[ComponentType.TABLE, ComponentType.CHART, ComponentType.METRIC],
        )

    def validate_component(self, component: ComponentConfig, template: TemplateConfig) -> list[ValidationIssue]:
        issues = []

        # Check data source requirement
        if not component.data_source:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category=self.category,
                    message=f"{component.type.value} component requires a data source",
                    component_id=component.id,
                    component_type=component.type,
                    field="data_source",
                    suggestion="Add a data source to this component",
                    code="MISSING_DATA_SOURCE",
                )
            )

        # Check if data source exists in template
        elif component.data_source not in template.data_sources:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.WARNING,
                    category=self.category,
                    message=f"Data source '{component.data_source}' not declared in template",
                    component_id=component.id,
                    component_type=component.type,
                    field="data_source",
                    suggestion="Add data source to template data_sources list",
                    code="UNDECLARED_DATA_SOURCE",
                )
            )

        return issues


class LayoutValidationRule(ComponentValidationRule):
    """Validate layout properties"""

    def __init__(self):
        super().__init__(
            name="layout_validation", description="Check layout properties", category=ValidationCategory.LAYOUT
        )

    def validate_component(self, component: ComponentConfig, template: TemplateConfig) -> list[ValidationIssue]:
        issues = []

        # Check width values
        if component.width and isinstance(component.width, str):
            if component.width.endswith("%"):
                try:
                    value = float(component.width[:-1])
                    if value > 100:
                        issues.append(
                            ValidationIssue(
                                level=ValidationLevel.WARNING,
                                category=self.category,
                                message=f"Width {component.width} exceeds 100%",
                                component_id=component.id,
                                component_type=component.type,
                                field="width",
                                suggestion="Consider using a width <= 100%",
                                code="EXCESSIVE_WIDTH",
                            )
                        )
                except ValueError:
                    issues.append(
                        ValidationIssue(
                            level=ValidationLevel.ERROR,
                            category=self.category,
                            message=f"Invalid width value: {component.width}",
                            component_id=component.id,
                            component_type=component.type,
                            field="width",
                            code="INVALID_WIDTH",
                        )
                    )

        return issues


class AccessibilityValidationRule(ComponentValidationRule):
    """Validate accessibility requirements"""

    def __init__(self):
        super().__init__(
            name="accessibility_validation",
            description="Check accessibility requirements",
            category=ValidationCategory.ACCESSIBILITY,
        )

    def validate_component(self, component: ComponentConfig, template: TemplateConfig) -> list[ValidationIssue]:
        issues = []

        # Check for descriptive titles
        if component.title and len(component.title) < 3:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.WARNING,
                    category=self.category,
                    message="Component title should be more descriptive",
                    component_id=component.id,
                    component_type=component.type,
                    field="title",
                    suggestion="Use a more descriptive title for better accessibility",
                    code="SHORT_TITLE",
                )
            )

        # Check for color-only information
        if component.background_color and not component.description:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.SUGGESTION,
                    category=self.category,
                    message="Consider adding description when using background colors",
                    component_id=component.id,
                    component_type=component.type,
                    field="description",
                    suggestion="Add description to avoid relying solely on color",
                    code="COLOR_ONLY_INFO",
                )
            )

        return issues


class PerformanceValidationRule(ValidationRule):
    """Validate performance characteristics"""

    def __init__(self):
        super().__init__(
            name="performance_validation",
            description="Check performance characteristics",
            category=ValidationCategory.PERFORMANCE,
        )

    def validate(self, template: TemplateConfig) -> list[ValidationIssue]:
        issues = []

        # Check component count
        if len(template.components) > 20:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.WARNING,
                    category=self.category,
                    message=f"High component count ({len(template.components)}) may affect performance",
                    suggestion="Consider splitting into multiple templates",
                    code="HIGH_COMPONENT_COUNT",
                )
            )

        # Check data source count
        if len(template.data_sources) > 10:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.WARNING,
                    category=self.category,
                    message=f"High data source count ({len(template.data_sources)}) may affect performance",
                    suggestion="Consider consolidating data sources",
                    code="HIGH_DATA_SOURCE_COUNT",
                )
            )

        return issues


class BestPracticesRule(ValidationRule):
    """Validate best practices"""

    def __init__(self):
        super().__init__(
            name="best_practices", description="Check best practices", category=ValidationCategory.BEST_PRACTICES
        )

    def validate(self, template: TemplateConfig) -> list[ValidationIssue]:
        issues = []

        # Check for header component
        has_header = any(comp.type == ComponentType.HEADER for comp in template.components)
        if not has_header:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.SUGGESTION,
                    category=self.category,
                    message="Consider adding a header component",
                    suggestion="Headers provide context and improve readability",
                    code="MISSING_HEADER",
                )
            )

        # Check for template description
        if not template.description:
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.SUGGESTION,
                    category=self.category,
                    message="Consider adding a template description",
                    suggestion="Descriptions help with template management",
                    code="MISSING_DESCRIPTION",
                )
            )

        # Check for duplicate component IDs
        component_ids = [comp.id for comp in template.components]
        if len(component_ids) != len(set(component_ids)):
            issues.append(
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    category=self.category,
                    message="Duplicate component IDs found",
                    suggestion="Each component must have a unique ID",
                    code="DUPLICATE_IDS",
                )
            )

        return issues


class ValidationEngine:
    """Main validation engine"""

    def __init__(self):
        self.rules: list[ValidationRule] = []
        self._register_default_rules()

    def _register_default_rules(self):
        """Register default validation rules"""
        self.rules.extend(
            [
                RequiredFieldsRule(),
                DataSourceValidationRule(),
                LayoutValidationRule(),
                AccessibilityValidationRule(),
                PerformanceValidationRule(),
                BestPracticesRule(),
            ]
        )

    def register_rule(self, rule: ValidationRule):
        """Register a custom validation rule"""
        self.rules.append(rule)

    def validate_template(self, template: TemplateConfig) -> ValidationResult:
        """Validate a template"""
        result = ValidationResult(
            is_valid=True,
            score=100.0,  # Initial score, will be calculated later
            template_id=template.id,
            component_count=len(template.components),
            data_source_count=len(template.data_sources),
        )

        # Run all validation rules
        for rule in self.rules:
            try:
                issues = rule.validate(template)
                for issue in issues:
                    result.add_issue(issue)
            except Exception as e:
                # Add error for failed rule
                result.add_issue(
                    ValidationIssue(
                        level=ValidationLevel.ERROR,
                        category=ValidationCategory.STRUCTURE,
                        message=f"Validation rule '{rule.name}' failed: {str(e)}",
                        code="RULE_FAILURE",
                    )
                )

        # Calculate final score
        result.calculate_score()

        return result

    def validate_component(self, component: ComponentConfig, template: TemplateConfig = None) -> ValidationResult:
        """Validate a single component"""
        # Create minimal template for validation
        if template is None:
            template = TemplateConfig(
                id="temp_validation",
                name="Validation Template",
                components=[component],
                data_sources=[component.data_source] if component.data_source else [],
            )

        result = ValidationResult(
            is_valid=True,
            score=100.0,
            template_id=template.id,
            component_count=1,
            data_source_count=len(template.data_sources),
        )

        # Run component-specific rules
        for rule in self.rules:
            if isinstance(rule, ComponentValidationRule):
                try:
                    if rule.applies_to_component(component):
                        issues = rule.validate_component(component, template)
                        for issue in issues:
                            result.add_issue(issue)
                except Exception as e:
                    result.add_issue(
                        ValidationIssue(
                            level=ValidationLevel.ERROR,
                            category=ValidationCategory.STRUCTURE,
                            message=f"Component validation rule '{rule.name}' failed: {str(e)}",
                            component_id=component.id,
                            component_type=component.type,
                            code="COMPONENT_RULE_FAILURE",
                        )
                    )

        # Calculate final score
        result.calculate_score()

        return result

    def get_validation_report(self, template: TemplateConfig) -> dict[str, Any]:
        """Get detailed validation report"""
        result = self.validate_template(template)

        # Group issues by category
        issues_by_category = {}
        for issue in result.issues:
            category = issue.category.value
            if category not in issues_by_category:
                issues_by_category[category] = []
            issues_by_category[category].append(issue)

        # Group issues by component
        issues_by_component = {}
        for issue in result.issues:
            component_id = issue.component_id or "template"
            if component_id not in issues_by_component:
                issues_by_component[component_id] = []
            issues_by_component[component_id].append(issue)

        return {
            "summary": {
                "is_valid": result.is_valid,
                "overall_score": result.score,
                "total_issues": len(result.issues),
                "errors": len(result.errors),
                "warnings": len(result.warnings),
                "suggestions": len(result.suggestions),
            },
            "category_scores": {
                "structure": result.structure_score,
                "data": result.data_score,
                "layout": result.layout_score,
                "performance": result.performance_score,
                "accessibility": result.accessibility_score,
                "best_practices": result.best_practices_score,
            },
            "issues_by_category": issues_by_category,
            "issues_by_component": issues_by_component,
            "recommendations": self._generate_recommendations(result),
        }

    def _generate_recommendations(self, result: ValidationResult) -> list[str]:
        """Generate recommendations based on validation results"""
        recommendations = []

        if result.structure_score < 80:
            recommendations.append("Review template structure and fix component configuration errors")

        if result.data_score < 80:
            recommendations.append("Ensure all data sources are properly configured and declared")

        if result.layout_score < 80:
            recommendations.append("Review layout properties and ensure proper spacing and sizing")

        if result.performance_score < 80:
            recommendations.append("Consider reducing component count or optimizing data sources")

        if result.accessibility_score < 80:
            recommendations.append("Improve accessibility by adding descriptions and meaningful titles")

        if result.best_practices_score < 80:
            recommendations.append("Follow best practices by adding headers and descriptions")

        return recommendations


# Global validation engine instance
validation_engine = ValidationEngine()
