"""Ejecutar desde la raíz: python -m simulacion.ejecutar --replicas 30."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import time

import numpy as np
import simpy
from .modelo import Config, Model, make_trace, trace_hash


ROOT = Path(__file__).resolve().parents[1]


def group(task):
    load,seed=task
    times,work=make_trace(load,seed)
    digest=trace_hash(times,work)
    rows=[]
    for vms in (4,6,8):
        for policy in ("RR","MP"):
            for failure in (False,True):
                cfg=Config(vms=vms,policy=policy,failure=failure)
                row=Model(cfg,times,work).run()
                rows.append(dict(load=load,seed=seed,vms=vms,policy=policy,failure=int(failure),trace_sha256=digest,**row))
    return rows


def write_csv(path,rows):
    with Path(path).open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--replicas",type=int,default=30)
    parser.add_argument("--workers",type=int,default=min(6,os.cpu_count() or 1))
    parser.add_argument("--benchmark",action="store_true")
    args=parser.parse_args()
    if args.replicas<2 or args.workers<1:
        parser.error("Se requieren al menos 2 réplicas y 1 trabajador")
    out=ROOT/"resultados";out.mkdir(exist_ok=True)
    start=time.perf_counter()
    if args.benchmark:
        times,work=make_trace("alta",0)
        print(Model(Config(policy="MP"),times,work).run(),flush=True)
        print(f"Segundos: {time.perf_counter()-start:.2f}",flush=True)
        return
    tasks=[(load,seed) for load in ("baja","alta","pico") for seed in range(args.replicas)]
    rows=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(group,t) for t in tasks]
        for i,f in enumerate(as_completed(futures),1):
            rows.extend(f.result())
            print(f"{i}/{len(tasks)} trazas; {len(rows)} ejecuciones; {time.perf_counter()-start:.1f} s",flush=True)
    rows.sort(key=lambda r:(r['load'],r['vms'],r['policy'],r['failure'],r['seed']))
    write_csv(out/"replicas.csv",rows)
    for vms,policy in [(4,"RR"),(8,"RR"),(8,"MP")]:
        times,work=make_trace("pico",0)
        model=Model(Config(vms=vms,policy=policy,failure=True),times,work,sample_interval=1)
        model.run()
        write_csv(out/f"serie_pico_{vms}_{policy}.csv",[r for r in model.samples if 0<=r['t']<=3600])
    files=["simulacion/modelo.py","simulacion/ejecutar.py","requirements.txt"]
    metadata=dict(python=platform.python_version(),numpy=np.__version__,simpy=simpy.__version__,
        replicas=args.replicas,executions=len(rows),seed_base=20261029,workers=args.workers,
        elapsed_seconds=time.perf_counter()-start,configuration=asdict(Config()),
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files})
    (out/"metadatos.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    print("Resultados completos guardados.",flush=True)


if __name__=="__main__":
    main()
