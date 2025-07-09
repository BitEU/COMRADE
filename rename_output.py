import re
import sys

# Read version from src/constants.py
with open('src/constants.py', 'r') as f:
    content = f.read()
match = re.search(r'COMRADE_VERSION\s*=\s*"([^"]+)"', content)
if not match:
    print('Could not find COMRADE_VERSION in src/constants.py')
    sys.exit(1)
version = match.group(1)

# Rename main.exe to COMRADE vX.X.X.exe
import os
src = os.path.join('dist', 'main.exe')
dst = os.path.join('dist', f'COMRADE v{version}.exe')
if os.path.exists(src):
    os.replace(src, dst)
    print(f'Renamed {src} to {dst}')
else:
    print(f'{src} does not exist')
