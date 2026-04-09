"""
ESP32 -> Doubao ASR HTTP bridge compatibility launcher.

用途：
- 保留原有脚本启动方式：python3 examples/esp32_asr_bridge.py
- 内部复用新的 api 服务实现
- 默认继续提供旧的 ESP32 接口：POST /asr/transcribe
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.cli import main


if __name__ == "__main__":
    main()
