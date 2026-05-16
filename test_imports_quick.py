#!/usr/bin/env python3
"""Quick import test to debug path issues."""

import os
import sys

repo_root = os.path.dirname(__file__)
print(f"Repo root: {repo_root}")

# Add both repo and src to path.
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, "src"))

print(f"Python path: {sys.path[:3]}")
print()

print("Test 1: Import orchestrate from pm_copilot.orchestration")
try:
    from pm_copilot.orchestration import orchestrate

    print(f"  [PASS] SUCCESS: {orchestrate}")
except Exception as e:
    print(f"  [FAIL] FAILED: {e}")

print()

print("Test 2: Import ProjectState from pm_copilot.orchestration")
try:
    from pm_copilot.orchestration import ProjectState

    print(f"  [PASS] SUCCESS: {ProjectState}")
except Exception as e:
    print(f"  [FAIL] FAILED: {e}")

print()

print("Test 3: Import analyze_v2 from pm_copilot.agents.phase2")
try:
    from pm_copilot.agents.phase2 import analyze_v2

    print(f"  [PASS] SUCCESS: {analyze_v2}")
except Exception as e:
    print(f"  [FAIL] FAILED: {e}")

print()

print("Test 4: Import CLI")
try:
    from pm_copilot.cli import build_parser

    print(f"  [PASS] SUCCESS: {build_parser}")
except Exception as e:
    print(f"  [FAIL] FAILED: {e}")

print()
print("=" * 60)
print("If all tests passed, the package structure is correct!")
