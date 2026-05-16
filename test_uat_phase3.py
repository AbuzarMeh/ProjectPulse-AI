#!/usr/bin/env python3
"""
Phase 3 User Acceptance Testing (UAT) Suite
Real-world scenario testing for project manager users
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Any

# Ensure src is on path
repo_root = os.path.dirname(__file__)
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, 'src'))

from pm_copilot.orchestration.langgraph_flow import orchestrate


# Real-world project scenarios for UAT
UAT_SCENARIOS = {
    "startup_pivot": {
        "title": "Startup Pivot Decision",
        "description": "Team discussing product pivot mid-development",
        "input": """
URGENT: Strategy Meeting Notes - Product Pivot Discussion

Attendees: CEO, Product Lead, Tech Lead, Designer

DECISION MADE:
- Pivoting from B2B to B2C market segment
- Reorienting product roadmap

IMPACT ASSESSMENT:
- Need to rewrite 40% of current features
- Timeline: compress 6-month roadmap to 3 months
- Budget: additional $200k needed
- Team: hiring 2 contractors

IMMEDIATE ACTIONS:
- Legal review of existing contracts (by Friday)
- Client notification plan (by Monday)
- Contractor procurement (ASAP)
- Redesign kickoff (next Wednesday)

BLOCKERS:
- Clarity on new market positioning (CEO to clarify by tomorrow)
- Design resources currently at capacity
- Uncertain contractor availability

RISKS:
- Early customers may churn
- Team morale impact (layoff concerns)
- Aggressive timeline may lead to quality issues
- Budget may not be sufficient given market unknowns
        """,
        "expectations": {
            "summary_contains": ["pivot", "b2c"],
            "tasks_count_min": 3,
            "tasks_contains_any": [
                ["legal", "contract"],
                ["client", "customer", "notification"],
                ["contractor", "hire", "procurement"],
                ["redesign", "design", "kickoff"],
            ],
            "risks_count_min": 2,
            "risks_contains_any": [
                ["churn", "attrition"],
                ["morale"],
                ["timeline", "schedule"],
                ["budget", "cost"],
            ],
            "keyword_pass_ratio": 0.5,
        }
    },
    
    "release_postmortem": {
        "title": "Production Incident & Post-Mortem",
        "description": "Team reviewing production incident and recovery",
        "input": """
Post-Incident Review: Production Database Outage
Date: May 14, 2026 | Duration: 2 hours 15 minutes

