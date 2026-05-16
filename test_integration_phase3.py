#!/usr/bin/env python3
"""
Phase 3 Integration Testing Suite
Tests Phase 3 orchestration against real LLMs and compares with Phase 2
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Tuple

# Ensure src is on path
repo_root = os.path.dirname(__file__)
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, 'src'))

from pm_copilot.agents.phase2 import analyze_v2
from pm_copilot.orchestration.langgraph_flow import orchestrate


# Test scenarios
TEST_SCENARIOS = {
    "basic": """
    Project Status Update - Week of May 15, 2026
    
    Progress:
    - Phase 1 MVP completed and tested successfully
    - Phase 2 multi-agent architecture implemented
    - Phase 3 LangGraph orchestration completed
    
    Current Blockers:
    - Need to confirm deployment strategy
    - API key management for Groq in production
    
    Next Steps:
    - Integration testing with real LLMs
    - User acceptance testing
    - Production deployment planning
    """,
    
    "empty_tasks": """
    Project Status Update - No specific action items
    
    This week we focused on planning and design work.
    No concrete tasks were assigned, just strategic discussions.
    The team is aligned on the architecture direction.
    """,
    
    "complex": """
    AI Project Manager Copilot - Detailed Status Report
    
    COMPLETED ITEMS:
    - Phase 1: Single-agent MVP with JSON output validation
    - Phase 2: Multi-agent separation (Summary, Tasks, Risks agents)
    - Phase 3: LangGraph stateful orchestration with centralized state
    
    CURRENT ITEMS:
    - Integration testing with Groq and Ollama LLM providers
    - Output comparison between Phase 2 and Phase 3 implementations
    - Production deployment preparation
    - User acceptance testing with real project updates
    
    RISKS:
    - LLM model availability changes (Groq has deprecated models before)
    - API rate limits during integration testing
    - Performance degradation with complex project updates
    - State persistence and memory scaling
    
    FOLLOW-UPS:
    - Confirm production deployment timeline
    - Set up monitoring and logging for production
    - Plan Phase 4 (n8n automation layer)
    - Gather user feedback on Phase 3 output quality
    """,
}


class IntegrationTester:
    """Phase 3 integration test executor."""
    
    def __init__(self):
        self.results = []
        self.start_time = datetime.now()
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}] [{level}]"
        print(f"{prefix} {message}")
        
    def test_groq_v3(self, scenario_name: str, input_text: str) -> Dict[str, Any]:
        """Test Phase 3 with Groq provider."""
        self.log(f"Testing Phase 3 with Groq ({scenario_name})...", "TEST")
        
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not groq_key:
            self.log("GROQ_API_KEY not set; skipping Groq test", "WARN")
            return {"status": "SKIPPED", "reason": "API key not set"}
        
        try:
            start = time.time()
            result = orchestrate(
                input_text=input_text,
                provider="groq",
                model="llama-3.3-70b-versatile",
                base_url="https://api.groq.com/openai/v1",
                timeout_s=60,
                max_tokens=512,
                max_attempts=2,
                allow_repair=True,
            )
            elapsed = time.time() - start
            
            self.log(f"✓ Groq Phase 3 completed in {elapsed:.2f}s", "PASS")
            return {
                "status": "PASS",
                "provider": "groq",
                "result": result,
                "elapsed_s": elapsed,
            }
        except Exception as e:
            self.log(f"✗ Groq Phase 3 failed: {e}", "FAIL")
            return {
                "status": "FAIL",
                "provider": "groq",
                "error": str(e),
            }
    
    def test_ollama_v3(self, scenario_name: str, input_text: str) -> Dict[str, Any]:
        """Test Phase 3 with Ollama provider."""
        self.log(f"Testing Phase 3 with Ollama ({scenario_name})...", "TEST")
        
        try:
            start = time.time()
            result = orchestrate(
                input_text=input_text,
                provider="ollama",
                model="phi3",
                base_url="http://localhost:11434",
                timeout_s=60,
                max_tokens=512,
                max_attempts=2,
                allow_repair=True,
            )
            elapsed = time.time() - start
            
            self.log(f"✓ Ollama Phase 3 completed in {elapsed:.2f}s", "PASS")
            return {
                "status": "PASS",
                "provider": "ollama",
                "result": result,
                "elapsed_s": elapsed,
            }
        except Exception as e:
            self.log(f"✗ Ollama Phase 3 failed: {e}", "FAIL")
            return {
                "status": "FAIL",
                "provider": "ollama",
                "error": str(e),
            }
    
    def test_phase2_reference(self, scenario_name: str, input_text: str) -> Dict[str, Any]:
        """Test Phase 2 for comparison."""
        self.log(f"Testing Phase 2 reference ({scenario_name})...", "TEST")
        
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not groq_key:
            self.log("GROQ_API_KEY not set; skipping Phase 2 test", "WARN")
            return {"status": "SKIPPED", "reason": "API key not set"}
        
        try:
            start = time.time()
            result = analyze_v2(
                update_text=input_text,
                provider="groq",
                model="llama-3.3-70b-versatile",
                base_url="https://api.groq.com/openai/v1",
                timeout_s=60,
                max_tokens=512,
                max_attempts=2,
                allow_repair=True,
            )
            elapsed = time.time() - start
            
            self.log(f"✓ Phase 2 reference completed in {elapsed:.2f}s", "PASS")
            return {
                "status": "PASS",
                "result": result,
                "elapsed_s": elapsed,
            }
        except Exception as e:
            self.log(f"✗ Phase 2 reference failed: {e}", "FAIL")
            return {
                "status": "FAIL",
                "error": str(e),
            }
    
    def compare_outputs(self, v2_result: Dict, v3_result: Dict) -> Dict[str, Any]:
        """Compare Phase 2 and Phase 3 outputs."""
        self.log("Comparing Phase 2 vs Phase 3 outputs...", "TEST")
        
        if v2_result.get("status") != "PASS" or v3_result.get("status") != "PASS":
            self.log("Skipping comparison: one or both tests failed", "WARN")
            return {"status": "SKIPPED"}
        
        v2_out = v2_result["result"]
        v3_out = v3_result["result"]
        
        # Check structure
        v2_keys = set(v2_out.keys())
        v3_keys = set(v3_out.keys())
        
        if v2_keys != v3_keys:
            self.log(f"✗ Output keys differ: Phase 2={v2_keys}, Phase 3={v3_keys}", "FAIL")
            return {"status": "FAIL", "reason": "Keys differ"}
        
        # Check content types
        checks = {
            "summary_is_string": isinstance(v3_out.get("summary"), str),
            "tasks_is_list": isinstance(v3_out.get("tasks"), list),
            "risks_is_list": isinstance(v3_out.get("risks"), list),
            "followups_is_list": isinstance(v3_out.get("followups"), list),
        }
        
        all_pass = all(checks.values())
        if all_pass:
            self.log("✓ Output structure matches", "PASS")
        else:
            failed = [k for k, v in checks.items() if not v]
            self.log(f"✗ Output structure mismatch: {failed}", "FAIL")
        
        return {
            "status": "PASS" if all_pass else "FAIL",
            "checks": checks,
            "v2_summary_len": len(v2_out.get("summary", "")),
            "v3_summary_len": len(v3_out.get("summary", "")),
            "v2_tasks_count": len(v2_out.get("tasks", [])),
            "v3_tasks_count": len(v3_out.get("tasks", [])),
        }
    
    def run_all_tests(self):
        """Run full integration test suite."""
        self.log("=" * 70, "INFO")
        self.log("Phase 3 Integration Testing Suite", "INFO")
        self.log("=" * 70, "INFO")
        
        all_results = {}
        
        # Test basic scenario
        scenario = "basic"
        self.log(f"\n--- Scenario: {scenario} ---", "INFO")
        
        v3_groq = self.test_groq_v3(scenario, TEST_SCENARIOS[scenario])
        time.sleep(2)  # Rate limiting
        
        v3_ollama = self.test_ollama_v3(scenario, TEST_SCENARIOS[scenario])
        time.sleep(2)  # Rate limiting
        
        v2_ref = self.test_phase2_reference(scenario, TEST_SCENARIOS[scenario])
        time.sleep(2)  # Rate limiting
        
        comparison = self.compare_outputs(v2_ref, v3_groq)
        
        all_results[scenario] = {
            "phase3_groq": v3_groq,
            "phase3_ollama": v3_ollama,
            "phase2_ref": v2_ref,
            "comparison": comparison,
        }
        
        # Test empty_tasks scenario (conditional routing)
        scenario = "empty_tasks"
        self.log(f"\n--- Scenario: {scenario} (Conditional Routing Test) ---", "INFO")
        
        v3_empty = self.test_groq_v3(scenario, TEST_SCENARIOS[scenario])
        
        # Verify that tasks are empty and risks were skipped
        if v3_empty.get("status") == "PASS":
            if not v3_empty["result"].get("tasks"):
                self.log("✓ Conditional routing: tasks are empty", "PASS")
            if not v3_empty["result"].get("risks"):
                self.log("✓ Conditional routing: risks were skipped", "PASS")
        
        all_results[scenario] = v3_empty
        
        # Test complex scenario
        scenario = "complex"
        self.log(f"\n--- Scenario: {scenario} (Complex Input) ---", "INFO")
        
        v3_complex = self.test_groq_v3(scenario, TEST_SCENARIOS[scenario])
        all_results[scenario] = v3_complex
        
        # Summary
        self.log("\n" + "=" * 70, "INFO")
        self.log("Integration Testing Summary", "INFO")
        self.log("=" * 70, "INFO")
        
        # Count results
        passed = sum(1 for r in all_results.values() 
                    if isinstance(r, dict) and r.get("status") == "PASS")
        failed = sum(1 for r in all_results.values() 
                    if isinstance(r, dict) and r.get("status") == "FAIL")
        skipped = sum(1 for r in all_results.values() 
                     if isinstance(r, dict) and r.get("status") == "SKIPPED")
        
        self.log(f"Passed:  {passed}", "INFO")
        self.log(f"Failed:  {failed}", "INFO")
        self.log(f"Skipped: {skipped}", "INFO")
        
        # Save results to file
        self._save_results(all_results)
        
        return all_results
    
    def _save_results(self, results: Dict):
        """Save test results to file."""
        output_file = "phase3_integration_test_results.json"
        
        # Sanitize results (remove full result objects for readability)
        sanitized = {}
        for scenario, data in results.items():
            if isinstance(data, dict):
                sanitized[scenario] = {
                    k: (
                        {
                            "status": v.get("status"),
                            "provider": v.get("provider"),
                            "elapsed_s": v.get("elapsed_s"),
                            "error": v.get("error"),
                        }
                        if k in ["phase3_groq", "phase3_ollama", "phase2_ref"]
                        else v
                    )
                    for k, v in data.items()
                }
            else:
                sanitized[scenario] = {
                    "status": data.get("status"),
                    "elapsed_s": data.get("elapsed_s"),
                }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=2, ensure_ascii=False)
        
        self.log(f"Results saved to: {output_file}", "INFO")


if __name__ == "__main__":
    tester = IntegrationTester()
    results = tester.run_all_tests()
    
    # Exit with status
    failed_count = sum(1 for r in results.values() 
                      if isinstance(r, dict) and r.get("status") == "FAIL")
    
    sys.exit(1 if failed_count > 0 else 0)
