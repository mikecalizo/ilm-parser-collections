# ilm-parser-collections
Collections of Python scripts for reading ILM policies

1. Make sure that _cat/commercial/ilm_policy.json is in the same folder as the code
2. run 
  > $python ilm-policy-parser-mike.py
3. Results should be:
  - Showing *Index Name*, *ILM Policy name*, *Retention* and *Phase*
  - Notably removed from the results are:  Indices that are in *hot*, *cold*, *warm*, and *frozen* phases, as well as empty (n/a). As a result, indices roll over in these phase are not reported.

<img width="995" alt="Screenshot 2025-04-22 at 8 02 54 AM" src="https://github.com/user-attachments/assets/5b5326c6-2c58-43f0-894b-3dd096a594a5" />

