#!/usr/bin/env python3
"""
Simple patch to enable CRUD operations for ABAP development objects.

This script modifies the odata_mcp.py to force-enable create/delete operations
for specific entity sets that are marked as read-only in the metadata.
"""

import re
import shutil
from pathlib import Path

def patch_odata_mcp():
    """Apply patch to enable CRUD operations."""
    
    # Read the original file
    original_file = Path("odata_mcp.py")
    if not original_file.exists():
        print("Error: odata_mcp.py not found!")
        return False
    
    # Create backup
    backup_file = Path("odata_mcp_original.py")
    if not backup_file.exists():
        shutil.copy(original_file, backup_file)
        print(f"Created backup: {backup_file}")
    
    content = original_file.read_text()
    
    # Find the entity set parsing section
    pattern = r'(entity_sets\[name\] = EntitySet\(\s*name=name,\s*entity_type=entity_type_name,\s*creatable=creatable,\s*updatable=updatable,\s*deletable=deletable,)'
    
    # Check if already patched
    if "# PATCH: Override for development objects" in content:
        print("File already patched!")
        return True
    
    # Create the patch
    replacement = r'''\1
                searchable=searchable,
                description=description
            )
            
            # PATCH: Override for development objects
            dev_entity_sets = ['PROGRAMSet', 'CLASSSet', 'INTERFACESet']
            if name in dev_entity_sets:
                entity_sets[name].creatable = True
                entity_sets[name].updatable = True
                entity_sets[name].deletable = True
                self._log_verbose(f"Overriding {name} to be fully writable")
            
            continue  # Skip the original assignment
            
            entity_sets[name] = EntitySet(
                name=name,
                entity_type=entity_type_name,
                creatable=creatable,
                updatable=updatable,
                deletable=deletable,'''
    
    # Apply the patch
    patched_content = re.sub(pattern, replacement, content)
    
    if patched_content == content:
        # Try alternative pattern
        print("Trying alternative patch location...")
        
        # Find where entity sets are created and add override logic after
        insert_point = "entity_sets[name] = EntitySet("
        lines = content.split('\n')
        patched_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            patched_lines.append(line)
            
            # Look for EntitySet creation
            if insert_point in line and "creatable=" in lines[i:i+10]:
                # Find the closing parenthesis
                j = i
                paren_count = 1
                while j < len(lines) and paren_count > 0:
                    j += 1
                    if j < len(lines):
                        paren_count += lines[j].count('(') - lines[j].count(')')
                        patched_lines.append(lines[j])
                
                # Add override logic
                indent = "            "
                patched_lines.extend([
                    "",
                    f"{indent}# PATCH: Override for development objects",
                    f"{indent}dev_entity_sets = ['PROGRAMSet', 'CLASSSet', 'INTERFACESet']",
                    f"{indent}if name in dev_entity_sets:",
                    f"{indent}    entity_sets[name].creatable = True",
                    f"{indent}    entity_sets[name].updatable = True", 
                    f"{indent}    entity_sets[name].deletable = True",
                    f"{indent}    self._log_verbose(f'Overriding {{name}} to be fully writable')",
                    ""
                ])
                i = j
            i += 1
        
        patched_content = '\n'.join(patched_lines)
    
    # Write the patched file
    original_file.write_text(patched_content)
    print("Successfully patched odata_mcp.py!")
    print("Entity sets PROGRAMSet, CLASSSet, and INTERFACESet are now writable.")
    return True


def unpatch_odata_mcp():
    """Restore original file from backup."""
    backup_file = Path("odata_mcp_original.py")
    original_file = Path("odata_mcp.py")
    
    if backup_file.exists():
        shutil.copy(backup_file, original_file)
        print("Restored original odata_mcp.py from backup")
        return True
    else:
        print("No backup file found!")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--unpatch":
        unpatch_odata_mcp()
    else:
        patch_odata_mcp()
        print("\nTo restore the original file, run: python enable_crud_patch.py --unpatch")