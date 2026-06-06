import glob
found = False
for file in glob.glob("**/*.py", recursive=True):
 with open(file, 'r') as f:
 content = f.read()
 if 'retry_on_fail' in content:
 found = True
 print(f"'retry_on_fail' found in {file}")
if not found:
 print("'retry_on_fail' not found in any files")