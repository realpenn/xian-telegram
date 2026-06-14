import os
import sys

# 确保仓库根目录在 sys.path 上，使 `import config`/`import services` 在测试中可用。
sys.path.insert(0, os.path.dirname(__file__))
