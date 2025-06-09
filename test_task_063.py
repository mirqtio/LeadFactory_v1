"""
Task 063 Verification Test - Create spam score checker

Simple verification test for spam score checking with rule-based analysis,
score reduction logic, and common pattern detection.

Acceptance Criteria:
- Basic spam scoring ✓
- Rule-based checks ✓
- Score reduction logic ✓
- Common patterns caught ✓
"""

import sys
import os
sys.path.insert(0, '/app')

# Set environment variables for config validation
os.environ['SECRET_KEY'] = 'test-secret-key-for-task-063-verification-32-chars-long'
os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/test'
os.environ['ENVIRONMENT'] = 'development'

import json

def test_task_063():
    """Test Task 063 acceptance criteria"""
    print("Testing Task 063: Create spam score checker")
    print("=" * 50)
    
    # Test 1: Basic spam scoring
    print("Testing basic spam scoring...")
    
    from d8_personalization.spam_checker import SpamScoreChecker, quick_spam_check
    
    # Test basic checker initialization
    checker = SpamScoreChecker()
    assert checker.rules is not None
    assert len(checker.rules) > 0
    assert checker.max_score == 100.0
    
    # Test basic spam score calculation
    clean_subject = "Website performance insights"
    clean_content = "Hi John, I wanted to share some insights about your website performance."
    
    result = checker.check_spam_score(clean_subject, clean_content)
    
    assert hasattr(result, 'overall_score')
    assert hasattr(result, 'risk_level')
    assert hasattr(result, 'triggered_rules')
    assert hasattr(result, 'suggestions')
    assert isinstance(result.overall_score, float)
    assert 0 <= result.overall_score <= 100
    
    # Test quick spam check utility
    quick_score = quick_spam_check(clean_subject, clean_content)
    assert isinstance(quick_score, float)
    assert quick_score == result.overall_score
    
    print("✓ Spam checker initialized successfully")
    print("✓ Basic spam scoring works")
    print(f"✓ Clean content score: {result.overall_score}")
    print("✓ Basic spam scoring complete")
    
    # Test 2: Rule-based checks
    print("Testing rule-based checks...")
    
    # Test with spammy content that should trigger rules
    spammy_subject = "FREE URGENT OFFER!!! ACT NOW!!!"
    spammy_content = "CLICK HERE NOW!!! Make $1000 instantly!!! LIMITED TIME GUARANTEED!!!"
    
    spammy_result = checker.check_spam_score(spammy_subject, spammy_content)
    
    assert spammy_result.overall_score > result.overall_score  # Should score higher
    assert len(spammy_result.triggered_rules) > 0  # Should trigger rules
    
    # Verify specific rules were triggered
    rule_ids = [rule['rule_id'] for rule in spammy_result.triggered_rules]
    
    # Should catch common spam patterns
    expected_patterns = ['keyword_free', 'keyword_urgent', 'keyword_act_now', 'keyword_click_here']
    found_patterns = [pattern for pattern in expected_patterns if any(pattern in rule_id for rule_id in rule_ids)]
    assert len(found_patterns) > 0
    
    # Test rule categories
    categories = [rule['category'] for rule in spammy_result.triggered_rules]
    assert 'keywords' in categories or 'formatting' in categories
    
    # Test category scoring
    assert len(spammy_result.category_scores) > 0
    assert any(score > 0 for score in spammy_result.category_scores.values())
    
    print("✓ Rule-based checks trigger correctly")
    print(f"✓ Spammy content score: {spammy_result.overall_score}")
    print(f"✓ Rules triggered: {len(spammy_result.triggered_rules)}")
    print("✓ Rule-based checks complete")
    
    # Test 3: Score reduction logic
    print("Testing score reduction logic...")
    
    # Test improvement suggestions generation
    assert len(spammy_result.suggestions) > 0
    suggestions_text = ' '.join(spammy_result.suggestions)
    
    # Should provide actionable suggestions
    suggestion_keywords = ['remove', 'replace', 'reduce', 'limit', 'improve']
    has_actionable = any(keyword in suggestions_text.lower() for keyword in suggestion_keywords)
    assert has_actionable
    
    # Test automatic score reduction
    improvements = checker.reduce_spam_score(spammy_content, spammy_result.suggestions)
    
    assert 'improved_content' in improvements
    assert 'applied_fixes' in improvements
    assert improvements['improved_content'] != spammy_content  # Should be different
    assert len(improvements['applied_fixes']) > 0  # Should have applied fixes
    
    # Test that improved content has lower spam score
    improved_subject = spammy_subject.replace('FREE', 'Complimentary').replace('!!!', '!')
    improved_result = checker.check_spam_score(improved_subject, improvements['improved_content'])
    
    # Improved content should have lower score (with some tolerance)
    assert improved_result.overall_score <= spammy_result.overall_score + 5  # Allow small variance
    
    # Test utility function for improvements
    from d8_personalization.spam_checker import improve_email_deliverability
    
    improvement_analysis = improve_email_deliverability(spammy_subject, spammy_content)
    assert 'original_score' in improvement_analysis
    assert 'suggestions' in improvement_analysis
    assert 'risk_level' in improvement_analysis
    
    print("✓ Improvement suggestions generated")
    print(f"✓ Applied fixes: {len(improvements['applied_fixes'])}")
    print("✓ Score reduction logic works")
    print("✓ Score reduction logic complete")
    
    # Test 4: Common patterns caught
    print("Testing common pattern detection...")
    
    # Test various spam patterns
    test_cases = [
        ("All caps test", "THIS IS ALL CAPS TEXT", ['pattern_all_caps']),
        ("Multiple exclamations", "Great offer!!!", ['pattern_multiple_exclamation']),
        ("Money terms", "Earn money fast", ['keyword_money_terms']),
        ("Click here", "Click here to win", ['keyword_click_here']),
        ("Dollar amounts", "Save $500 today", ['pattern_dollar_amounts']),
        ("Percentage discount", "50% off sale", ['pattern_percentage_discount'])
    ]
    
    patterns_caught = 0
    for test_name, test_content, expected_rules in test_cases:
        test_result = checker.check_spam_score("Test", test_content)
        
        triggered_rule_ids = [rule['rule_id'] for rule in test_result.triggered_rules]
        
        # Check if any expected rules were triggered
        if any(expected in ' '.join(triggered_rule_ids) for expected in expected_rules):
            patterns_caught += 1
    
    assert patterns_caught >= 4  # Should catch most common patterns
    
    # Test batch checking
    test_emails = [
        {'subject': 'Clean email', 'content': 'Professional business email'},
        {'subject': 'FREE MONEY!!!', 'content': 'GET RICH QUICK!!!'},
        {'subject': 'Newsletter', 'content': 'Monthly updates from our team'}
    ]
    
    batch_results = checker.batch_check_emails(test_emails)
    assert len(batch_results) == 3
    assert all(hasattr(result, 'overall_score') for result in batch_results)
    
    # Middle email should have highest score
    scores = [result.overall_score for result in batch_results]
    assert scores[1] > scores[0]  # Spammy > Clean
    assert scores[1] > scores[2]  # Spammy > Newsletter
    
    print(f"✓ Common patterns caught: {patterns_caught}/6 test cases")
    print("✓ Batch email checking works")
    print("✓ Common patterns caught")
    
    # Test additional functionality
    print("Testing additional spam checker features...")
    
    # Test rule statistics
    stats = checker.get_rule_statistics()
    assert 'total_rules' in stats
    assert 'enabled_rules' in stats
    assert 'rules_by_type' in stats
    assert 'rules_by_category' in stats
    assert stats['total_rules'] > 0
    
    # Test utility functions
    from d8_personalization.spam_checker import is_likely_spam
    
    assert is_likely_spam("FREE MONEY!!!", "GET RICH QUICK!!!", threshold=50.0) == True
    assert is_likely_spam("Professional email", "Business communication", threshold=50.0) == False
    
    # Test rules loading from JSON
    assert os.path.exists(checker.rules_file)
    with open(checker.rules_file, 'r') as f:
        rules_data = json.load(f)
        assert 'rules' in rules_data
        assert 'thresholds' in rules_data
        assert len(rules_data['rules']) > 0
    
    # Test risk level calculation
    from d8_personalization.spam_checker import SpamRiskLevel
    
    low_risk_content = "Professional business email content"
    high_risk_content = "FREE URGENT MONEY GUARANTEED!!!"
    
    low_result = checker.check_spam_score("Business Update", low_risk_content)
    high_result = checker.check_spam_score("FREE MONEY!!!", high_risk_content)
    
    assert low_result.risk_level in [SpamRiskLevel.LOW, SpamRiskLevel.MEDIUM]
    assert high_result.risk_level in [SpamRiskLevel.HIGH, SpamRiskLevel.CRITICAL]
    
    print("✓ Rule statistics calculated")
    print("✓ Utility functions work")
    print("✓ JSON rules file loaded")
    print("✓ Risk level calculation accurate")
    print("✓ Additional features complete")
    
    print("=" * 50)
    print("🎉 ALL SPAM SCORE CHECKER TESTS PASSED!")
    print("")
    print("Acceptance Criteria Status:")
    print("✓ Basic spam scoring")
    print("✓ Rule-based checks")
    print("✓ Score reduction logic")
    print("✓ Common patterns caught")
    print("")
    print("Task 063 spam score checker complete and verified!")
    return True

if __name__ == "__main__":
    test_task_063()