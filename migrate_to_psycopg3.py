#!/usr/bin/env python3
"""
Script to migrate app.py from psycopg2 to psycopg (version 3)
Usage: python migrate_to_psycopg3.py path/to/app.py
"""

import sys
import re
from pathlib import Path

def migrate_app_py(filepath):
    """Migrate app.py from psycopg2 to psycopg3"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # 1. Replace imports
    content = content.replace('import psycopg2', 'import psycopg')
    content = content.replace('from psycopg2 import sql', 'from psycopg import sql')
    content = content.replace('from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT', 
                             'from psycopg import IsolationLevel')
    
    # 2. Replace psycopg2.connect with psycopg.connect
    content = content.replace('psycopg2.connect', 'psycopg.connect')
    
    # 3. Replace exception handling
    content = content.replace('psycopg2.IntegrityError', 'psycopg.IntegrityError')
    content = content.replace('except psycopg2.', 'except psycopg.')
    
    # 4. Replace isolation level setting
    content = re.sub(
        r'conn\.set_isolation_level\(ISOLATION_LEVEL_AUTOCOMMIT\)',
        'conn.autocommit = True',
        content
    )
    
    # 5. Clean up connection strings (remove extra quotes)
    # This pattern finds the old-style connection string
    old_pattern = r'f"dbname=\'{([^}]+)}\' user=\'{([^}]+)}\' password=\'{([^}]+)}\' host=\'{([^}]+)}\' port=\'{([^}]+)}\'"'
    new_pattern = r'f"dbname={} user={} password={} host={} port={}"'
    
    if 'TARGET_CONN_STR' in content:
        # Update TARGET_CONN_STR
        content = re.sub(
            r'TARGET_CONN_STR = \(\s*f"dbname=\'[^\']+\' user=\'[^\']+\' password=\'[^\']+\' host=\'[^\']+\' port=\'[^\']+\'"\s*\)',
            f'''TARGET_CONN_STR = (
    f"dbname={{DB_NAME}} user={{DB_USER}} password={{DB_PASSWORD}} host={{DB_HOST}} port={{DB_PORT}}"
)''',
            content
        )
    
    # Check if changes were made
    if content == original_content:
        print("⚠ No changes needed - file might already be migrated or no psycopg2 references found")
        return False
    
    # Create backup
    backup_path = Path(filepath).with_suffix('.py.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(original_content)
    print(f"✓ Backup created: {backup_path}")
    
    # Write migrated content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ Migrated: {filepath}")
    
    return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python migrate_to_psycopg3.py path/to/app.py")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    if not Path(filepath).exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    
    print(f"Migrating {filepath} from psycopg2 to psycopg3...")
    print("-" * 60)
    
    success = migrate_app_py(filepath)
    
    print("-" * 60)
    if success:
        print("✓ Migration complete!")
        print("\nNext steps:")
        print("1. Review the changes in your app.py")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Test your application: python app.py")
    else:
        print("Migration skipped - no changes made")