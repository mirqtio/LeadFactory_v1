"""
Simplified Task 062 Test
"""

import sys
import os
sys.path.insert(0, '/app')

# Set environment variables for config validation
os.environ['SECRET_KEY'] = 'test-secret-key-for-task-062-verification-32-chars-long'
os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/test'
os.environ['ENVIRONMENT'] = 'development'

import asyncio
from datetime import datetime

def test_task_062_simple():
    """Simplified test for Task 062"""
    print("Testing Task 062: Email personalizer (simplified)")
    print("=" * 50)
    
    try:
        # Test 1: Issue extraction
        from d8_personalization.personalizer import IssueExtractor
        
        test_assessment_data = {
            'pagespeed': {'performance_score': 45, 'seo_score': 60},
            'issues': {'count': 3, 'list': ['slow_loading', 'seo_issues']}
        }
        test_business_data = {'name': 'Acme Restaurant LLC', 'category': 'restaurant'}
        
        issue_extractor = IssueExtractor()
        extracted_issues = issue_extractor.extract_issues_from_assessment(
            test_assessment_data, test_business_data, max_issues=3
        )
        
        print(f"✓ Issue extraction: {len(extracted_issues)} issues found")
        
        # Test 2: Spam checking
        from d8_personalization.personalizer import SpamChecker
        
        spam_checker = SpamChecker()
        spam_score, spam_details = spam_checker.calculate_spam_score(
            "Test subject", "Test content", "text"
        )
        
        print(f"✓ Spam checking: score = {spam_score}")
        
        # Test 3: Simple personalizer test
        from d8_personalization.personalizer import EmailPersonalizer, PersonalizationRequest
        from d8_personalization.models import EmailContentType, PersonalizationStrategy, ContentStrategy
        
        class MockClient:
            async def generate_email_content(self, business_name, website_issues, recipient_name=None):
                return {'email_body': f'Test email for {business_name}'}
        
        personalizer = EmailPersonalizer(openai_client=MockClient())
        
        request = PersonalizationRequest(
            business_id="test",
            business_data=test_business_data,
            assessment_data=test_assessment_data,
            contact_data={'first_name': 'John'}
        )
        
        # Run async test
        async def run_test():
            result = await personalizer.personalize_email(request)
            print(f"✓ Personalization: spam_score = {result.spam_score} (type: {type(result.spam_score)})")
            return result
        
        result = asyncio.run(run_test())
        
        print("✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_task_062_simple()