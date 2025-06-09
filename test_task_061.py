"""
Task 061 Verification Test - Build subject line generator

Simple verification test for subject line generation with pattern-based generation,
token replacement, length limits, and A/B variant creation.

Acceptance Criteria:
- Pattern-based generation ✓
- Token replacement works ✓
- Length limits enforced ✓
- A/B variants created ✓
"""

import sys
sys.path.insert(0, '/app')

import tempfile
import yaml
from datetime import datetime

def test_task_061():
    """Test Task 061 acceptance criteria"""
    print("Testing Task 061: Build subject line generator")
    print("=" * 50)
    
    # Test 1: Pattern-based generation
    print("Testing pattern-based generation...")
    
    from d8_personalization.subject_lines import (
        SubjectLineGenerator, SubjectLineRequest, GenerationStrategy, ToneStyle
    )
    from d8_personalization.models import EmailContentType, PersonalizationStrategy
    
    # Create test templates
    test_templates = {
        "templates": {
            "cold_outreach": {
                "direct": [
                    {
                        "pattern": "Quick question about {business_name}",
                        "tokens": ["business_name"],
                        "max_length": 50,
                        "tone": "professional",
                        "urgency": "low"
                    },
                    {
                        "pattern": "Hi {contact_name}, noticed something about {business_name}",
                        "tokens": ["contact_name", "business_name"],
                        "max_length": 65,
                        "tone": "casual",
                        "urgency": "low"
                    }
                ]
            }
        },
        "token_config": {
            "business_name": {
                "default": "your business",
                "max_length": 50,
                "transformations": ["title_case", "remove_legal_suffixes"]
            },
            "contact_name": {
                "default": "there",
                "max_length": 30,
                "transformations": ["title_case"]
            }
        },
        "generation_rules": {
            "global_constraints": {
                "min_length": 10,
                "max_length": 78
            }
        }
    }
    
    # Create temporary template file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(test_templates, f)
        temp_file = f.name
    
    # Initialize generator
    generator = SubjectLineGenerator(temp_file)
    
    # Create test request
    request = SubjectLineRequest(
        business_id="test_biz_123",
        content_type=EmailContentType.COLD_OUTREACH,
        personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
        business_data={
            "name": "Acme Restaurant LLC",
            "category": "restaurant"
        },
        contact_data={
            "first_name": "john"
        },
        max_variants=2
    )
    
    # Generate subject lines
    results = generator.generate_subject_lines(request)
    
    assert len(results) > 0
    assert len(results) <= 2
    
    for result in results:
        assert result.pattern_used
        assert result.text
        assert result.variant_name
        assert isinstance(result.tokens_resolved, dict)
        assert isinstance(result.tokens_failed, list)
    
    print("✓ Subject line generator created successfully")
    print("✓ Template patterns loaded correctly")
    print("✓ Pattern-based generation works")
    
    # Test 2: Token replacement works
    print("Testing token replacement...")
    
    # Check token resolution
    found_business_replacement = False
    found_contact_replacement = False
    
    for result in results:
        # Should not contain unresolved tokens
        assert "{business_name}" not in result.text
        assert "{contact_name}" not in result.text
        
        # Should contain actual values or defaults
        if "Acme Restaurant" in result.text:
            found_business_replacement = True
        if "John" in result.text:
            found_contact_replacement = True
    
    # Test token resolution directly
    tokens_resolved, tokens_failed = generator._resolve_tokens(
        ["business_name", "contact_name"], request
    )
    
    assert "business_name" in tokens_resolved
    assert "contact_name" in tokens_resolved
    assert tokens_resolved["business_name"] == "Acme Restaurant"  # LLC removed
    assert tokens_resolved["contact_name"] == "John"  # Title cased
    
    print("✓ Business name token resolved correctly")
    print("✓ Contact name token resolved correctly") 
    print("✓ Token transformations applied")
    print("✓ Token replacement works")
    
    # Test 3: Length limits enforced
    print("Testing length limits...")
    
    # Test with specific length limit
    request.target_length = 25
    short_results = generator.generate_subject_lines(request)
    
    for result in short_results:
        assert len(result.text) <= 25
        assert len(result.text) >= 10  # Minimum length
        assert result.length == len(result.text)
    
    # Test truncation
    long_text = "This is a very long subject line that exceeds limits"
    truncated = generator._truncate_subject_line(long_text, 30)
    assert len(truncated) <= 30
    assert truncated.endswith("...")
    
    # Test length validation utility
    from d8_personalization.subject_lines import validate_subject_line_length
    assert validate_subject_line_length("Good length subject") is True
    assert validate_subject_line_length("Short") is False
    assert validate_subject_line_length("A" * 100) is False
    
    print("✓ Target length limits enforced")
    print("✓ Text truncation works correctly")
    print("✓ Length validation functions correctly")
    print("✓ Length limits enforced")
    
    # Test 4: A/B variants created
    print("Testing A/B variant creation...")
    
    # Create templates with A/B testing config
    ab_templates = {
        "templates": {
            "cold_outreach": {
                "direct": [
                    {
                        "pattern": "Quick question about {business_name}",
                        "tokens": ["business_name"],
                        "max_length": 50,
                        "tone": "professional"
                    }
                ]
            }
        },
        "token_config": {
            "business_name": {
                "default": "your business",
                "max_length": 50
            }
        },
        "ab_testing": {
            "variant_strategies": {
                "length_variants": {
                    "short": {"max_length": 30, "style": "concise"},
                    "medium": {"max_length": 50, "style": "balanced"}
                },
                "tone_variants": {
                    "formal": {"style": "professional"},
                    "casual": {"style": "friendly"}
                }
            }
        },
        "generation_rules": {
            "global_constraints": {
                "min_length": 10,
                "max_length": 78
            }
        }
    }
    
    # Create new temp file with A/B config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(ab_templates, f)
        ab_temp_file = f.name
    
    ab_generator = SubjectLineGenerator(ab_temp_file)
    
    # Request A/B testing generation
    ab_request = SubjectLineRequest(
        business_id="ab_test_biz",
        content_type=EmailContentType.COLD_OUTREACH,
        personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
        business_data={"name": "Test Business"},
        generation_strategy=GenerationStrategy.AB_TESTING,
        max_variants=4
    )
    
    ab_results = ab_generator.generate_subject_lines(ab_request)
    
    assert len(ab_results) > 1  # Should generate multiple variants
    
    # Check variant names are unique
    variant_names = [result.variant_name for result in ab_results]
    assert len(set(variant_names)) == len(variant_names)  # All unique
    
    # Check for different variant types
    variant_types = [name.split("_")[0] for name in variant_names if "_" in name]
    assert len(set(variant_types)) > 1  # Different types
    
    print("✓ Multiple A/B variants generated")
    print("✓ Variant names are unique")
    print("✓ Different variant types created")
    print("✓ A/B variants created")
    
    # Test additional functionality
    print("Testing additional subject line features...")
    
    # Test quality scoring
    template = {
        "pattern": "Quick question about {business_name}",
        "tokens": ["business_name"],
        "max_length": 50,
        "tone": "professional"
    }
    
    subject_text = "Quick question about Acme Restaurant"
    quality_score = generator._calculate_quality_score(subject_text, template, request)
    assert 0.0 <= quality_score <= 1.0
    
    # Test personalization scoring
    tokens_resolved = {"business_name": "Acme Corp", "contact_name": "John"}
    required_tokens = ["business_name", "contact_name"]
    personalization_score = generator._calculate_personalization_score(tokens_resolved, required_tokens)
    assert personalization_score == 1.0  # Full personalization
    
    # Test spam risk calculation
    clean_text = "Quick question about your business"
    spam_score = generator._calculate_spam_risk_score(clean_text)
    assert spam_score < 0.5  # Should be low risk
    
    # Test readability
    from d8_personalization.subject_lines import calculate_subject_line_readability
    readability = calculate_subject_line_readability("Quick question about business")
    assert readability > 0.0
    
    # Test hash generation
    from d8_personalization.subject_lines import generate_subject_line_hash
    hash1 = generate_subject_line_hash("Test subject")
    hash2 = generate_subject_line_hash("Test subject")
    assert hash1 == hash2
    assert len(hash1) == 16
    
    print("✓ Quality scoring works")
    print("✓ Personalization scoring accurate")
    print("✓ Spam risk calculation functional")
    print("✓ Readability calculation works")
    print("✓ Hash generation functional")
    
    # Test subject line manager
    from d8_personalization.subject_lines import SubjectLineManager
    manager = SubjectLineManager()
    assert manager.generator is not None
    
    print("✓ Subject line manager initialized")
    
    # Test performance-optimized generation
    perf_templates = {
        "templates": {
            "cold_outreach": {
                "direct": [
                    {
                        "pattern": "Quick question about {business_name}",
                        "tokens": ["business_name"],
                        "max_length": 50,
                        "tone": "professional"
                    }
                ]
            }
        },
        "token_config": {
            "business_name": {"default": "your business"}
        },
        "high_performing_patterns": {
            "top_performers": [
                {
                    "pattern": "Quick question about {business_name}",
                    "open_rate": 0.31,
                    "click_rate": 0.08
                }
            ]
        },
        "generation_rules": {
            "global_constraints": {
                "min_length": 10,
                "max_length": 78
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(perf_templates, f)
        perf_temp_file = f.name
    
    perf_generator = SubjectLineGenerator(perf_temp_file)
    perf_request = SubjectLineRequest(
        business_id="perf_test",
        content_type=EmailContentType.COLD_OUTREACH,
        personalization_strategy=PersonalizationStrategy.BUSINESS_SPECIFIC,
        business_data={"name": "Test Business"},
        generation_strategy=GenerationStrategy.PERFORMANCE_OPTIMIZED,
        max_variants=2
    )
    
    perf_results = perf_generator.generate_subject_lines(perf_request)
    assert len(perf_results) > 0
    
    print("✓ Performance-optimized generation works")
    
    # Clean up temp files
    import os
    os.unlink(temp_file)
    os.unlink(ab_temp_file)
    os.unlink(perf_temp_file)
    
    print("=" * 50)
    print("🎉 ALL SUBJECT LINE GENERATOR TESTS PASSED!")
    print("")
    print("Acceptance Criteria Status:")
    print("✓ Pattern-based generation")
    print("✓ Token replacement works")
    print("✓ Length limits enforced")
    print("✓ A/B variants created")
    print("")
    print("Task 061 subject line generator complete and verified!")
    return True

if __name__ == "__main__":
    test_task_061()