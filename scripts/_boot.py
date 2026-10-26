"""scripts/ 안의 스크립트가 상위 폴더의 tracker 패키지를 import할 수 있게 한다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tracker.util import setup_console  # noqa: E402

setup_console()
