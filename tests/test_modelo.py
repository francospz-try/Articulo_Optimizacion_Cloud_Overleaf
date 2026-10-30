"""Pruebas de comportamiento con trazas deterministas y resultados conocidos."""
from dataclasses import replace
import unittest
from simulacion.modelo import Config, Model, make_trace, trace_hash


class Tests(unittest.TestCase):
    def config(self,**kw):
        return replace(Config(),**(dict(vms=1,slots=1,warmup=0,duration=20,network=0)|kw))

    def test_fifo(self):
        m=Model(self.config(),[0,0.1,0.2],[1,2,1]);r=m.run()
        self.assertEqual(r['correct'],3)
        self.assertAlmostEqual(r['mean_latency'],(1+2.9+3.8)/3)

    def test_queue_limit(self):
        r=Model(self.config(queue_limit=1),[0,0.1,0.2],[1,1,1]).run()
        self.assertEqual((r['correct'],r['rejected']),(2,1))

    def test_cpu_released_after_expiration(self):
        m=Model(self.config(deadline=1),[0,0.2],[5,0.1]);r=m.run()
        self.assertEqual((r['expired'],r['correct']),(1,1))
        self.assertAlmostEqual(r['mean_latency'],.9)

    def test_queued_expiration_removes_waiter(self):
        m=Model(self.config(deadline=1),[0,.1,.2],[5,5,5]);r=m.run()
        self.assertEqual(r['expired'],3)
        self.assertEqual(m.vms[0].waiting,0)

    def test_failure_and_detection(self):
        cfg=self.config(failure=True,failure_at=1,failure_duration=3,detection=.5)
        r=Model(cfg,[0,1.1,1.8,4.1],[2,.1,.1,.1]).run()
        self.assertEqual((r['failed'],r['correct']),(3,1))

    def test_network_does_not_hold_cpu(self):
        r=Model(self.config(network=.5),[0,.11],[.1,.1]).run()
        self.assertAlmostEqual(r['mean_latency'],.6)

    def test_measurement_cohort_and_tail(self):
        cfg=replace(self.config(),warmup=1,duration=1)
        r=Model(cfg,[.5,1.9],[.1,.5]).run()
        self.assertEqual((r['offered'],r['correct']),(1,1))
        self.assertEqual(r['throughput'],0)

    def test_queue_time_integral(self):
        r=Model(self.config(),[0,0],[1,1]).run()
        self.assertAlmostEqual(r['queue_mean'],1/20)
        self.assertAlmostEqual(r['utilization'],2/20)

    def test_mp_avoids_busy_vm(self):
        cfg=replace(self.config(),vms=2,policy='MP')
        m=Model(cfg,[0,.01,.12],[2,.1,.1]);r=m.run()
        self.assertAlmostEqual(r['mean_latency'],(2+.1+.1)/3)

    def test_reproducible_trace(self):
        t,w=make_trace('baja',0,warmup=0,duration=2)
        t2,w2=make_trace('baja',0,warmup=0,duration=2)
        self.assertEqual(trace_hash(t,w),trace_hash(t2,w2))


if __name__=='__main__':
    unittest.main()
