"""Contraste de la implementación con la solución analítica M/M/1."""
from dataclasses import replace
import json
import math
import numpy as np
from scipy.stats import t
from .modelo import Config, Model
from .ejecutar import ROOT,write_csv


def main():
    rows=[]
    for seed in range(30):
        a=np.random.default_rng(np.random.SeedSequence([8675309,seed,0]))
        w=np.random.default_rng(np.random.SeedSequence([8675309,seed,1]))
        arrivals=np.cumsum(a.exponential(.2,80000))
        arrivals=arrivals[arrivals<11000]
        work=w.exponential(.1,len(arrivals))
        cfg=replace(Config(),vms=1,slots=1,queue_limit=None,warmup=1000,duration=10000,
                    network=0,deadline=math.inf)
        r=Model(cfg,arrivals,work).run()
        rows.append(dict(seed=seed,W=r['mean_latency'],L=r['queue_mean']+r['utilization'],rho=r['utilization']))
    write_csv(ROOT/'resultados'/'validacion_replicas.csv',rows)
    summary={}
    for name,theory in [('W',.2),('L',1.),('rho',.5)]:
        y=np.array([r[name] for r in rows]);half=t.ppf(.975,29)*y.std(ddof=1)/np.sqrt(30)
        summary[name]=dict(theory=theory,mean=y.mean(),lower=y.mean()-half,upper=y.mean()+half,
                           relative_error_pct=100*abs(y.mean()-theory)/theory)
    (ROOT/'resultados'/'validacion.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
