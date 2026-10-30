"""Simulación de eventos discretos; reloj y calendario de eventos de SimPy."""
from collections import deque
from dataclasses import dataclass
from functools import partial
import hashlib
import math

import numpy as np
import simpy


@dataclass(frozen=True)
class Config:
    vms: int = 4
    policy: str = "RR"
    slots: int = 2
    queue_limit: int | None = 100
    warmup: float = 600.0
    duration: float = 3600.0
    network: float = 0.02
    deadline: float = 10.0
    target: float = 2.0
    failure: bool = False
    failure_at: float = 1800.0
    failure_duration: float = 120.0
    detection: float = 5.0
    vm_price: float = 0.10
    lb_price: float = 0.02


@dataclass(slots=True)
class Request:
    ident: int
    arrival: float
    work: float
    measured: bool
    state: str = "queued"
    started: float | None = None


class VM:
    def __init__(self, ident):
        self.ident = ident
        self.host = ident % 4
        self.up = True
        self.eligible = True
        self.stale_pending = 0
        self.busy = 0
        self.waiting = 0
        self.queue = deque()
        self.active = {}
        self.last = 0.0
        self.busy_area = 0.0
        self.queue_area = 0.0


def make_trace(load, seed, warmup=600.0, duration=3600.0, service_mean=0.10):
    """Genera llegadas y trabajo con flujos RNG independientes de las políticas."""
    load_index = {"baja": 0, "alta": 1, "pico": 2}[load]
    arrivals_rng = np.random.default_rng(np.random.SeedSequence([20261029, seed, load_index, 0]))
    work_rng = np.random.default_rng(np.random.SeedSequence([20261029, seed, load_index, 1]))
    rates = {"baja": [40.0]*3, "alta": [72.0]*3, "pico": [40.0,120.0,40.0]}[load]
    spans = [(0.0, warmup, rates[0])]
    spans += [(warmup+i*duration/3, warmup+(i+1)*duration/3, r) for i,r in enumerate(rates)]
    chunks = []
    for begin,end,rate in spans:
        t = begin
        while t < end:
            n = max(256, int((end-t)*rate*1.05)+100)
            ts = t + np.cumsum(arrivals_rng.exponential(1/rate, n))
            chunks.append(ts[ts < end])
            t = float(ts[-1])
    times = np.concatenate(chunks)
    work = work_rng.exponential(service_mean, len(times))
    return times, work


def trace_hash(times, work):
    digest = hashlib.sha256()
    digest.update(np.asarray(times,dtype="<f8").tobytes())
    digest.update(np.asarray(work,dtype="<f8").tobytes())
    return digest.hexdigest()


