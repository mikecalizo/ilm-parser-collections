# ilm-parser-collections
Collections of Python scripts for reading ILM policies


## ILM policy parser report

To use the code:

> $python ilm-policy-parser.py --dir  ~/(diagnostic-dir)/commercial/



Results will show:
1. ILM Policy Name
2. Retention in days
3. Indices covered by the ILM Policy
4. Date modified
5. Lifecycle
<img width="1908" height="691" alt="image" src="https://github.com/user-attachments/assets/c359899b-b75c-4cb7-b218-3a6a34a500cc" />

It will also include:
1. Errors if found
2. Recommendations

<img width="1106" height="399" alt="image" src="https://github.com/user-attachments/assets/eea7acb0-6160-4501-9e71-dabfaf9809aa" />

# Command Options

## Full comprehensive analysis with categories
python ilm-policy-parser.py

## Just policy breakdown with context
python ilm-policy-parser.py --policies-only

## Export detailed report
python ilm-policy-parser.py --export auto


