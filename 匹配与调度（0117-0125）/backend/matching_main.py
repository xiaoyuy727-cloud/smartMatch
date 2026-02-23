"""兼容入口：保留 matching_main:app 的启动方式，实际使用统一后的 main.app。"""
from main import app  # noqa: F401