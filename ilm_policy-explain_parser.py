import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
import argparse

def strip_trailing_date(index_name):
    """Remove date pattern like -2024.09.27-000001 from index names"""
    return re.sub(r'-\d{4}\.\d{2}\.\d{2}-\d{6}$', '', index_name)

def parse_age_to_days(age_str):
    """Convert age string like '18.67d' to float days"""
    if not age_str or age_str == "N/A":
        return 0
    
    if age_str.endswith('d'):
        return float(age_str[:-1])
    elif age_str.endswith('h'):
        return float(age_str[:-1]) / 24
    elif age_str.endswith('m'):
        return float(age_str[:-1]) / (24 * 60)
    return 0

def parse_min_age_to_days(min_age_str):
    """Convert min_age like '7d', '30d', '90d' to days"""
    if not min_age_str or min_age_str == "N/A" or min_age_str == "0ms":
        return 0
    
    if min_age_str.endswith('d'):
        return int(min_age_str[:-1])
    elif min_age_str.endswith('h'):
        return int(min_age_str[:-1]) / 24
    elif min_age_str.endswith('m'):
        return int(min_age_str[:-1]) / (24 * 60)
    return 0

class ILMAnalyzer:
    def __init__(self, ilm_policies_file, ilm_explain_file=None):
        self.policies = self.load_policies(ilm_policies_file)
        self.explain_data = self.load_explain_data(ilm_explain_file) if ilm_explain_file else {}
        self.analysis_results = {}
    
    def load_policies(self, file_path):
        """Load ILM policies from JSON file"""
        # Add .json extension if not present
        if not file_path.endswith('.json'):
            file_path += '.json'
        
        with open(file_path, 'r') as f:
            return json.load(f)
    
    def load_explain_data(self, file_path):
        """Load ILM explain data from JSON file"""
        # Add .json extension if not present
        if not file_path.endswith('.json'):
            file_path += '.json'
            
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data.get('indices', {})
    
    def should_skip_policy(self, policy_name):
        """Check if policy should be skipped based on name patterns"""
        skip_patterns = [
            "metrics",
            "elastic-agent-ilm", 
            "kibana-event-log-policy"
        ]
        
        return any(pattern in policy_name.lower() for pattern in skip_patterns) or \
               ("logs" in policy_name.lower() and "logs-" not in policy_name.lower())
    
    def should_skip_index(self, index_name):
        """Check if index should be skipped based on name patterns"""
        return "partial" in index_name.lower() or "internal" in index_name.lower()
    
    def analyze_policies(self):
        """Analyze ILM policies and return structured data"""
        results = []
        
        for policy_name, policy_info in self.policies.items():
            if self.should_skip_policy(policy_name):
                continue
            
            indices = policy_info.get("in_use_by", {}).get("indices", [])
            phases = policy_info["policy"].get("phases", {})
            
            # Get phase information
            phase_info = {}
            for phase_name, phase_data in phases.items():
                min_age = phase_data.get("min_age", "N/A")
                phase_info[phase_name] = {
                    "min_age": min_age,
                    "min_age_days": parse_min_age_to_days(min_age),
                    "actions": list(phase_data.get("actions", {}).keys())
                }
            
            # Process each index
            filtered_indices = [idx for idx in indices if not self.should_skip_index(idx)]
            
            for index in filtered_indices:
                short_index = strip_trailing_date(index)
                explain_info = self.explain_data.get(index, {})
                
                result = {
                    "index_name": index,
                    "short_index": short_index,
                    "policy_name": policy_name,
                    "phases": phase_info,
                    "current_status": self.get_current_status(explain_info),
                    "health_check": self.perform_health_check(phase_info, explain_info)
                }
                results.append(result)
        
        return results
    
    def get_current_status(self, explain_info):
        """Extract current status from explain data"""
        if not explain_info:
            return {
                "status": "no_explain_data",
                "current_phase": "unknown",
                "age_days": 0,
                "action": "unknown",
                "step": "unknown", 
                "managed": False,
                "repository_name": None,
                "snapshot_name": None,
                "previous_step_info": {}
            }
        
        return {
            "status": "active",
            "current_phase": explain_info.get("phase", "unknown"),
            "age_days": parse_age_to_days(explain_info.get("age", "0d")),
            "action": explain_info.get("action", "unknown"),
            "step": explain_info.get("step", "unknown"),
            "managed": explain_info.get("managed", False),
            "repository_name": explain_info.get("repository_name"),
            "snapshot_name": explain_info.get("snapshot_name"),
            "previous_step_info": explain_info.get("previous_step_info", {})
        }
    
    def perform_health_check(self, phases, explain_info):
        """Perform health checks on index lifecycle"""
        issues = []
        status = "healthy"
        
        if not explain_info:
            return {"status": "no_data", "issues": ["No explain data available"]}
        
        current_phase = explain_info.get("phase", "unknown")
        age_days = parse_age_to_days(explain_info.get("age", "0d"))
        step = explain_info.get("step", "unknown")
        action = explain_info.get("action", "unknown")
        previous_step_info = explain_info.get("previous_step_info", {})
        
        # Check if index is stuck
        if step != "complete" and action != "complete":
            issues.append(f"Index may be stuck in {current_phase} phase, step: {step}")
            status = "warning"
        
        # Check for error messages
        if previous_step_info and "message" in previous_step_info:
            issues.append(f"Previous step issue: {previous_step_info['message']}")
            status = "warning"
        
        # Check phase progression
        if current_phase in phases:
            expected_min_age = phases[current_phase]["min_age_days"]
            if age_days < expected_min_age:
                issues.append(f"Index in {current_phase} phase but only {age_days:.1f} days old (expected {expected_min_age}+ days)")
                status = "warning"
        
        # Check for very old indices still in hot phase
        if current_phase == "hot" and age_days > 30:
            issues.append(f"Index very old ({age_days:.1f} days) but still in hot phase")
            status = "warning"
        
        return {"status": status, "issues": issues}
    
    def generate_summary_report(self):
        """Generate a summary report of ILM status"""
        results = self.analyze_policies()
        
        # Group by policy
        policy_summary = defaultdict(lambda: {
            "total_indices": 0,
            "phases": defaultdict(int),
            "health_status": defaultdict(int),
            "avg_age": 0,
            "total_age": 0
        })
        
        for result in results:
            policy = result["policy_name"]
            current_status = result.get("current_status", {})
            health = result.get("health_check", {"status": "unknown"})
            
            policy_summary[policy]["total_indices"] += 1
            
            # Safely get current phase
            current_phase = current_status.get("current_phase", "unknown")
            policy_summary[policy]["phases"][current_phase] += 1
            
            # Safely get health status
            health_status = health.get("status", "unknown")
            policy_summary[policy]["health_status"][health_status] += 1
            
            # Safely get age
            age_days = current_status.get("age_days", 0)
            policy_summary[policy]["total_age"] += age_days
        
        # Calculate averages
        for policy, summary in policy_summary.items():
            if summary["total_indices"] > 0:
                summary["avg_age"] = summary["total_age"] / summary["total_indices"]
        
        return dict(policy_summary), results
    
    def print_detailed_report(self, output_format="table"):
        """Print detailed analysis report"""
        policy_summary, detailed_results = self.generate_summary_report()
        
        if output_format == "table":
            self._print_table_report(policy_summary, detailed_results)
        elif output_format == "json":
            self._print_json_report(policy_summary, detailed_results)
    
    def _print_table_report(self, policy_summary, detailed_results):
        """Print table format report"""
        print("=" * 120)
        print("ILM POLICY SUMMARY REPORT")
        print("=" * 120)
        
        print(f"{'Policy Name':<40} {'Indices':<8} {'Avg Age':<10} {'Hot':<6} {'Frozen':<8} {'Issues':<8}")
        print("-" * 120)
        
        for policy, summary in policy_summary.items():
            issues = summary["health_status"].get("warning", 0) + summary["health_status"].get("error", 0)
            print(f"{policy:<40} {summary['total_indices']:<8} {summary['avg_age']:<10.1f} "
                  f"{summary['phases']['hot']:<6} {summary['phases']['frozen']:<8} {issues:<8}")
        
        print("\n" + "=" * 120)
        print("DETAILED INDEX STATUS")
        print("=" * 120)
        
        print(f"{'Index Name':<60} {'Policy':<25} {'Phase':<8} {'Age':<8} {'Status':<10} {'Issues'}")
        print("-" * 120)
        
        for result in detailed_results:
            current_status = result.get("current_status", {})
            health_check = result.get("health_check", {"status": "unknown", "issues": []})
            
            current_phase = current_status.get("current_phase", "unknown")
            if health_check["status"] != "healthy" or current_phase in ["hot", "frozen"]:
                issues_str = "; ".join(health_check.get("issues", [])[:2])  # Limit to 2 issues for display
                if len(health_check.get("issues", [])) > 2:
                    issues_str += "..."
                
                print(f"{result.get('short_index', 'unknown'):<60} {result.get('policy_name', 'unknown'):<25} "
                      f"{current_phase:<8} "
                      f"{current_status.get('age_days', 0):<8.1f} "
                      f"{health_check.get('status', 'unknown'):<10} {issues_str}")
    
    def _print_json_report(self, policy_summary, detailed_results):
        """Print JSON format report"""
        report = {
            "summary": policy_summary,
            "detailed_results": detailed_results,
            "generated_at": datetime.now().isoformat()
        }
        print(json.dumps(report, indent=2))
    
    def export_health_issues(self, filename="ilm_health_issues.json"):
        """Export indices with health issues to JSON file"""
        _, detailed_results = self.generate_summary_report()
        
        issues = []
        for result in detailed_results:
            if result["health_check"]["status"] != "healthy":
                issues.append({
                    "index": result["index_name"],
                    "policy": result["policy_name"],
                    "current_phase": result["current_status"]["current_phase"],
                    "age_days": result["current_status"]["age_days"],
                    "issues": result["health_check"]["issues"]
                })
        
        with open(filename, 'w') as f:
            json.dump(issues, f, indent=2)
        
        print(f"Exported {len(issues)} indices with issues to {filename}")

def main():
    parser = argparse.ArgumentParser(description="Enhanced ILM Policy and Status Analyzer")
    parser.add_argument("--policy", "--policies", dest="policies", required=True, help="Path to ilm_policies.json file")
    parser.add_argument("--explain", help="Path to ilm_explain.json file")
    parser.add_argument("--format", choices=["table", "json"], default="table", help="Output format")
    parser.add_argument("--export-issues", action="store_true", help="Export health issues to JSON file")
    
    args = parser.parse_args()
    
    analyzer = ILMAnalyzer(args.policies, args.explain)
    analyzer.print_detailed_report(args.format)
    
    if args.export_issues:
        analyzer.export_health_issues()

if __name__ == "__main__":
    main()
