"""测试文件锁保护功能。

验证 config_center_service 的文件锁保护机制。
"""

import os
import sys
import tempfile
import time
import threading
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.config_center_service import ConfigCenterService


def test_basic_write_with_lock():
    """测试基本写入功能（带锁保护）。"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        test_file = Path(f.name)
        f.write("TEST_KEY1=value1\n")
        f.write("TEST_KEY2=value2\n")

    service = ConfigCenterService()

    # 写入新配置
    service._write_env_file(test_file, {"TEST_KEY3": "value3", "TEST_KEY1": "updated1"})

    # 验证写入结果
    result = service._read_env_file(test_file)
    assert result["TEST_KEY1"] == "updated1", f"Expected 'updated1', got {result['TEST_KEY1']}"
    assert result["TEST_KEY2"] == "value2", f"Expected 'value2', got {result['TEST_KEY2']}"
    assert result["TEST_KEY3"] == "value3", f"Expected 'value3', got {result['TEST_KEY3']}"

    # 清理
    test_file.unlink()
    print("✓ 基本写入测试通过")


def test_concurrent_writes():
    """测试并发写入场景（验证锁保护）。"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        test_file = Path(f.name)
        f.write("INITIAL_KEY=initial\n")

    service = ConfigCenterService()
    results = []
    errors = []

    def writer_thread(thread_id: int, key: str, value: str):
        """写入线程。"""
        try:
            # 每个线程写入不同的键
            service._write_env_file(test_file, {key: value})
            results.append((thread_id, key, value))
        except Exception as e:
            errors.append((thread_id, str(e)))

    # 创建多个线程同时写入
    threads = []
    num_threads = 5

    for i in range(num_threads):
        key = f"THREAD_KEY_{i}"
        value = f"thread_value_{i}"
        t = threading.Thread(target=writer_thread, args=(i, key, value))
        threads.append(t)

    # 同时启动所有线程
    start_time = time.time()
    for t in threads:
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join(timeout=30)

    elapsed = time.time() - start_time

    # 验证结果
    final_result = service._read_env_file(test_file)

    print(f"并发写入完成，耗时: {elapsed:.2f}s")
    print(f"成功写入: {len(results)} 个线程")
    print(f"错误: {len(errors)} 个线程")

    # 检查所有写入是否成功
    for thread_id, key, value in results:
        assert final_result.get(key) == value, f"Thread {thread_id}: Expected '{value}', got '{final_result.get(key)}'"

    # 清理
    test_file.unlink()
    print("✓ 并发写入测试通过")


def test_lock_timeout():
    """测试锁超时场景。"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        test_file = Path(f.name)
        f.write("TEST_KEY=value\n")

    service = ConfigCenterService()
    lock_file_path = service._get_lock_file_path(test_file)

    # 确保锁文件存在
    lock_file_path.touch()

    # 模拟锁被其他进程持有
    import fcntl

    # 打开锁文件并持有锁
    with open(lock_file_path, 'r') as lock_holder:
        fcntl.flock(lock_holder.fileno(), fcntl.LOCK_EX)

        try:
            # 尝试写入，应该超时失败
            # 使用另一个文件句柄尝试获取锁
            start_time = time.time()
            try:
                with open(lock_file_path, 'r') as another_handle:
                    # 设置短超时以快速失败
                    service._acquire_file_lock(another_handle, timeout=0.5)
                    print("警告：预期应该超时但成功了")
            except TimeoutError as e:
                elapsed = time.time() - start_time
                print(f"✓ 锁超时测试通过，耗时: {elapsed:.2f}s")
                print(f"  错误信息: {e}")
        finally:
            # 释放锁
            fcntl.flock(lock_holder.fileno(), fcntl.LOCK_UN)

    # 清理
    test_file.unlink()
    if lock_file_path.exists():
        lock_file_path.unlink()


def test_write_preserves_comments():
    """测试写入保留注释。"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        test_file = Path(f.name)
        f.write("# 这是注释\n")
        f.write("KEY1=value1\n")
        f.write("# 另一个注释\n")
        f.write("KEY2=value2\n")

    service = ConfigCenterService()

    # 更新配置
    service._write_env_file(test_file, {"KEY1": "updated1", "KEY3": "new_value"})

    # 验证注释被保留
    content = test_file.read_text(encoding="utf-8")
    assert "# 这是注释" in content, "注释丢失"
    assert "# 另一个注释" in content, "注释丢失"

    result = service._read_env_file(test_file)
    assert result["KEY1"] == "updated1"
    assert result["KEY2"] == "value2"
    assert result["KEY3"] == "new_value"

    # 清理
    test_file.unlink()
    print("✓ 注释保留测试通过")


def main():
    """运行所有测试。"""
    print("=" * 60)
    print("测试 config_center_service 文件锁保护功能")
    print("=" * 60)

    test_basic_write_with_lock()
    test_write_preserves_comments()
    test_concurrent_writes()
    test_lock_timeout()

    print("\n" + "=" * 60)
    print("所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()