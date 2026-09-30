"""验证慢日志输出不会阻塞请求，积压日志也不会无限占用内存。"""

import logging
import threading
import unittest
from unittest.mock import patch

from services.api.app.core.logging_config import setup_logging


class SlowConsole(logging.Handler):
    """模拟 Docker 日志管道停止消费。"""

    def __init__(self):
        """准备开始写入与释放写入的同步信号。"""
        super().__init__()
        self.started = threading.Event()
        self.unblock = threading.Event()

    def emit(self, record):
        """等待外部恢复，模拟实际阻塞。"""
        self.started.set()
        self.unblock.wait(timeout=2)


class LoggingBackpressureTests(unittest.TestCase):
    """覆盖日志反压与缓存上限。"""

    def test_slow_console_is_async_and_queue_is_bounded(self):
        """日志消费卡住时请求仍能返回，超出容量的日志直接计数丢弃。"""
        root = logging.getLogger()
        previous_handlers = list(root.handlers)
        previous_level = root.level
        console = SlowConsole()
        caller_done = threading.Event()
        handler = None
        caller = None
        try:
            with patch("logging.StreamHandler", return_value=console), patch.dict(
                "os.environ", {"QUANT_LOG_QUEUE_LIMIT": "2"}
            ):
                setup_logging(level=logging.INFO)
            def log():
                """模拟请求线程产生日志。"""
                root.info("首次日志")
                caller_done.set()
            caller = threading.Thread(target=log)
            caller.start()
            self.assertTrue(console.started.wait(timeout=1))
            self.assertTrue(caller_done.wait(timeout=0.1), "请求被慢日志阻塞")
            self.assertEqual(len(root.handlers), 1)
            handler = root.handlers[0]
            self.assertEqual(handler.queue.maxsize, 2)
            root.info("积压日志一")
            root.info("积压日志二")
            with patch("sys.stderr.write") as stderr:
                root.info("超出容量")
            stderr.assert_not_called()
            self.assertEqual(handler.dropped_records, 1)
        finally:
            console.unblock.set()
            if caller is not None:
                caller.join(timeout=3)
            if handler is not None and hasattr(handler, "listener"):
                handler.queue.join()
                handler.listener.stop()
            root.handlers[:] = previous_handlers
            root.setLevel(previous_level)
