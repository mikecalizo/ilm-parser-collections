#!/usr/bin/env python3

import json
import re
from datetime import datetime
from collections import defaultdict
import argparse
from pathlib import Path

def days(age_str):
    if not age_str or age_str in ("N/A", "0ms", "null"):
        return 0
    for suffix, mult in {'d': 1, 'h': 1/24, 'm': 1/(24*60), 's': 1/(24*3600)}.items():
        if age_str.endswith(suffix):
            try:
                return float(age_str[:-1]) * mult
            except:
                return 0
    return 0

def load_data(data_dir):
    data_dir = Path(data_dir)
    if not data_dir.exists():
        data_dir = Path("./commercial/") if Path("./commercial/").exists() else Path("./")
    
    def load(f):
        try:
            return json.load(open(data_dir / f))
        except:
            return {}
    
    return {
        'policies': load("ilm_policies.json"),
        'explain': load("ilm_explain.json").get('indices', {}),
        'errors': load("ilm_explain_only_errors.json").get('indices', {})
    }

def lifecycle_config(phases):
    retention = 0
    parts = []
    
    for phase in ['hot', 'warm', 'cold', 'frozen', 'delete']:
        if phase in phases:
            p = phases[phase]
            if phase == 'delete':
                retention = days(p.get('min_age', '0'))
            config = {"min_age": p.get('min_age', '0ms'), "actions": p.get('actions', {})}
            parts.append(f'{phase}={json.dumps(config, separators=(",", ":"))}')
        else:
            parts.append(f'{phase}=null')
    
    return retention, ' '.join(parts)

def show_policies(data):
    policies = data['policies']
    skip = ["metrics", "elastic-agent-ilm", "kibana-event-log-policy"]
    
    print(f"\n ILM POLICIES ({len(policies)})")
    print("=" * 200)
    print(f"{'Policy':<50} {'Retention':<10} {'Indices':<8} {'Modified':<12} {'Lifecycle'}")
    print("-" * 200)
    
    summary = {}
    for name, pol in sorted(policies.items()):
        if any(s in name.lower() for s in skip):
            continue
            
        phases = pol.get('policy', {}).get('phases', {})
        retention, lifecycle = lifecycle_config(phases)
        
        indices = [i for i in pol.get('in_use_by', {}).get('indices', []) 
                  if not any(skip in i.lower() for skip in ["partial-restored", ".internal"])]
        
        modified = pol.get('modified_date', 'N/A')[:10] if pol.get('modified_date') else 'N/A'
        ret_str = f"{retention:.0f}d" if retention > 0 else "∞"
        
        print(f"{name:<50} {ret_str:<10} {len(indices):<8} {modified:<12} {lifecycle}")
        summary[name] = {'retention': retention, 'indices': len(indices), 'lifecycle': lifecycle}
    
    return summary

def show_errors(data):
    errors = data['errors']
    explain = data['explain']
    
    # Find all errors
    all_errors = dict(errors)
    all_errors.update({k: v for k, v in explain.items() 
                      if v.get('step') == 'ERROR' or 'error' in str(v.get('step_info', {})).lower()})
    
    if not all_errors:
        print("\n NO ERRORS FOUND")
        return {}
    
    print(f"\n ILM ERRORS ({len(all_errors)})")
    print("=" * 120)
    print(f"{'Index':<40} {'Policy':<25} {'Phase':<8} {'Age':<6} {'Error'}")
    print("-" * 120)
    
    error_list = {}
    for idx, details in all_errors.items():
        if any(skip in idx.lower() for skip in ["partial-restored", ".internal"]):
            continue
            
        error_info = details.get('step_info', {}) or details.get('previous_step_info', {})
        reason = error_info.get('reason', 'Unknown error')[:60]
        
        error_list[idx] = {
            'index': re.sub(r'-\d{4}\.\d{2}\.\d{2}-\d{6}$', '', idx),
            'policy': details.get('policy', 'unknown'),
            'phase': details.get('phase', 'unknown'),
            'age': days(details.get('age', '0d')),
            'error': reason
        }
    
    for err in sorted(error_list.values(), key=lambda x: x['age'], reverse=True)[:20]:
        print(f"{err['index']:<40} {err['policy']:<25} {err['phase']:<8} {err['age']:<6.1f} {err['error']}")
    
    return error_list

def show_recommendations(data):
    policies = data['policies']
    explain = data['explain']
    
    print(f"\n RECOMMENDATIONS")
    print("=" * 80)
    
    recs = []
    
    for name, pol in policies.items():
        if any(s in name.lower() for s in ["metrics", "elastic-agent-ilm", "kibana-event-log-policy"]):
            continue
            
        phases = pol.get('policy', {}).get('phases', {})
        indices = pol.get('in_use_by', {}).get('indices', [])
        
        # Missing warm phase
        if 'hot' in phases and 'cold' in phases and 'warm' not in phases:
            recs.append(f"'{name}': Add warm phase between hot and cold")
        
        # Long hot phase
        if 'warm' in phases and days(phases['warm'].get('min_age', '0')) > 30:
            recs.append(f"'{name}': Hot phase too long ({days(phases['warm'].get('min_age', '0')):.0f}d)")
        
        # Missing frozen for long retention
        if 'delete' in phases:
            del_age = days(phases['delete'].get('min_age', '0'))
            if del_age > 365 and 'frozen' not in phases:
                recs.append(f"'{name}': Use frozen phase for {del_age:.0f}d retention")
        
        # Stuck indices
        stuck = 0
        for idx in indices:
            if any(skip in idx.lower() for skip in ["partial-restored", ".internal"]):
                continue
            info = explain.get(idx, {})
            if info.get('phase') == 'hot' and days(info.get('age', '0d')) > 30:
                stuck += 1
        
        if stuck > 0:
            recs.append(f"'{name}': {stuck} indices stuck in hot phase > 30d")
    
    for i, rec in enumerate(recs, 1):
        print(f"{i:2d}. {rec}")
    
    return recs

def health_score(summary, errors):
    total = sum(p['indices'] for p in summary.values())
    error_count = len(errors)
    
    if total == 0:
        score = 0
    else:
        score = max(0, 100 - (error_count / total * 100))
    
    if score >= 95:
        rating = " EXCELLENT"
    elif score >= 85:
        rating = " GOOD"
    elif score >= 70:
        rating = " FAIR"
    else:
        rating = " POOR"
    
    print(f"\n HEALTH: {score:.1f}% {rating}")
    print(f"Total: {total} indices, Errors: {error_count}")
    
    return score

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="./")
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument("--errors-only", action="store_true")
    parser.add_argument("--recommendations-only", action="store_true")
    parser.add_argument("--export")
    
    args = parser.parse_args()
    
    data = load_data(args.dir)
    
    print(f" ILM ANALYSIS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.summary_only:
        summary = show_policies(data)
        errors = show_errors(data)
        health_score(summary, errors)
    elif args.errors_only:
        summary = show_policies(data)
        errors = show_errors(data)
        health_score(summary, errors)
    elif args.recommendations_only:
        show_recommendations(data)
    else:
        summary = show_policies(data)
        errors = show_errors(data)
        recs = show_recommendations(data)
        health_score(summary, errors)
    
    if args.export:
        filename = args.export if args.export != "auto" else f"ilm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump({'summary': summary, 'errors': errors, 'recommendations': recs}, f, indent=2)
        print(f"\n Exported: {filename}")

if __name__ == "__main__":
    main()
