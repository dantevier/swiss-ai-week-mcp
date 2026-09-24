#!/usr/bin/env python3
"""
Automated script to rename MCP boilerplate project.
Usage: python rename_project.py <new_project_name>
"""

import os
import re
import sys
from pathlib import Path
import shutil
import argparse


def validate_project_name(name):
    """Validate project name follows Python package naming conventions."""
    if not re.match(r'^[a-z][a-z0-9_]*$', name):
        raise ValueError(
            f"Invalid project name '{name}'. Must start with lowercase letter "
            "and contain only lowercase letters, numbers, and underscores."
        )


def update_file_content(file_path, old_name, new_name):
    """Update imports and references in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace package imports
        content = re.sub(
            rf'\bfrom {old_name}\b',
            f'from {new_name}',
            content
        )
        content = re.sub(
            rf'\bimport {old_name}\b',
            f'import {new_name}',
            content
        )
        content = re.sub(
            rf'\b{old_name}\.',
            f'{new_name}.',
            content
        )
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
        return False


def update_pyproject_toml(file_path, old_name, new_name):
    """Update pyproject.toml with new package name."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Update package name
        content = re.sub(
            r'^name = ".*"',
            f'name = "{new_name}"',
            content,
            flags=re.MULTILINE
        )
        
        # Update package references
        content = re.sub(
            rf'\b{old_name}\b',
            new_name,
            content
        )
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"Error updating pyproject.toml: {e}")
        return False


def rename_project(new_name, dry_run=False):
    """Rename the MCP boilerplate project."""
    old_name = "mcp_boilerplate"
    project_root = Path.cwd()
    src_dir = project_root / "src"
    old_package_dir = src_dir / old_name
    new_package_dir = src_dir / new_name
    
    print(f"Renaming project from '{old_name}' to '{new_name}'")
    
    if dry_run:
        print("DRY RUN MODE - No changes will be made")
    
    # Check if old package directory exists
    if not old_package_dir.exists():
        print(f"Error: {old_package_dir} does not exist")
        return False
    
    # Check if new package directory already exists
    if new_package_dir.exists():
        print(f"Error: {new_package_dir} already exists")
        return False
    
    files_to_update = []
    
    # Find all Python files to update (excluding .venv)
    for py_file in project_root.rglob("*.py"):
        if (".git" not in str(py_file) and "__pycache__" not in str(py_file) 
            and ".venv" not in str(py_file)):
            files_to_update.append(py_file)
    
    # Add pyproject.toml
    pyproject_file = project_root / "pyproject.toml"
    if pyproject_file.exists():
        files_to_update.append(pyproject_file)
    
    print(f"Found {len(files_to_update)} files to update")
    
    if dry_run:
        print(f"Would rename: {old_package_dir} -> {new_package_dir}")
        for file_path in files_to_update:
            print(f"Would update: {file_path}")
        return True
    
    # Rename the package directory
    try:
        shutil.move(str(old_package_dir), str(new_package_dir))
        print(f"Renamed directory: {old_package_dir} -> {new_package_dir}")
    except Exception as e:
        print(f"Error renaming directory: {e}")
        return False
    
    # Update file contents
    success_count = 0
    for file_path in files_to_update:
        if file_path.name == "pyproject.toml":
            if update_pyproject_toml(file_path, old_name, new_name):
                success_count += 1
                print(f"Updated: {file_path}")
        else:
            if update_file_content(file_path, old_name, new_name):
                success_count += 1
                print(f"Updated: {file_path}")
    
    print(f"Successfully updated {success_count}/{len(files_to_update)} files")
    
    # Update CLAUDE.md if it exists
    claude_md = project_root / "CLAUDE.md"
    if claude_md.exists():
        try:
            with open(claude_md, 'r', encoding='utf-8') as f:
                content = f.read()
            
            content = content.replace(old_name, new_name)
            
            with open(claude_md, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"Updated: {claude_md}")
        except Exception as e:
            print(f"Warning: Could not update CLAUDE.md: {e}")
    
    print(f"Project renamed successfully to '{new_name}'!")
    print("Don't forget to:")
    print("1. Update any additional configuration files")
    print("2. Test the renamed project")
    print("3. Update git remote if needed")
    
    return True


def main():
    parser = argparse.ArgumentParser(description="Rename MCP boilerplate project")
    parser.add_argument("name", help="New project name (lowercase, underscores allowed)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without making changes")
    
    args = parser.parse_args()
    
    try:
        validate_project_name(args.name)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    success = rename_project(args.name, args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()