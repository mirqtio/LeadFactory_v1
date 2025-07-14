#!/usr/bin/env python3
"""
Fix model imports in conftest.py files by adding # noqa: F401 comments
These imports are needed for SQLAlchemy model registration
"""

import re
from pathlib import Path

def fix_conftest_file(file_path):
    """Fix a single conftest.py file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern to match import lines that need noqa comments
    patterns = [
        (r'^(\s*import\s+\w+\.models)(\s*#.*)?$', r'\1  # noqa: F401'),
        (r'^(\s*import\s+database\.models)(\s*#.*)?$', r'\1  # noqa: F401'),
        (r'^(\s*import\s+database\.governance_models)(\s*#.*)?$', r'\1  # noqa: F401'),
        (r'^(\s*import\s+lead_explorer\.models)(\s*#.*)?$', r'\1  # noqa: F401'),
        (r'^(\s*from\s+\w+\.models\s+import\s+.*)(\s*#.*)?$', r'\1  # noqa: F401'),
    ]
    
    lines = content.split('\n')
    modified = False
    
    for i, line in enumerate(lines):
        for pattern, replacement in patterns:
            if re.match(pattern, line, re.MULTILINE):
                # Only add noqa if not already present
                if '# noqa' not in line:
                    new_line = re.sub(pattern, replacement, line)
                    if new_line != line:
                        lines[i] = new_line
                        modified = True
                        print(f"  Fixed: {line.strip()} -> {new_line.strip()}")
    
    if modified:
        with open(file_path, 'w') as f:
            f.write('\n'.join(lines))
        return True
    return False

def main():
    """Fix all conftest.py files"""
    project_root = Path(__file__).parent
    conftest_files = list(project_root.rglob('conftest.py'))
    
    fixed_count = 0
    for conftest_file in conftest_files:
        print(f"Checking {conftest_file}")
        if fix_conftest_file(conftest_file):
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} conftest.py files")

if __name__ == "__main__":
    main()