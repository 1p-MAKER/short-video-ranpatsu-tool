import sys
import threading
import time

import pytest

from podcast_clip_factory.utils.media import CommandError, run_command


def test_run_command_can_be_cancelled():
    cancel_event = threading.Event()

    def stopper():
        time.sleep(0.3)
        cancel_event.set()

    threading.Thread(target=stopper, daemon=True).start()

    with pytest.raises(CommandError, match="cancelled"):
        run_command([sys.executable, "-c", "import time; time.sleep(5)"], cancel_event=cancel_event)
