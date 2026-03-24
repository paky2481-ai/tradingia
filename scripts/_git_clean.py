import subprocess, sys, os
os.chdir(r'C:\dev\tradingia')

result = subprocess.run(
    ['git', 'rm', '-r', '--cached', '--ignore-unmatch',
     'backtesting/__pycache__', 'config/__pycache__', 'core/__pycache__',
     'data/__pycache__', 'gui/__pycache__', 'gui/panels/__pycache__',
     'gui/styles/__pycache__', 'gui/widgets/__pycache__',
     'indicators/__pycache__', 'models/__pycache__', 'strategies/__pycache__',
     'utils/__pycache__', 'logs/tradingia.log'],
    capture_output=True, text=True
)
print(result.stdout[-500:] if result.stdout else "(nessun output)")
print(result.stderr[-200:] if result.stderr else "")
print("Exit:", result.returncode)
