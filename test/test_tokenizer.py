import re

line = re.sub(r"\W+", " ", "Hello, 世界!!! This_is 2025-10-12.")
print(line)