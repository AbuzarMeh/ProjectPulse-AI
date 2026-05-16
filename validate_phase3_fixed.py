#!/usr/bin/env python3
"""
Phase 3 Implementation Validation - FIXED VERSION
Validates package structure and basic imports
"""

import sys
import os
from pathlib import Path

repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / 'src'))

print("Phase 3 Implementation Validation")
print("=" * 70)
print()

errors = []
passed = 0

# Test 1: Check directory structure
print("1. Checking directory structure...")
required_dirs = [
    'src/pm_copilot',
    'src/pm_copilot/orchestration',
    'src/pm_copilot/agents',
]
for d in required_dirs:
    path = repo_root / d
    if path.exists():
        print(f"   ✓ {d}/ exists")
        passed += 1
    else:
        print(f"   ✗ {d}/ missing")
        errors.append(f"Missing directory: {d}")

print()

# Test 2: Check __init__.py files
print("2. Checking package __init__.py files...")
required_inits = [
    'src/__init__.py',
    'src/pm_copilot/__init__.py',
    'src/pm_copilot/orchestration/__init__.py',
    'src/pm_copilot/agents/__init__.py',
]
for f in required_inits:
    path = repo_root / f
    if path.exists():
        print(f"   ✓ {f} exists")
        passed += 1
    else:
        print(f"   ✗ {f} missing")
        errors.append(f"Missing __init__.py: {f}")

print()

# Test 3: Check core files exist
print("3. Checking core implementation files...")
required_files = [
    'src/pm_copilot/orchestration/langgraph_flow.py',
    'src/pm_copilot/agents/phase2.py',
    'src/pm_copilot/cli.py',
]
for f in required_files:
    path = repo_root / f
    if path.exists():
        size = path.stat().st_size
        print(f"   ✓ {f} ({size} bytes)")
        passed += 1
    else:
        print(f"   ✗ {f} missing")
        errors.append(f"Missing file: {f}")

print()

# Test 4: Try basic imports
print("4. Testing basic imports...")
try:
    from pm_copilot.orchestration import orchestrate, ProjectState
    print("   ✓ orchestrate and ProjectState imported successfully")
    passed += 1
except ImportError as e:
    print(f"   ✗ Failed to import orchestration: {e}")
    errors.append(f"Import failed: {e}")

try:
    from pm_copilot.agents.phase2 import analyze_v2
    print("   ✓ analyze_v2 imported successfully")
    passed += 1
except ImportError as e:
    print(f"   ✗ Failed to import phase2: {e}")
    errors.append(f"Import failed: {e}")

try:
    from pm_copilot.cli import build_parser
    print("   ✓ CLI parser imported successfully")
    passed += 1
except ImportError as e:
    print(f"   ✗ Failed to import CLI: {e}")
    errors.append(f"Import failed: {e}")

print()
print("=" * 70)
print()

if errors:
    print(f"✗ {len(errors)} validation error(s) found:")
    for i, err in enumerate(errors, 1):
        print(f"   {i}. {err}")
    sys.exit(1)
else:
    print(f"✓ All {passed} validation checks passed!")
    print()
    print("Phase 3 is ready for testing.")
    print()
    print("Next steps:")
    print("  1. Run: python check_production_readiness.py")
    print("  2. Then: export GROQ_API_KEY='...' && python test_integration_phase3.py")
    print("  3. Finally: python test_uat_phase3.py")
    sys.exit(0)
