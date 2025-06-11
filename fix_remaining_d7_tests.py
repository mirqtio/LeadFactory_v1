#!/usr/bin/env python3
"""Fix remaining D7 API tests with @patch decorators"""

import re

# Read the test file
with open('tests/unit/d7_storefront/test_d7_api.py', 'r') as f:
    content = f.read()

# List of all remaining methods that need fixing
remaining_tests = [
    ('test_success_page_invalid_session', '@patch("d7_storefront.api.get_checkout_manager")'),
    ('test_cancel_page', '@patch("d7_storefront.api.get_checkout_manager")'),
    ('test_get_purchase_history', '@patch("d7_storefront.api.get_checkout_manager")'),
    ('test_get_purchase_details', '@patch("d7_storefront.api.get_checkout_manager")'),
    ('test_simulate_purchase_flow', '@patch("d7_storefront.api.get_checkout_manager")'),
    ('test_webhook_purchase_flow', '@patch("d7_storefront.api.get_checkout_manager")'),
]

fixes_made = 0

for test_name, decorator in remaining_tests:
    # Find and replace the decorator line
    pattern = f'{decorator}\s*\n\s*def {test_name}\(self, mock_get_manager\):'
    replacement = f'def {test_name}(self, mock_checkout_manager):'
    
    if pattern in content:
        content = re.sub(pattern, replacement, content)
        print(f"Fixed decorator for {test_name}")
        fixes_made += 1
        
        # Replace mock_get_manager.return_value = mock_manager
        content = content.replace(
            f'mock_get_manager.return_value = mock_manager',
            '# Fixed to use fixture directly'
        )
        
        # Replace mock_manager references with mock_checkout_manager
        # This is tricky - need to be careful
        # Find the test method and replace within it
        test_pattern = f'def {test_name}.*?(?=\n    def|\nclass|\Z)'
        match = re.search(test_pattern, content, re.DOTALL)
        if match:
            test_content = match.group(0)
            # Replace mock_manager. with mock_checkout_manager.
            fixed_test = test_content.replace('mock_manager = Mock()\n', '')
            fixed_test = fixed_test.replace('mock_manager.', 'mock_checkout_manager.')
            content = content.replace(test_content, fixed_test)
            print(f"  - Fixed mock references in {test_name}")

# Handle the webhook processor test separately
webhook_pattern = r'@patch\("d7_storefront\.api\.get_webhook_processor"\)\s*\n\s*def test_webhook_failure\(self, mock_get_processor\):'
if re.search(webhook_pattern, content):
    content = re.sub(webhook_pattern, 'def test_webhook_failure(self, mock_webhook_processor):', content)
    # Fix the mock references
    content = content.replace('mock_processor = Mock()', '# Use fixture')
    content = content.replace('mock_get_processor.return_value = mock_processor', '# Fixed to use fixture')
    # In the webhook test, replace mock_processor with mock_webhook_processor
    test_pattern = r'def test_webhook_failure.*?(?=\n    def|\nclass|\Z)'
    match = re.search(test_pattern, content, re.DOTALL)
    if match:
        test_content = match.group(0)
        fixed_test = test_content.replace('mock_processor.', 'mock_webhook_processor.')
        content = content.replace(test_content, fixed_test)
    print("Fixed webhook processor test")
    fixes_made += 1

# Write back
with open('tests/unit/d7_storefront/test_d7_api.py', 'w') as f:
    f.write(content)

print(f"\nTotal fixes made: {fixes_made}")
print("\nNote: Manual review recommended to ensure proper formatting")