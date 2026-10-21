"""Fix all corrupted characters in project.py."""
import re

with open('routes/project.py', 'rb') as f:
    raw = f.read()

# The corruption: UTF-8 sequences for em-dash (â€") encoded as windows-1252 bytes
# \xe2\x80\x93 = en-dash, \xe2\x80\x94 = em-dash
# But we see: â€" = \xc3\xa2\xc2\x80\xc2\x93 (double-encoded)
# Or in latin-1 decoded then re-encoded: just replace with ' - '

lines = raw.split(b'\n')
fixed = []
for line in lines:
    try:
        decoded = line.decode('utf-8')
        # Replace Unicode replacement chars and curly stuff
        decoded = decoded.replace('�', '-')
        fixed.append(decoded.encode('utf-8'))
    except UnicodeDecodeError:
        # Line has bad bytes - decode as latin-1 and convert
        decoded = line.decode('latin-1')
        # Remove the bad multi-byte sequences by re-encoding safely
        encoded = decoded.encode('ascii', errors='replace').decode('ascii')
        # Replace bad patterns in print statements
        # Pattern: print(f"...â€" ..." -> print(f"... - ..."
        encoded = re.sub(r'[?]{2,}', ' - ', encoded)
        fixed.append(encoded.encode('utf-8'))

content = b'\n'.join(fixed)

# Now fix specific patterns: the corrupted em-dash in f-strings
# These appear as multi-byte sequences that break string literals
# Strategy: for any line containing a print(f"...") with bad chars, simplify the message
src = content.decode('utf-8', errors='replace')

# Fix corrupted lines with em-dash in print statements
def fix_print_line(m):
    line = m.group(0)
    # Replace any sequence of replacement chars with ' - '
    line = re.sub(r'�+', ' - ', line)
    return line

src = re.sub(r'.*�.*', fix_print_line, src)
src = src.lstrip('﻿')

with open('routes/project.py', 'w', encoding='utf-8') as f:
    f.write(src)

import ast
try:
    ast.parse(src)
    print('Syntax OK')
except SyntaxError as e:
    lines_list = src.splitlines()
    print(f'SyntaxError line {e.lineno}: {e.msg}')
    if e.lineno and e.lineno <= len(lines_list):
        print(repr(lines_list[e.lineno - 1]))
