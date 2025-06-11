#!/usr/bin/env python3
"""
Script to fix all remaining D7 API tests that use the old @patch pattern
"""

import re
import sys

def fix_d7_api_tests():
    """Fix all remaining FastAPI dependency tests in D7 API module."""
    
    # Read the test file
    with open('tests/unit/d7_storefront/test_d7_api.py', 'r') as f:
        content = f.read()
    
    # Pattern to find test methods with @patch decorator for get_checkout_manager
    pattern = r'(@patch\("d7_storefront\.api\.get_checkout_manager"\)\s*\n\s*def\s+(\w+)\(self,\s*mock_get_manager\):)'
    
    fixes_made = 0
    
    # Find all matches
    for match in re.finditer(pattern, content):
        full_match = match.group(0)
        method_name = match.group(2)
        
        # Replace the decorator and method signature
        new_signature = f'def {method_name}(self):'
        content = content.replace(full_match, new_signature)
        
        # Find the mock_get_manager.return_value line
        mock_pattern = rf'(mock_get_manager\.return_value = mock_manager\s*\n)'
        mock_replacement = r'''
        # Override the FastAPI dependency for this test
        from d7_storefront.api import get_checkout_manager
        app.dependency_overrides[get_checkout_manager] = lambda: mock_manager

        try:
'''
        
        # Find where to add the finally block
        # Look for the assertions section
        test_end_pattern = rf'({method_name}.*?)(^    def|\Z)'
        
        fixes_made += 1
        print(f"Fixing test: {method_name}")
    
    # Now fix the mock_get_manager.return_value lines
    content = re.sub(
        r'mock_get_manager\.return_value = mock_manager\s*\n',
        '''
        # Override the FastAPI dependency for this test
        from d7_storefront.api import get_checkout_manager
        app.dependency_overrides[get_checkout_manager] = lambda: mock_manager

        try:
''',
        content
    )
    
    # Add finally blocks after response assertions
    # This is tricky - we need to add indentation to existing code
    lines = content.split('\n')
    new_lines = []
    in_try_block = False
    indent_level = 0
    
    for i, line in enumerate(lines):
        if 'app.dependency_overrides[get_checkout_manager]' in line and i + 2 < len(lines) and 'try:' in lines[i + 2]:
            in_try_block = True
            indent_level = len(line) - len(line.lstrip())
        
        if in_try_block and line.strip() and not line.strip().startswith('#'):
            # Check if this is the start of a new method or class
            if (line.lstrip().startswith('def ') or line.lstrip().startswith('class ')) and not line.startswith(' ' * (indent_level + 4)):
                # Add finally block before new method/class
                new_lines.append(' ' * (indent_level + 8) + 'finally:')
                new_lines.append(' ' * (indent_level + 12) + '# Clean up dependency override')
                new_lines.append(' ' * (indent_level + 12) + 'app.dependency_overrides.clear()')
                new_lines.append('')
                in_try_block = False
            elif in_try_block and i < len(lines) - 1:
                # Add extra indentation for code in try block
                if not line.lstrip().startswith('try:') and len(line) > indent_level:
                    line = '    ' + line
        
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    # Write the fixed content back
    with open('tests/unit/d7_storefront/test_d7_api.py', 'w') as f:
        f.write(content)
    
    print(f"\nFixed {fixes_made} test methods")
    print("Manual review may be needed for proper indentation and finally blocks")

if __name__ == '__main__':
    fix_d7_api_tests()