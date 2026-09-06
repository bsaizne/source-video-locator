"""pipeline_map 单测（性能批① 流水线, 2026-09-06）。纯内存, 无 IO。

运行: venv python -m unittest mvp.tests.test_pipeline -v
"""
import unittest

from engine.common import pipeline_map


class PipelineMapTest(unittest.TestCase):
    def test_order_preserved(self):
        got = pipeline_map(iter(range(100)), lambda x: x * 2)
        self.assertEqual(got, [i * 2 for i in range(100)])

    def test_empty(self):
        self.assertEqual(pipeline_map(iter(()), str), [])

    def test_produce_error_propagates(self):
        def gen():
            yield 1
            yield 2
            raise ValueError("boom-produce")

        with self.assertRaises(ValueError):
            pipeline_map(gen(), str)

    def test_fn_error_propagates_and_stops_producer(self):
        produced = []

        def gen():
            for i in range(10000):
                produced.append(i)
                yield i

        calls = []

        def fn(x):
            calls.append(x)
            if x == 2:
                raise RuntimeError("boom-fn")
            return x

        with self.assertRaises(RuntimeError):
            pipeline_map(gen(), fn)
        self.assertLess(len(produced), 100)   # 消费方异常后生产者尽快停止
        self.assertEqual(calls, [0, 1, 2])    # 保序, 首个异常重抛

    def test_slow_consumer_no_deadlock(self):
        # 生产远快于消费: 队列背压路径(超时重试+哨兵必达)不形成自死锁
        got = pipeline_map(iter(range(500)), lambda x: sum(range(x % 7)))
        self.assertEqual(len(got), 500)


if __name__ == "__main__":
    unittest.main()
