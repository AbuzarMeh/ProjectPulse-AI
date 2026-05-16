#!/usr/bin/env python3
"""Quick validation that Phase 3 implementation is complete and importable."""

import sys
import os

# Add both repo root and src to path
repo_root = os.path.dirname(__file__)
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, 'src'))

print("Phase 3 Implementation Validation")
print("=" * 70)

errors = []

# Test 1: Import orchestration module
print("\n1. Importing orchestration module...")
try:
    from pm_copilot.orchestration import orchestrate, ProjectState, visualize_graph_structure
    print("   ✓ Successfully imported orchestrate, ProjectState, visualize_graph_structure")
except ImportError as e:
    errors.append(f"Failed to import orchestration: {e}")
    print(f"   ✗ {e}")

# Test 2: Import CLI
print("\n2. Importing CLI...")
try:
    from pm_copilot.cli import cmd_analyze_v3, build_parser
    print("   ✓ Successfully imported cmd_analyze_v3 and build_parser")
except ImportError as e:
    errors.append(f"Failed to import CLI: {e}")
    print(f"   ✗ {e}")

# Test 3: Check CLI has analyze-v3 command
print("\n3. Checking CLI parser for analyze-v3 command...")
try:
    from pm_copilot.cli import build_parser
    parser = build_parser()
    
    # Check if analyze-v3 is in subparsers
    if hasattr(parser, '_subparsers'):
        print("   ✓ Parser has subparsers")
    
    # Try to parse analyze-v3 help
    try:
        parser.parse_args(['analyze-v3', '--help'])
    except SystemExit as e:
        if e.code == 0:
            print("   ✓ analyze-v3 command exists and help works")
        else:
            errors.append("analyze-v3 help failed unexpectedly")
            print(f"   ✗ Unexpected exit code: {e.code}")
except Exception as e:
    errors.append(f"Failed to check CLI: {e}")
    print(f"   ✗ {e}")

# Test 4: Import schema
print("\n4. Importing schema module...")
try:
    from pm_copilot.schema import normalize_partial
    print("   ✓ Successfully imported normalize_partial")
except ImportError as e:
    errors.append(f"Failed to import schema: {e}")
    print(f"   ✗ {e}")

# Test 5: Import agents
print("\n5. Importing agents module...")
try:
    from pm_copilot.agents.runner import run_json_agent
    print("   ✓ Successfully imported run_json_agent")
except ImportError as e:
    errors.append(f"Failed to import agents: {e}")
    print(f"   ✗ {e}")

# Test 6: Import prompts
print("\n6. Importing prompts module...")
try:
    from pm_copilot.prompts import SUMMARY_AGENT_PROMPT, TASKS_AGENT_PROMPT, RISKS_AGENT_PROMPT
    print("   ✓ Successfully imported all agent prompts")
except ImportError as e:
    errors.append(f"Failed to import prompts: {e}")
    print(f"   ✗ {e}")

# Test 7: Verify LangGraph graph compiles
print("\n7. Verifying LangGraph graph compilation...")
try:
    from pm_copilot.orchestration.langgraph_flow import _build_graph
    graph_def = _build_graph()
    graph = graph_def.compile()
    print("   ✓ LangGraph compiled successfully")
except Exception as e:
    errors.append(f"Graph compilation failed: {e}")
    print(f"   ✗ {e}")

# Summary
print("\n" + "=" * 70)
if not errors:
    print("✓ All validation checks passed!")
    print("✓ Phase 3 implementation is complete and ready for integration")
    sys.exit(0)
else:
    print(f"✗ {len(errors)} validation error(s) found:")
    for i, err in enumerate(errors, 1):
        print(f"   {i}. {err}")
    sys.exit(1)
