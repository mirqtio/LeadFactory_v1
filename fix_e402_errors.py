#!/usr/bin/env python3
"""
Fix E402 errors by adding noqa comments where imports need to be after sys.path modifications
"""

from pathlib import Path

def fix_e402_in_file(file_path):
    """Fix E402 errors in a single file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    modified = False
    
    # Look for pattern: sys.path modifications followed by imports
    for i, line in enumerate(lines):
        # If we see sys.path.insert or similar, mark following imports
        if 'sys.path.insert' in line or 'sys.path.append' in line:
            # Add noqa to imports in the next few lines
            for j in range(i + 1, min(i + 20, len(lines))):
                next_line = lines[j].strip()
                
                # Skip empty lines and comments
                if not next_line or next_line.startswith('#'):
                    continue
                    
                # If it's an import and doesn't have noqa
                if (next_line.startswith('import ') or next_line.startswith('from ')) and '# noqa' not in next_line:
                    # Add noqa comment
                    lines[j] = lines[j] + '  # noqa: E402'
                    modified = True
                    print(f"  Fixed: {next_line}")
                    
                # Stop when we hit non-import lines
                elif not (next_line.startswith('import ') or next_line.startswith('from ')):
                    break
    
    if modified:
        with open(file_path, 'w') as f:
            f.write('\n'.join(lines))
        return True
    return False

def main():
    """Fix E402 errors in all Python files"""
    project_root = Path(__file__).parent
    
    # Find files with E402 errors
    import subprocess
    try:
        result = subprocess.run(
            ['ruff', 'check', '.', '--select=E402', '--output-format=json'],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        
        if result.returncode != 0:
            # Parse the output to get files with E402 errors
            import json
            try:
                errors = json.loads(result.stdout)
                files_with_errors = set()
                for error in errors:
                    if error.get('code') == 'E402':
                        files_with_errors.add(Path(error['filename']))
                
                fixed_count = 0
                for file_path in files_with_errors:
                    if file_path.suffix == '.py' and file_path.exists():
                        print(f"Checking {file_path}")
                        if fix_e402_in_file(file_path):
                            fixed_count += 1
                
                print(f"\nFixed {fixed_count} files with E402 errors")
                
            except json.JSONDecodeError:
                print("Could not parse ruff output as JSON")
        
    except FileNotFoundError:
        print("ruff not found, using fallback method")
        # Fallback: check common script patterns
        script_files = list(project_root.glob('scripts/*.py'))
        test_files = list(project_root.glob('tests/**/*.py'))
        
        all_files = script_files + test_files
        fixed_count = 0
        
        for file_path in all_files:
            if fix_e402_in_file(file_path):
                fixed_count += 1
        
        print(f"\nFixed {fixed_count} files using fallback method")

if __name__ == "__main__":
    main()