class Model:
    def __init__(self, config, times, work, sample_interval=None):
        if config.policy not in ("RR", "MP") or config.vms < 1 or config.slots < 1:
            raise ValueError("Configuración no válida")
        if len(times) != len(work) or np.any(np.diff(times)<0) or np.any(np.asarray(work)<0):
            raise ValueError("Traza no válida")
        self.cfg = config
        self.env = simpy.Environment()
        self.vms = [VM(i) for i in range(config.vms)]
        self.cursor = 0
        self.times, self.work = times, work
        self.counts = dict(offered=0, correct=0, good=0, rejected=0, expired=0, failed=0)
        self.latencies = []
        self.waits = []
        self.throughput_count = 0
        self.max_busy = 0
        self.samples = []
        self.sample_interval = sample_interval

    def schedule(self, delay, callback, value=None):
        ev = self.env.timeout(max(0.0, delay), value)
        ev.callbacks.append(callback)

    def touch(self, vm):
        end = self.cfg.warmup + self.cfg.duration
        dt = max(0.0, min(self.env.now,end)-max(vm.last,self.cfg.warmup))
        vm.busy_area += dt*vm.busy
        vm.queue_area += dt*vm.waiting
        vm.last = self.env.now

    def select(self):
        n = len(self.vms)
        order = [(self.cursor+i)%n for i in range(n)]
        eligible = [i for i in order if self.vms[i].eligible]
        if not eligible:
            return None
        if self.cfg.policy == "RR":
            i = eligible[0]
        else:
            i = min(eligible,key=lambda j:(self.vms[j].busy+self.vms[j].waiting) if self.vms[j].up else self.vms[j].stale_pending)
        self.cursor = (i+1)%n
        return self.vms[i]

    def arrive(self, ident, t, work):
        measured = self.cfg.warmup <= t < self.cfg.warmup+self.cfg.duration
        if measured:
            self.counts["offered"] += 1
        vm = self.select()
        if vm is None or not vm.up:
            if measured:
                self.counts["failed"] += 1
            return
        if vm.busy >= self.cfg.slots and self.cfg.queue_limit is not None and vm.waiting >= self.cfg.queue_limit:
            if measured:
                self.counts["rejected"] += 1
            return
        req = Request(ident, t, work, measured)
        vm.active[ident] = req
        self.touch(vm)
        if vm.busy < self.cfg.slots:
            self.start(vm,req)
        else:
            vm.queue.append(req)
            vm.waiting += 1
        if math.isfinite(self.cfg.deadline):
            self.schedule(self.cfg.deadline, partial(self.expire,vm),req)

    def start(self, vm, req):
        req.state = "running"
        req.started = self.env.now
        vm.busy += 1
        self.max_busy = max(self.max_busy,vm.busy)
        self.schedule(req.work, partial(self.cpu_done,vm),req)

    def drain(self, vm):
        while vm.up and vm.busy < self.cfg.slots and vm.queue:
            req = vm.queue.popleft()
            if req.state != "queued":
                continue
            vm.waiting -= 1
            self.start(vm,req)

    def cpu_done(self, vm, ev):
        req = ev.value
        if req.state != "running":
            return
        self.touch(vm)
        vm.busy -= 1
        req.state = "network"
        self.drain(vm)
        self.schedule(self.cfg.network,partial(self.response,vm),req)

    def terminal(self, vm, req, outcome):
        if req.state == "done":
            return
        self.touch(vm)
        if req.state == "queued":
            vm.waiting -= 1
        elif req.state == "running":
            vm.busy -= 1
        req.state = "done"
        del vm.active[req.ident]
        if req.measured:
            self.counts[outcome] += 1
            if outcome == "correct":
                latency = self.env.now-req.arrival
                self.latencies.append(latency)
                self.waits.append(req.started-req.arrival)
                if latency <= self.cfg.target:
                    self.counts["good"] += 1
        if outcome == "correct" and self.cfg.warmup <= self.env.now < self.cfg.warmup+self.cfg.duration:
            self.throughput_count += 1
        self.drain(vm)

    def response(self, vm, ev):
        if ev.value.state == "network":
            self.terminal(vm,ev.value,"correct")

    def expire(self, vm, ev):
        if ev.value.state != "done":
            self.terminal(vm,ev.value,"expired")

    def fail(self, ev=None):
        for vm in self.vms:
            if vm.host == 0:
                vm.stale_pending = vm.busy+vm.waiting
                vm.up = False
                for req in list(vm.active.values()):
                    self.terminal(vm,req,"failed")
                vm.queue.clear()

    def detect(self, ev=None):
        for vm in self.vms:
            if vm.host == 0:
                vm.eligible = False

    def recover(self, ev=None):
        for vm in self.vms:
            if vm.host == 0:
                vm.up = vm.eligible = True

    def arrivals(self):
        for ident,(t,w) in enumerate(zip(self.times,self.work)):
            yield self.env.timeout(float(t)-self.env.now)
            self.arrive(ident,float(t),float(w))

    def sampler(self):
        while True:
            self.samples.append(dict(t=self.env.now-self.cfg.warmup,
                queue=sum(v.waiting for v in self.vms),busy=sum(v.busy for v in self.vms),
                up=sum(v.up for v in self.vms),**self.counts))
            yield self.env.timeout(self.sample_interval)

    def run(self):
        if self.cfg.failure:
            at = self.cfg.warmup+self.cfg.failure_at
            self.schedule(at,self.fail)
            self.schedule(at+self.cfg.detection,self.detect)
            self.schedule(at+self.cfg.failure_duration,self.recover)
        self.env.process(self.arrivals())
        if self.sample_interval:
            self.env.process(self.sampler())
        end = self.cfg.warmup+self.cfg.duration
        follow = self.cfg.deadline if math.isfinite(self.cfg.deadline) else 1000.0
        self.env.run(until=end+follow)
        for vm in self.vms:
            self.touch(vm)
        assert all(not v.active for v in self.vms), "Solicitudes sin estado terminal"
        c = self.counts
        assert c["offered"] == sum(c[k] for k in ("correct","rejected","expired","failed")), c
        assert self.max_busy <= self.cfg.slots
        n = c["offered"]
        horizon_h = (end+follow)/3600
        return dict(**c,
            availability=c["correct"]/n if n else math.nan,
            timely=c["good"]/n if n else math.nan,
            mean_latency=float(np.mean(self.latencies)) if self.latencies else math.nan,
            p95=float(np.quantile(self.latencies,.95)) if self.latencies else math.nan,
            mean_wait=float(np.mean(self.waits)) if self.waits else math.nan,
            queue_mean=sum(v.queue_area for v in self.vms)/self.cfg.duration,
            utilization=sum(v.busy_area for v in self.vms)/(self.cfg.slots*self.cfg.vms*self.cfg.duration),
            throughput=self.throughput_count/self.cfg.duration,
            cost=(self.cfg.vms*self.cfg.vm_price+self.cfg.lb_price)*horizon_h)
