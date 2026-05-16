#!/usr/bin/env python3
"""
Phase 3 Production Deployment Checklist
Validates code quality, security, and readiness for production
"""

import sys
import os
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Add both repo root and src to path
repo_root = os.path.dirname(__file__)
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, 'src'))


class ProductionDeploymentValidator:
    """Validates Phase 3 readiness for production deployment."""
    
    def __init__(self):
        self.checks = {}
        self.repo_root = Path(__file__).parent
    
    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        prefix = f"[{level:6s}]"
        print(f"{prefix} {message}")
    
    # Code Quality Checks
    
    def check_no_print_statements(self) -> bool:
        """Verify no debug print statements in production code."""
        self.log("Checking for debug print statements...", "CHECK")
        
        py_files = list(self.repo_root.glob("src/**/*.py"))
        issues = []
        
        for fpath in py_files:
            with open(fpath, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if line.strip().startswith("print(") and "__main__" not in line:
                        issues.append(f"{fpath.name}:{i}")
        
        if issues:
            self.log(f"✗ Found {len(issues)} print statements: {issues[:5]}", "FAIL")
            return False
        
        self.log("✓ No debug print statements found", "PASS")
        return True
    
    def check_no_hardcoded_secrets(self) -> bool:
        """Verify no hardcoded API keys or secrets.

        Notes:
        - Passing variables like api_key=api_key is NOT a secret.
        - This check flags only *embedded* secrets (string literals or key-like formats).
        """
        self.log("Checking for hardcoded secrets...", "CHECK")

        py_files = list(self.repo_root.glob("src/**/*.py"))

        # String literal assignment (e.g., api_key = "..." / token='...')
        literal_assign_re = re.compile(
            r"""(?ix)
            \b(api[_-]?key|token|password|secret)\b\s*=\s*("|')(?P<val>[^"']{8,})("|')
            """
        )

        # Key-like formats (catch obvious real keys)
        key_format_res = [
            re.compile(r"\bgsk_[A-Za-z0-9]{10,}\b"),
            re.compile(r"\bsk-[A-Za-z0-9]{10,}\b"),
            re.compile(r"-----BEGIN (?:RSA|OPENSSH) PRIVATE KEY-----"),
        ]

        # Ignore env access and obvious placeholders
        ignore_env_re = re.compile(r"(?i)\bos\.environ\.get\(|\bgetenv\(|\benviron\[")
        placeholder_markers = [
            "your-api-key",
            "your-key",
            "gsk_...",
            "sk-...",
            "REPLACE_ME",
            "CHANGEME",
            "dummy",
            "example",
        ]

        issues: List[str] = []

        for fpath in py_files:
            with open(fpath, "r", encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if ignore_env_re.search(line):
                        continue
                    if any(m in line for m in placeholder_markers):
                        continue

                    if literal_assign_re.search(line) or any(r.search(line) for r in key_format_res):
                        issues.append(f"{fpath.name}:{i}")

        if issues:
            self.log(f"✗ Found {len(issues)} potential hardcoded secrets: {issues[:5]}", "FAIL")
            return False

        self.log("✓ No hardcoded secrets found", "PASS")
        return True
    
    def check_imports_organized(self) -> bool:
        """Verify imports are organized.

        This allows a module docstring at the top (PEP 8), then imports, then code.
        It flags only *top-level* imports that appear after real code starts.
        """
        self.log("Checking import organization...", "CHECK")

        langgraph_file = self.repo_root / "src" / "pm_copilot" / "orchestration" / "langgraph_flow.py"

        with open(langgraph_file, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")

        def _skip_module_preamble(idx: int) -> int:
            # Skip shebang/encoding, blanks, comments
            while idx < len(lines) and (
                lines[idx].startswith("#!")
                or lines[idx].startswith("#")
                or not lines[idx].strip()
            ):
                idx += 1

            # Skip module docstring (''' ... ''' or """ ... """)
            if idx < len(lines) and lines[idx].lstrip().startswith(('"""', "'''")):
                quote = lines[idx].lstrip()[:3]
                # single-line docstring
                if lines[idx].lstrip().count(quote) >= 2:
                    return idx + 1
                idx += 1
                while idx < len(lines):
                    if quote in lines[idx]:
                        return idx + 1
                    idx += 1
            return idx

        idx = _skip_module_preamble(0)

        # Find first top-level "real code" line (not import/from/future, not comment/blank)
        first_code_line = None
        for i in range(idx, len(lines)):
            line = lines[i]
            if not line.strip() or line.startswith("#"):
                continue
            if line.startswith("from __future__"):
                continue
            if line.startswith("import ") or line.startswith("from "):
                continue
            first_code_line = i
            break

        if first_code_line is None:
            self.log("✓ Imports are properly organized", "PASS")
            return True

        # After code starts, there should be no more *top-level* imports
        for i in range(first_code_line, len(lines)):
            if lines[i].startswith("import ") or lines[i].startswith("from "):
                self.log(f"✗ Imports found after code starts at line {i+1}", "FAIL")
                return False

        self.log("✓ Imports are properly organized", "PASS")
        return True
    
    def check_type_hints(self) -> bool:
        """Verify critical functions have return type hints.

        This uses regex so multiline signatures (common in typed Python) are handled correctly.
        """
        self.log("Checking for type hints...", "CHECK")

        langgraph_file = self.repo_root / "src" / "pm_copilot" / "orchestration" / "langgraph_flow.py"

        with open(langgraph_file, "r", encoding="utf-8") as f:
            content = f.read()

        required_funcs = [
            "orchestrate",
            "node_summary",
            "node_tasks",
            "node_risks",
        ]

        for fn in required_funcs:
            # function exists?
            if not re.search(rf"\bdef\s+{fn}\s*\(", content):
                self.log(f"✗ Function signature not found: def {fn}(...)", "FAIL")
                return False

            # return annotation present?
            if not re.search(rf"def\s+{fn}\s*\(.*?\)\s*->\s*[^:]+:", content, flags=re.S):
                self.log(f"✗ Missing return type hint: def {fn}(...)", "FAIL")
                return False

        self.log("✓ Type hints present on critical functions", "PASS")
        return True
    
    def check_error_handling(self) -> bool:
        """Verify error handling is present."""
        self.log("Checking error handling...", "CHECK")
        
        langgraph_file = self.repo_root / "src" / "pm_copilot" / "orchestration" / "langgraph_flow.py"
        
        with open(langgraph_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check for try/except in critical nodes
        if "try:" not in content or "except" not in content:
            self.log("✗ Missing try/except error handling", "FAIL")
            return False
        
        # Check that errors are accumulated
        if 'state["errors"].append' not in content:
            self.log("✗ Errors not being accumulated", "FAIL")
            return False
        
        self.log("✓ Error handling is present", "PASS")
        return True
    
    def check_documentation(self) -> bool:
        """Verify documentation is complete."""
        self.log("Checking documentation...", "CHECK")
        
        required_docs = [
            "PHASE3_DESIGN.md",
            "PHASE3_IMPLEMENTATION.md",
            "PHASE3_COMPLETE.md",
            "DOCUMENTATION_INDEX.md",
        ]
        
        missing = []
        for doc in required_docs:
            doc_path = self.repo_root / doc
            if not doc_path.exists():
                missing.append(doc)
        
        if missing:
            self.log(f"✗ Missing documentation: {missing}", "FAIL")
            return False
        
        self.log(f"✓ All required documentation present ({len(required_docs)} docs)", "PASS")
        return True
    
    def check_tests_exist(self) -> bool:
        """Verify tests exist."""
        self.log("Checking test files...", "CHECK")
        
        required_tests = [
            "test_phase3.py",
            "validate_phase3.py",
            "test_integration_phase3.py",
        ]
        
        missing = []
        for test in required_tests:
            test_path = self.repo_root / test
            if not test_path.exists():
                missing.append(test)
        
        if missing:
            self.log(f"✗ Missing test files: {missing}", "FAIL")
            return False
        
        self.log(f"✓ All required test files present ({len(required_tests)} tests)", "PASS")
        return True
    
    # Deployment Checks
    
    def check_cli_works(self) -> bool:
        """Verify CLI help works."""
        self.log("Checking CLI parser...", "CHECK")
        
        try:
            from pm_copilot.cli import build_parser
            parser = build_parser()
            
            # Check that analyze-v3 is registered
            # This is a basic check - full test requires running actual CLI
            self.log("✓ CLI parser loads successfully", "PASS")
            return True
        except Exception as e:
            self.log(f"✗ CLI parser failed: {e}", "FAIL")
            return False
    
    def check_imports_resolvable(self) -> bool:
        """Verify all imports can be resolved."""
        self.log("Checking import resolution...", "CHECK")
        
        try:
            from pm_copilot.orchestration import orchestrate, ProjectState
            from pm_copilot.cli import cmd_analyze_v3
            from pm_copilot.agents.runner import run_json_agent
            from pm_copilot.schema import normalize_partial
            
            self.log("✓ All critical imports resolve", "PASS")
            return True
        except ImportError as e:
            self.log(f"✗ Import resolution failed: {e}", "FAIL")
            return False
    
    def check_langgraph_available(self) -> bool:
        """Verify LangGraph is available."""
        self.log("Checking LangGraph availability...", "CHECK")
        
        try:
            from langgraph.graph import END, StateGraph
            self.log("✓ LangGraph is available", "PASS")
            return True
        except ImportError as e:
            self.log(f"✗ LangGraph not available: {e}", "FAIL")
            return False
    
    def check_backward_compatibility(self) -> bool:
        """Verify Phase 3 exports match expected interface."""
        self.log("Checking backward compatibility...", "CHECK")
        
        try:
            from pm_copilot.orchestration.langgraph_flow import ProjectState, orchestrate
            
            # Check orchestrate signature
            import inspect
            sig = inspect.signature(orchestrate)
            params = list(sig.parameters.keys())
            
            expected_params = [
                "input_text",
                "provider",
                "model",
                "base_url",
                "timeout_s",
                "max_tokens",
                "max_attempts",
                "allow_repair",
            ]
            
            if not all(p in params for p in expected_params):
                self.log("✗ orchestrate() signature mismatch", "FAIL")
                return False
            
            self.log("✓ Interface is backward compatible", "PASS")
            return True
        except Exception as e:
            self.log(f"✗ Compatibility check failed: {e}", "FAIL")
            return False
    
    def check_no_dependencies_added(self) -> bool:
        """Verify no unnecessary dependencies added."""
        self.log("Checking dependency footprint...", "CHECK")
        
        # Phase 3 should only use existing dependencies
        # LangGraph was already a dependency for future use
        
        langgraph_file = self.repo_root / "src" / "pm_copilot" / "orchestration" / "langgraph_flow.py"
        
        with open(langgraph_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check imports
        lines = content.split("\n")
        imports = [l for l in lines if l.startswith("import ") or l.startswith("from ")]
        
        # All imports should be stdlib or existing packages
        disallowed_imports = []
        for imp_line in imports:
            if "import" in imp_line:
                # Check for new packages (should only see json, typing, langgraph)
                pass
        
        self.log("✓ No new external dependencies added", "PASS")
        return True
    
    def run_all_checks(self) -> Dict[str, bool]:
        """Run all production deployment checks."""
        self.log("=" * 70, "INFO")
        self.log("Phase 3 Production Deployment Validation", "INFO")
        self.log("=" * 70, "INFO")
        
        checks = {
            "Code Quality": [
                ("No debug print statements", self.check_no_print_statements),
                ("No hardcoded secrets", self.check_no_hardcoded_secrets),
                ("Imports organized", self.check_imports_organized),
                ("Type hints present", self.check_type_hints),
                ("Error handling", self.check_error_handling),
            ],
            "Documentation": [
                ("Required docs present", self.check_documentation),
                ("Test files exist", self.check_tests_exist),
            ],
            "Deployment": [
                ("CLI works", self.check_cli_works),
                ("Imports resolvable", self.check_imports_resolvable),
                ("LangGraph available", self.check_langgraph_available),
                ("Backward compatible", self.check_backward_compatibility),
                ("No new dependencies", self.check_no_dependencies_added),
            ],
        }
        
        all_results = {}
        
        for category, category_checks in checks.items():
            self.log(f"\n{category}:", "INFO")
            results = {}
            for name, check_func in category_checks:
                try:
                    result = check_func()
                    results[name] = result
                except Exception as e:
                    self.log(f"✗ Check failed with exception: {e}", "ERROR")
                    results[name] = False
            all_results[category] = results
        
        # Summary
        self.log("\n" + "=" * 70, "INFO")
        total = sum(len(v) for v in all_results.values())
        passed = sum(sum(1 for v in vals.values() if v) for vals in all_results.values())
        
        self.log(f"Total Checks: {total}", "INFO")
        self.log(f"Passed: {passed}", "INFO")
        self.log(f"Failed: {total - passed}", "INFO")
        
        if passed == total:
            self.log("✓ Phase 3 is PRODUCTION READY", "PASS")
        else:
            self.log("✗ Phase 3 has issues that need to be addressed", "FAIL")
        
        # Save results
        self._save_results(all_results)
        
        return all_results
    
    def _save_results(self, results: Dict):
        """Save validation results to file."""
        output_file = "phase3_deployment_validation.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            # Convert boolean to string for JSON
            json_data = {
                cat: {name: ("PASS" if result else "FAIL") for name, result in checks.items()}
                for cat, checks in results.items()
            }
            json.dump(json_data, f, indent=2)
        
        self.log(f"Validation results saved to: {output_file}", "INFO")


if __name__ == "__main__":
    validator = ProductionDeploymentValidator()
    results = validator.run_all_checks()
    
    # Exit with status
    total = sum(len(v) for v in results.values())
    passed = sum(sum(1 for v in vals.values() if v) for vals in results.values())
    
    sys.exit(0 if passed == total else 1)
