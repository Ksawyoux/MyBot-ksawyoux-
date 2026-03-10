import re
text = 'Hello (world) and [link](http://example.com) with **bold** and * bullet and __italic__'

text = re.sub(r'(?m)^(\s*)([-*])\s+', r'\1• ', text)
text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text, flags=re.DOTALL)
text = re.sub(r'__(.+?)__', r'_\1_', text, flags=re.DOTALL)

if text.count('*') % 2 != 0: text = text.replace('*', r'\*')
if text.count('_') % 2 != 0: text = text.replace('_', r'\_')
if text.count('`') % 2 != 0: text = text.replace('`', r'\`')

escape_chars = r'.!+-=|{}#>~'
escaped = re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)
escaped = escaped.replace('(', r'\(').replace(')', r'\)')
escaped = re.sub(r'\[([^\]]+)\]\\\(([^)]+)\\\)', r'[\1](\2)', escaped)

print(escaped)