WHAT HAPPENED:
- Database replica fell out of sync with primary
- Automated failover triggered (but didn't succeed)
- Manual intervention required to restore service
- 127 users affected during outage
- Data consistency verified (no data loss)

ROOT CAUSE:
- Recent schema migration had a typo in the replication trigger
- Monitoring alert for replication lag was set to 1 hour (too high)
- No automated rollback procedure in place

IMMEDIATE FIXES (Done):
- Corrected schema migration on all replicas
- Restarted replication process
- Verified data consistency
- Notified affected users

FOLLOW-UP ACTIONS (Next 2 weeks):
- Reduce replication lag alert threshold to 5 minutes
- Implement automated rollback for failed migrations
- Add replication status to on-call dashboard
- Post-mortem documentation and team review
- Customer communication and compensation plan
- Database backup verification and testing
- Load testing on new replication setup

LESSONS LEARNED:
1. Schema migrations need better testing before production
2. Monitoring thresholds were not aggressive enough
3. Runbook for replication failures was incomplete
4. Team training needed on failover procedures

PREVENTION:
- Implement pre-production database testing
- Set up staging environment mirroring production
- Document and practice incident response drills
        """,
        "expectations": {
            "summary_contains": ["outage", "database", "replication"],
            "tasks_count_min": 4,
            "tasks_contains_any": [
                ["alert", "threshold", "monitor"],
                ["rollback"],
                ["dashboard", "on-call", "runbook"],
                ["backup"],
                ["testing", "staging", "load test"],
            ],
            "risks_count_min": 1,
            "risks_contains_any": [
                ["migration"],
                ["recurr", "again"],
            ],
            "keyword_pass_ratio": 0.5,
        }
    },
    
    "sprint_planning": {
        "title": "Sprint Planning & Commitment",
        "description": "Team planning next sprint with dependencies",
        "input": """
Sprint 47 Planning - May 19 to May 30, 2026

TEAM CAPACITY:
- 3 backend engineers: ~45 story points
- 2 frontend engineers: ~30 story points
- 1 QA engineer: testing for entire sprint
- 1 DevOps: infrastructure (part-time)

COMMITTED ITEMS:
1. API Rate Limiting (8 pts) - MUST HAVE
   - Block clients exceeding 100 req/sec
   - Return 429 with retry-after header
   - Stakeholder: Sales (customer complaints about abuse)
   Assigned: Backend Team Lead

2. Dashboard Performance (5 pts) - HIGH PRIORITY
   - Optimize slow queries (customer timeouts at 500 users)
   - Add database indexing
   - Cache frequently accessed metrics
   Assigned: Backend Engineer + Frontend Engineer

3. Dark Mode UI (8 pts) - NICE TO HAVE
   - Implement dark theme toggle
   - Update all components
   - Mobile responsive testing
   Assigned: Frontend Team

4. Bug Fixes (5 pts) - COMMITTED
   - Fix export PDF issue (customer critical)
   - Fix notification timing bug
   - Fix mobile sidebar collapse

DEPENDENCIES:
- Dashboard Performance depends on new query optimization (Backend)
- Dark Mode needs design review before frontend starts
- Bug fixes can start immediately

RISKS:
- Rate limiting changes may impact legacy API clients
- No dedicated QA for new features (shared capacity)
- Team sick leave possibility (2 people out last week)

BLOCKERS:
- Design review for dark mode (designer unavailable until Wednesday)
- Production database access for rate limiting testing
        """,
        "expectations": {
            "summary_contains": ["sprint", "47"],
            "tasks_count_min": 4,
            "tasks_contains_any": [
                ["rate", "429", "limiting"],
                ["dashboard", "performance", "optimiz", "index"],
                ["bug", "fix"],
                ["dark", "theme", "mode"],
            ],
            "risks_count_min": 2,
            "risks_contains_any": [
                ["legacy", "client"],
                ["qa", "capacity"],
                ["sick", "leave", "absence"],
            ],
            "keyword_pass_ratio": 0.5,
        }
    },
}


class UATExecutor:
    """User Acceptance Testing executor."""
    
    def __init__(self):
        self.results = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{timestamp}] [{level}]"
        print(f"{prefix} {message}")
    
    def validate_output_schema(self, output: Dict[str, Any]) -> Dict[str, bool]:
        """Validate that output conforms to schema."""
        checks = {
            "has_summary": "summary" in output and isinstance(output["summary"], str),
            "has_tasks": "tasks" in output and isinstance(output["tasks"], list),
            "has_risks": "risks" in output and isinstance(output["risks"], list),
            "has_followups": "followups" in output and isinstance(output["followups"], list),
            "summary_not_empty": bool(output.get("summary", "").strip()),
            "tasks_items_valid": all(
                isinstance(t, dict) and "title" in t and "description" in t
                for t in output.get("tasks", [])
            ),
            "risks_items_valid": all(
                isinstance(r, dict) and "description" in r
                for r in output.get("risks", [])
            ),
            "followups_items_valid": all(
                isinstance(f, dict) and "message" in f
                for f in output.get("followups", [])
            ),
        }
        return checks
    
    def validate_expectations(self, output: Dict[str, Any], 
                            expectations: Dict[str, Any]) -> Dict[str, bool]:
        """Validate scenario-specific expectations.

        LLM phrasing varies, so keyword checks are intentionally *soft*.
        The hard requirements are: minimum task/risk counts.
        """
        checks: Dict[str, bool] = {}

        summary_lower = output.get("summary", "").lower()

        # Summary keyword checks (soft)
        for keyword in expectations.get("summary_contains", []):
            check_key = f"summary_has_{keyword}"
            checks[check_key] = keyword.lower() in summary_lower

        # Task count (hard)
        tasks = output.get("tasks", [])
        tasks_count = len(tasks)
        checks["tasks_count_sufficient"] = tasks_count >= expectations.get("tasks_count_min", 0)

        # Task keywords (soft, allow synonym groups)
        tasks_text = " ".join(
            [f"{t.get('title', '')} {t.get('description', '')}" for t in tasks]
        ).lower()
        for group in expectations.get("tasks_contains_any", []):
            label = "|".join(group)
            checks[f"tasks_has_any_{label}"] = any(k.lower() in tasks_text for k in group)

        # Risk count (hard)
        risks = output.get("risks", [])
        risks_count = len(risks)
        checks["risks_count_sufficient"] = risks_count >= expectations.get("risks_count_min", 0)

        # Risk keywords (soft)
        risks_text = " ".join([r.get("description", "") for r in risks]).lower()
        for group in expectations.get("risks_contains_any", []):
            label = "|".join(group)
            checks[f"risks_has_any_{label}"] = any(k.lower() in risks_text for k in group)

        # Aggregate pass signal for keywords
        keyword_checks = [
            v for k, v in checks.items() if k.startswith("summary_has_") or k.startswith("tasks_has_any_") or k.startswith("risks_has_any_")
        ]
        ratio = sum(1 for v in keyword_checks if v) / max(1, len(keyword_checks))
        checks["keyword_ratio_sufficient"] = ratio >= expectations.get("keyword_pass_ratio", 0.5)

        return checks
    
    def run_uat(self) -> Dict[str, Any]:
        """Run UAT for all scenarios."""
        self.log("=" * 70, "INFO")
        self.log("Phase 3 User Acceptance Testing Suite", "INFO")
        self.log("=" * 70, "INFO")
        
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not groq_key:
            self.log("GROQ_API_KEY not set; cannot run UAT", "WARN")
            self.log("Set GROQ_API_KEY to run real-world scenario tests", "WARN")
            return {"status": "SKIPPED"}
        
        all_results = {}
        
        for scenario_id, scenario in UAT_SCENARIOS.items():
            self.log(f"\n--- UAT: {scenario['title']} ---", "INFO")
            self.log(f"Description: {scenario['description']}", "INFO")
            
            try:
                # Execute orchestration
                self.log("Running Phase 3 orchestration...", "INFO")
                output = orchestrate(
                    input_text=scenario["input"],
                    provider="groq",
                    model="llama-3.3-70b-versatile",
                    base_url="https://api.groq.com/openai/v1",
                    timeout_s=60,
                    max_tokens=512,
                    max_attempts=2,
                    allow_repair=True,
                )
                
                # Validate schema
                schema_checks = self.validate_output_schema(output)
                schema_pass = all(schema_checks.values())
                
                # Validate expectations
                expectation_checks = self.validate_expectations(output, scenario["expectations"])
                # Expectation pass: counts must pass, plus a reasonable keyword ratio
                counts_ok = expectation_checks.get("tasks_count_sufficient", False) and expectation_checks.get(
                    "risks_count_sufficient", False
                )
                keywords_ok = expectation_checks.get("keyword_ratio_sufficient", True)
                expectation_pass = counts_ok and keywords_ok
                
                # Overall result
                scenario_pass = schema_pass and expectation_pass
                status = "PASS" if scenario_pass else "FAIL"
                
                self.log(f"Schema validation: {sum(schema_checks.values())}/{len(schema_checks)}", "INFO")
                self.log(f"Expectation validation: {sum(expectation_checks.values())}/{len(expectation_checks)}", "INFO")
                self.log(f"Result: {status}", status)
                
                # Store results
                all_results[scenario_id] = {
                    "status": status,
                    "title": scenario["title"],
                    "schema_checks": schema_checks,
                    "expectation_checks": expectation_checks,
                    "output": {
                        "summary_length": len(output.get("summary", "")),
                        "tasks_count": len(output.get("tasks", [])),
                        "risks_count": len(output.get("risks", [])),
                        "followups_count": len(output.get("followups", [])),
                    }
                }
                
            except Exception as e:
                self.log(f"Exception: {e}", "FAIL")
                all_results[scenario_id] = {
                    "status": "FAIL",
                    "title": scenario["title"],
                    "error": str(e),
                }
        
        # Summary
        self.log("\n" + "=" * 70, "INFO")
        self.log("UAT Summary", "INFO")
        self.log("=" * 70, "INFO")
        
        passed = sum(1 for r in all_results.values() if r.get("status") == "PASS")
        failed = sum(1 for r in all_results.values() if r.get("status") == "FAIL")
        
        self.log(f"Scenarios Passed: {passed}", "INFO")
        self.log(f"Scenarios Failed: {failed}", "INFO")
        
        if failed == 0 and passed > 0:
            self.log("✓ UAT PASSED - Phase 3 ready for user acceptance", "PASS")
        else:
            self.log("✗ UAT FAILED - Issues found, review output", "FAIL")
        
        # Save results
        self._save_results(all_results)
        
        return all_results
    
    def _save_results(self, results: Dict):
        """Save UAT results to file."""
        output_file = "phase3_uat_results.json"
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        self.log(f"UAT results saved to: {output_file}", "INFO")


if __name__ == "__main__":
    executor = UATExecutor()
    results = executor.run_uat()
    
    # Exit with status
    failed = sum(1 for r in results.values() if isinstance(r, dict) and r.get("status") == "FAIL")
    sys.exit(1 if failed > 0 else 0)
