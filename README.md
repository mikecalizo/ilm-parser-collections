# ilm-parser-collections
Collections of Python scripts for reading ILM policies


## ILM policy parser report

To use the code:

> $python ilm-policy-parser.py --dir  ~/(diagnostic-dir)/commercial/

<img width="1908" height="691" alt="image" src="https://github.com/user-attachments/assets/c359899b-b75c-4cb7-b218-3a6a34a500cc" />
<img width="1106" height="399" alt="image" src="https://github.com/user-attachments/assets/eea7acb0-6160-4501-9e71-dabfaf9809aa" />



## Version 1

1. Make sure that _cat/commercial/ilm_policy.json is in the same folder as the code
2. run 
  > $python ilm-policy-parser-mike.py
3. Results should be:
  - Showing *Index Name*, *ILM Policy name*, *Retention* and *Phase*
  - Notably removed from the results are:  Indices that are in *hot*, *cold*, *warm*, and *frozen* phases, as well as empty (n/a). As a result, indices roll over in these phase are not reported.

<img width="995" alt="Screenshot 2025-04-22 at 8 02 54 AM" src="https://github.com/user-attachments/assets/5b5326c6-2c58-43f0-894b-3dd096a594a5" />
