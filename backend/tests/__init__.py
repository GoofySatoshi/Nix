"""
核心基础设施测试
"""

import pytest
import asyncio
import sys
import os

# 添加 backend 到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
