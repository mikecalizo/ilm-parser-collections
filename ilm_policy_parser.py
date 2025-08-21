#!/usr/bin/env python3
"""
ILM policy analysis, error reporting, and optimization recommendations
"""

import json
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import argparse
import sys
from pathlib import Path

def parse_age_to_days(age_str):
    """Convert age string to float days"""
    if not age_str or age_str in ("N/A", "0ms", "null"):
        return 0
    
    multipliers = {'d': 1, 'h': 1/24, 'm': 1/(24*60), 's': 1/(24*3600)}
    for suffix, mult in multipliers.items():
        if age_str.endswith(suffix):
            try:
                return float(age_str[:-1]) * mult
            except ValueError:
                return 0
    return 0

class EnhancedILMMonitor:
    def __init__(self, data_dir="./"):
        """Initialize with data directory"""
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            self.data_dir = Path("./commercial/")
        if not self.data_dir.exists():
            self.data_dir = Path("./")
            
        # Load all data files
        self.status = self._load_json("ilm_status.json", {})
        self.policies = self._load_json("ilm_policies.json", {})
        self.explain_data = self._load_json("ilm_explain.json", {}).get('indices', {})
        self.error_data = self._load_json("ilm_explain_only_errors.json", {}).get('indices', {})
        
        # Skip patterns for system indices
        self.skip_policies = ["metrics", "elastic-agent-ilm", "kibana-event-log-policy"]
        self.skip_indices = ["partial-restored", ".internal"]
    
    def _load_json(self, filename, default=None):
        """Load JSON file from data directory"""
        file_path = self.data_dir / filename
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            if default is None:
                print(f"⚠️  Could not load {filename}: {e}", file=sys.stderr)
            return default if default is not None else {}
    
    def _should_skip(self, name, skip_patterns):
        """Check if name should be skipped"""
        name_lower = name.lower()
        return any(pattern in name_lower for pattern in skip_patterns)
    
    def _extract_retention_info(self, phases):
        """Extract retention information and lifecycle details from phases"""
        retention_days = 0
        lifecycle_parts = []
        
        phase_order = ['hot', 'warm', 'cold', 'frozen', 'delete']
        for phase in phase_order:
            if phase in phases:
                phase_data = phases[phase]
                min_age = parse_age_to_days(phase_data.get('min_age', '0'))
                
                if phase == 'delete':
                    retention_days = min_age
                
                # Format phase configuration
                phase_config = {
                    "min_age": phase_data.get('min_age', '0ms'),
                    "actions": phase_data.get('actions', {})
                }
                lifecycle_parts.append(f'{phase}={json.dumps(phase_config, separators=(",", ":"))}')
            else:
                lifecycle_parts.append(f'{phase}=null')
        
        lifecycle_str = ' '.join(lifecycle_parts)
        return retention_days, lifecycle_str
    
    def summarize_ilm_policies(self):
        """1. Summarize existing ILM policies in a concise manner"""
        if not self.policies:
            return {}
        
        print(f"\n ILM POLICY SUMMARY ({len(self.policies)} policies)")
        print("=" * 200)
        print(f"{'Policy Name':<50} {'Retention':<10} {'Indices':<8} {'Modified':<12} {'Lifecycle Configuration'}")
        print("-" * 200)
        
        policy_summary = {}
        
        for policy_name, policy_data in sorted(self.policies.items()):
            if self._should_skip(policy_name, self.skip_policies):
                continue
                
            phases = policy_data.get('policy', {}).get('phases', {})
            retention_days, lifecycle_str = self._extract_retention_info(phases)
            
            indices = policy_data.get('in_use_by', {}).get('indices', [])
            filtered_indices = [idx for idx in indices if not self._should_skip(idx, self.skip_indices)]
            
            modified = policy_data.get('modified_date', 'N/A')[:10] if policy_data.get('modified_date') else 'N/A'
            
            retention_str = f"{retention_days:.0f}d" if retention_days > 0 else "∞"
            
            print(f"{policy_name:<50} {retention_str:<10} {len(filtered_indices):<8} {modified:<12} {lifecycle_str}")
            
            policy_summary[policy_name] = {
                'retention_days': retention_days,
                'lifecycle_config': lifecycle_str,
                'total_indices': len(filtered_indices),
                'phases': list(phases.keys()),
                'modified_date': modified
            }
        
        return policy_summary
    
    def report_ilm_errors(self):
        """2. Report ILM policy errors"""
        all_errors = {}
        
        # Combine error data sources
        error_sources = [
            ("explain_errors", self.error_data),
            ("explain_all", {k: v for k, v in self.explain_data.items() 
                           if v.get('step') == 'ERROR' or 'error' in str(v.get('step_info', {})).lower()})
        ]
        
        print(f"\n ILM ERROR ANALYSIS")
        print("=" * 120)
        
        for source_name, error_indices in error_sources:
            if not error_indices:
                continue
                
            print(f"\n {source_name.upper()} ({len(error_indices)} indices)")
            print("-" * 120)
            
            # Group errors by type
            error_patterns = defaultdict(list)
            
            for index, details in error_indices.items():
                if self._should_skip(index, self.skip_indices):
                    continue
                    
                error_info = details.get('step_info', {}) or details.get('previous_step_info', {})
                error_type = error_info.get('type', 'unknown_error')
                error_reason = error_info.get('reason', 'No reason provided')
                
                # Categorize common errors
                if 'security_exception' in error_type:
                    category = " Permission Error"
                elif 'snapshot' in error_reason.lower():
                    category = " Snapshot Error"
                elif 'shard' in error_reason.lower():
                    category = "🔧 Shard Error"
                elif 'disk' in error_reason.lower() or 'space' in error_reason.lower():
                    category = " Storage Error"
                else:
                    category = " Other Error"
                
                age_days = parse_age_to_days(details.get('age', '0d'))
                retry_count = details.get('failed_step_retry_count', 0)
                
                error_patterns[category].append({
                    'index': re.sub(r'-\d{4}\.\d{2}\.\d{2}-\d{6}$', '', index),
                    'policy': details.get('policy', 'unknown'),
                    'phase': details.get('phase', 'unknown'),
                    'age_days': age_days,
                    'error_type': error_type,
                    'error_reason': error_reason[:80] + "..." if len(error_reason) > 80 else error_reason,
                    'retry_count': retry_count,
                    'step': details.get('step', 'unknown')
                })
                
                all_errors[index] = error_patterns[category][-1]
            
            # Display errors by category
            for category, errors in error_patterns.items():
                print(f"\n{category} ({len(errors)} indices)")
                print(f"{'Index':<40} {'Policy':<25} {'Phase':<8} {'Age':<6} {'Retries':<8} {'Error'}")
                print("-" * 120)
                
                for error in sorted(errors, key=lambda x: x['retry_count'], reverse=True)[:10]:  # Top 10
                    print(f"{error['index']:<40} {error['policy']:<25} {error['phase']:<8} "
                          f"{error['age_days']:<6.1f} {error['retry_count']:<8} {error['error_reason']}")
        
        return all_errors
    
    def analyze_ilm_improvements(self):
        """3. Report ILM policy improvements"""
        print(f"\n ILM OPTIMIZATION RECOMMENDATIONS")
        print("=" * 120)
        
        recommendations = defaultdict(list)
        
        # Analyze each policy for improvements
        for policy_name, policy_data in self.policies.items():
            if self._should_skip(policy_name, self.skip_policies):
                continue
                
            phases = policy_data.get('policy', {}).get('phases', {})
            indices = policy_data.get('in_use_by', {}).get('indices', [])
            filtered_indices = [idx for idx in indices if not self._should_skip(idx, self.skip_indices)]
            
            if not filtered_indices:
                continue
                
            # Check for common optimization opportunities
            self._check_policy_optimizations(policy_name, phases, filtered_indices, recommendations)
            self._check_index_health_patterns(policy_name, filtered_indices, recommendations)
        
        # Display recommendations by category
        categories = {
            'performance': ' Performance Optimizations',
            'cost': ' Cost Optimizations', 
            'reliability': '  Reliability Improvements',
            'maintenance': ' Maintenance Recommendations'
        }
        
        for category, title in categories.items():
            if recommendations[category]:
                print(f"\n{title}")
                print("-" * 80)
                for i, rec in enumerate(recommendations[category], 1):
                    print(f"{i:2d}. {rec}")
        
        return dict(recommendations)
    
    def _check_policy_optimizations(self, policy_name, phases, indices, recommendations):
        """Check for policy-level optimizations"""
        # Check for missing warm phase
        if 'hot' in phases and 'cold' in phases and 'warm' not in phases:
            recommendations['performance'].append(
                f"Policy '{policy_name}': Consider adding warm phase between hot and cold for better performance transition"
            )
        
        # Check for very long hot phase retention
        if 'hot' in phases and 'warm' in phases:
            warm_min_age = parse_age_to_days(phases['warm'].get('min_age', '0'))
            if warm_min_age > 30:
                recommendations['cost'].append(
                    f"Policy '{policy_name}': Hot phase duration ({warm_min_age:.0f}d) is very long - consider shorter hot retention for cost savings"
                )
        
        # Check for missing frozen phase for long retention
        if 'delete' in phases:
            delete_min_age = parse_age_to_days(phases['delete'].get('min_age', '0'))
            if delete_min_age > 365 and 'frozen' not in phases:
                recommendations['cost'].append(
                    f"Policy '{policy_name}': Long retention ({delete_min_age:.0f}d) without frozen phase - consider frozen storage for cost optimization"
                )
        
        # Check for rollover configuration
        if 'hot' in phases:
            hot_actions = phases['hot'].get('actions', {})
            if 'rollover' in hot_actions:
                rollover_config = hot_actions['rollover']
                max_size = rollover_config.get('max_primary_shard_size', '').replace('gb', '').replace('GB', '')
                if max_size and float(max_size) > 50:
                    recommendations['performance'].append(
                        f"Policy '{policy_name}': Large shard size ({max_size}GB) may impact performance - consider smaller shards"
                    )
    
    def _check_index_health_patterns(self, policy_name, indices, recommendations):
        """Check for index health patterns"""
        hot_old_indices = []
        stuck_indices = []
        
        for index in indices:
            explain_info = self.explain_data.get(index, {})
            if not explain_info:
                continue
                
            phase = explain_info.get('phase', 'unknown')
            age_days = parse_age_to_days(explain_info.get('age', '0d'))
            step = explain_info.get('step', 'unknown')
            
            # Check for old hot indices
            if phase == 'hot' and age_days > 30:
                hot_old_indices.append(f"{index}({age_days:.0f}d)")
            
            # Check for stuck indices
            if step in ['ERROR', 'wait-for-action'] or 'wait' in step.lower():
                stuck_indices.append(f"{index}:{step}")
        
        if hot_old_indices:
            recommendations['maintenance'].append(
                f"Policy '{policy_name}': {len(hot_old_indices)} indices stuck in hot phase > 30d - investigate rollover conditions"
            )
        
        if stuck_indices:
            recommendations['reliability'].append(
                f"Policy '{policy_name}': {len(stuck_indices)} indices appear stuck - review phase transitions"
            )
    
    def _calculate_health_score(self, policy_summary, errors):
        """Calculate overall ILM health score"""
        print(f"\n OVERALL ILM HEALTH SCORE")
        print("=" * 80)
        
        total_indices = sum(p['total_indices'] for p in policy_summary.values())
        error_indices = len(errors)
        
        if total_indices == 0:
            health_score = 0
        else:
            health_score = max(0, 100 - (error_indices / total_indices * 100))
        
        # Health rating
        if health_score >= 95:
            rating = "🟢 EXCELLENT"
        elif health_score >= 85:
            rating = "🟡 GOOD"
        elif health_score >= 70:
            rating = "🟠 FAIR"
        else:
            rating = "🔴 POOR"
        
        print(f"Health Score: {health_score:.1f}% {rating}")
        print(f"Total Indices: {total_indices}")
        print(f"Error Indices: {error_indices}")
        print(f"Success Rate: {((total_indices - error_indices) / total_indices * 100):.1f}%" if total_indices > 0 else "N/A")
        
        return health_score, rating
    
    def generate_comprehensive_report(self):
        """Generate comprehensive ILM report"""
        print(f" COMPREHENSIVE ILM ANALYSIS REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 120)
        
        # 1. Policy Summary
        policy_summary = self.summarize_ilm_policies()
        
        # 2. Error Analysis  
        errors = self.report_ilm_errors()
        
        # 3. Optimization Recommendations
        recommendations = self.analyze_ilm_improvements()
        
        # 4. Overall Health Score
        health_score, rating = self._calculate_health_score(policy_summary, errors)
        
        return {
            'policy_summary': policy_summary,
            'errors': errors,
            'recommendations': recommendations,
            'health_score': health_score,
            'health_rating': rating,
            'timestamp': datetime.now().isoformat()
        }
    
    def export_detailed_report(self, filename=None):
        """Export detailed analysis to JSON"""
        if filename is None:
            filename = f"ilm_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = self.generate_comprehensive_report()
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n Detailed report exported to: {filename}")
        return filename

def main():
    parser = argparse.ArgumentParser(description="Enhanced ILM Health Monitor and Optimizer")
    parser.add_argument("--dir", default="./", help="Data directory (default: ./)")
    parser.add_argument("--summary-only", action="store_true", help="Show only policy summary")
    parser.add_argument("--errors-only", action="store_true", help="Show only error analysis")
    parser.add_argument("--recommendations-only", action="store_true", help="Show only optimization recommendations")
    parser.add_argument("--export", help="Export detailed report to JSON file")
    parser.add_argument("--format", choices=["table", "json"], default="table", help="Output format")
    
    args = parser.parse_args()
    
    monitor = EnhancedILMMonitor(args.dir)
    
    if args.format == "json":
        report = monitor.generate_comprehensive_report()
        print(json.dumps(report, indent=2))
        return
    
    # For selective reporting, we'll still calculate and show health score
    policy_summary = {}
    errors = {}
    
    # Selective reporting
    if args.summary_only:
        policy_summary = monitor.summarize_ilm_policies()
    elif args.errors_only:
        errors = monitor.report_ilm_errors()
    elif args.recommendations_only:
        monitor.analyze_ilm_improvements()
    else:
        # Full comprehensive report
        monitor.generate_comprehensive_report()
        return
    
    # Always show health score for selective reports
    if args.summary_only or args.errors_only:
        # Get the missing data for health calculation
        if not policy_summary:
            policy_summary = monitor.summarize_ilm_policies()
        if not errors:
            errors = monitor.report_ilm_errors()
        monitor._calculate_health_score(policy_summary, errors)
    
    # Export if requested
    if args.export:
        if args.export == "auto":
            monitor.export_detailed_report()
        else:
            monitor.export_detailed_report(args.export)

if __name__ == "__main__":
    main()
