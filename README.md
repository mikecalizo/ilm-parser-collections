# ilm-parser-collections
Collections of Python scripts for reading ILM policies

1. Make sure that _cat/commercial/ilm_policy.json is in the same folder as the code
2. run 
  > $python ilm-policy-parser-mike.py
3. Results should be:
  - Showing *Index Name*, *ILM Policy name*, *Retention* and *Phase*
  - Notably removed from the results are:  Indices that are in *hot*, *cold*, *warm*, and *frozen* phases, as well as empty (n/a). As a result, indices roll over in these phase are not reported.

<img width="995" alt="Screenshot 2025-04-22 at 8 02 54 AM" src="https://github.com/user-attachments/assets/5b5326c6-2c58-43f0-894b-3dd096a594a5" />

# Added the parser to report ILM Health

To use the code:

> python ilm_policy-explain_parser.py --policies ilm_policies.json --explain ilm_explain.json
 
> python ilm_policy-explain_parser.py --policies ilm_policies.json --explain ilm_explain.json --export-issues

<img width="2058" height="802" alt="image" src="https://github.com/user-attachments/assets/2aea67ce-78fe-4e3b-8724-ef25287388ed" />
<img width="2900" height="1576" alt="image" src="https://github.com/user-attachments/assets/ab4cf35f-8376-4c52-8c8e-ed3a7f1fefe1" />
