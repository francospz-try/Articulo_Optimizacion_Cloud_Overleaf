"""Genera tablas y figuras del artículo exclusivamente desde resultados.csv."""
import json
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import t
from .ejecutar import ROOT

METRICS=['availability','timely','mean_latency','p95','mean_wait','queue_mean','utilization','throughput','cost']


def ci(values):
    v=np.asarray(values,dtype=float)
    half=t.ppf(.975,len(v)-1)*v.std(ddof=1)/math.sqrt(len(v))
    return float(v.mean()),float(v.mean()-half),float(v.mean()+half)


def main():
    out=ROOT/'resultados'
    df=pd.read_csv(out/'replicas.csv')
    assert len(df)==36*df.seed.nunique()
    assert df.groupby(['load','seed']).trace_sha256.nunique().eq(1).all()
    assert (df.offered==df.correct+df.rejected+df.expired+df.failed).all()
    summary=[]
    for keys,g in df.groupby(['vms','policy','load','failure']):
        row=dict(zip(['vms','policy','load','failure'],keys))
        row['replicas']=len(g)
        for m in METRICS:
            row[m],row[m+'_lo'],row[m+'_hi']=ci(g[m])
        summary.append(row)
    s=pd.DataFrame(summary)
    s.to_csv(out/'resumen.csv',index=False)
    candidates=[]
    for (vms,policy),g in s.groupby(['vms','policy']):
        candidates.append(dict(vms=int(vms),policy=policy,cost=float(g.cost.iloc[0]),
            min_availability=float(g.availability.min()),min_timely=float(g.timely.min()),
            max_p95=float(g.p95.max()),feasible=bool((g.availability>=.99).all() and (g.timely>=.95).all()),
            all_lower_bounds_pass=bool((g.availability_lo>=.99).all() and (g.timely_lo>=.95).all())))
    c=pd.DataFrame(candidates)
    c.to_csv(out/'seleccion.csv',index=False)
    valid=[r for r in candidates if r['feasible']]
    chosen=min(valid,key=lambda r:(r['cost'],r['max_p95'])) if valid else None
    (out/'decision.json').write_text(json.dumps(dict(selected=chosen,candidates=candidates),indent=2),encoding='utf-8')
    paired=[]
    for (vms,load,failure),g in df.groupby(['vms','load','failure']):
        rr=g[g.policy=='RR'].set_index('seed')
        mp=g[g.policy=='MP'].set_index('seed')
        for metric in ['p95','mean_latency','timely','availability']:
            mean,lo,hi=ci(mp[metric]-rr[metric])
            paired.append(dict(vms=vms,load=load,failure=failure,metric=metric,MP_minus_RR=mean,lower=lo,upper=hi))
    pd.DataFrame(paired).to_csv(out/'diferencias_pareadas.csv',index=False)
    validation=json.loads((out/'validacion.json').read_text())
    tex=[]
    for name,val in validation.items():
        tex.append('\\newcommand{\\val'+name+'}{'+f"{val['mean']:.4f}"+'}')
        tex.append('\\newcommand{\\err'+name+'}{'+f"{val['relative_error_pct']:.2f}"+'}')
    if chosen:
        for name,value in [('ElegidaVM',str(chosen['vms'])),('ElegidaPolitica',chosen['policy']),
                           ('ElegidaCosto',f"{chosen['cost']:.4f}"),
                           ('ElegidaA',f"{chosen['min_availability']*100:.3f}"),
                           ('ElegidaG',f"{chosen['min_timely']*100:.3f}"),
                           ('ElegidaP',f"{chosen['max_p95']:.3f}")]:
            tex.append('\\newcommand{\\'+name+'}{'+value+'}')
        g=s[(s.vms==chosen['vms'])&(s.policy==chosen['policy'])]
        for name,value in [('ElegidaLCBA',100*g.availability_lo.min()),('ElegidaLCBG',100*g.timely_lo.min())]:
            tex.append('\\newcommand{\\'+name+'}{'+f'{value:.3f}'+'}')
    for prefix,vms,load,failure in [('Alta',4,'alta',0),('Pico',8,'pico',1)]:
        r=next(r for r in paired if r['vms']==vms and r['load']==load and r['failure']==failure and r['metric']=='p95')
        base=s[(s.vms==vms)&(s.policy=='RR')&(s.load==load)&(s.failure==failure)].p95.iloc[0]
        for suffix,value in [('Dif',r['MP_minus_RR']),('Lo',r['lower']),('Hi',r['upper']),('Red',-100*r['MP_minus_RR']/base)]:
            tex.append('\\newcommand{\\'+prefix+suffix+'}{'+f'{value:.3f}'+'}')
    costs=c.groupby('vms').cost.first()
    cost_per_vm=(costs.loc[8]-costs.loc[6])/2
    fixed_cost=costs.loc[4]-4*cost_per_vm
    for name,value,digits in [
        ('CostoVMAdicional',cost_per_vm,4),('CostoBalanceador',fixed_cost,4),
        ('CostoCuatro',costs.loc[4],4),('CostoSeis',costs.loc[6],4),('CostoOcho',costs.loc[8],4),
        ('AumentoSeisOcho',100*(costs.loc[8]-costs.loc[6])/costs.loc[6],1),
        ('AhorroOchoCuatro',100*(costs.loc[8]-costs.loc[4])/costs.loc[8],1),
        ('GCuatroMP',100*c[(c.vms==4)&(c.policy=='MP')].min_timely.iloc[0],3),
        ('GSeisMP',100*c[(c.vms==6)&(c.policy=='MP')].min_timely.iloc[0],3)]:
        tex.append('\\newcommand{\\'+name+'}{'+f'{value:.{digits}f}'+'}')
    (out/'valores.tex').write_text('\n'.join(tex)+'\n',encoding='utf-8')
    lines=[]
    for r in candidates:
        lines.append(f"{r['vms']} & {r['policy']} & {r['cost']:.4f} & {100*r['min_availability']:.3f} & {100*r['min_timely']:.3f} & {r['max_p95']:.3f} & "+('Sí' if r['feasible'] else 'No')+r' \\')
    (out/'tabla_seleccion.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    lines=[]
    for _,r in s[s.failure==0].sort_values(['load','vms','policy']).iterrows():
        lines.append(f"{dict(alta='Alta',baja='Baja',pico='Pico')[r['load']]} & {r.vms} & {r.policy} & {r.p95:.3f} & {r.queue_mean:.2f} & {100*r.utilization:.1f} & {100*r.timely:.2f}"+r' \\')
    (out/'tabla_rendimiento.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    lines=[]
    for name,r in validation.items():
        symbol='\\rho' if name=='rho' else name
        lines.append(f"${symbol}$ & {r['theory']:.3f} & {r['mean']:.4f} & [{r['lower']:.4f}, {r['upper']:.4f}] & {r['relative_error_pct']:.2f}"+r' \\')
    (out/'tabla_validacion.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    figures(s,c)
    print(c.to_string(index=False))
    print('Seleccionada:',chosen)


def figures(s,c):
    dest=ROOT/'figuras';dest.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.spines.top':False,
                         'axes.spines.right':False,'pdf.fonttype':42})
    fig,ax=plt.subplots(figsize=(3.45,2.5),layout='constrained')
    for policy,color in [('RR','#be5a2c'),('MP','#176596')]:
        for failure,style in [(0,'-'),(1,'--')]:
            g=s[(s.load=='pico')&(s.policy==policy)&(s.failure==failure)].sort_values('vms')
            ax.errorbar(g.vms,g.p95,yerr=[g.p95-g.p95_lo,g.p95_hi-g.p95],color=color,linestyle=style,
                        marker='o',markersize=3,capsize=2,label=policy+(' con fallo' if failure else ' sin fallo'))
    ax.axhline(2,color='#777777',lw=.8,ls=':',label='Referencia: 2 s')
    ax.set(xlabel='Máquinas virtuales',ylabel='p95 de latencia (s)',xticks=[4,6,8],ylim=(0,None))
    ax.legend(fontsize=6.5,ncol=2);ax.grid(alpha=.2)
    fig.savefig(dest/'latencia.pdf');plt.close(fig)
    fig,ax=plt.subplots(figsize=(3.45,2.5),layout='constrained')
    for _,r in c.iterrows():
        ax.scatter(r.cost,100*r.min_timely,color='#176596' if r.policy=='MP' else '#be5a2c',marker='o' if r.policy=='MP' else 's',s=25)
        offset=(5,8) if r.policy=='MP' else (5,-12)
        ax.annotate(f'{r.vms} {r.policy}',(r.cost,100*r.min_timely),xytext=offset,textcoords='offset points',fontsize=7)
    ax.axhline(95,color='#555555',ls='--',lw=.8)
    ax.set(xlabel='Costo por ejecución (u. m.)',ylabel='Peor cumplimiento de 2 s (%)',xlim=(.45,1.08),ylim=(30,105))
    ax.grid(alpha=.2);fig.savefig(dest/'costo_servicio.pdf');plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(7.0,4.3),sharex=True,layout='constrained',height_ratios=[1,1.7,1])
    x=np.linspace(0,60,3601);d=np.where((x>=20)&(x<40),120,40)
    axes[0].plot(x,d,color='#333333');axes[0].set_ylabel('Llegadas/s')
    for vms,policy,color in [(4,'RR','#be5a2c'),(8,'RR','#bb941c'),(8,'MP','#176596')]:
        frame=pd.read_csv(ROOT/'resultados'/f'serie_pico_{vms}_{policy}.csv')
        axes[1].plot(frame.t/60,frame.queue,label=f'{vms} VMs, {policy}',color=color,lw=.9)
        if policy=='MP':
            axes[2].plot(frame.t/60,frame.busy,label='vCPU ocupadas (8 VMs MP)',color=color,lw=.7)
            axes[2].plot(frame.t/60,2*frame.up,label='vCPU disponibles',color='#333333',ls='--')
    axes[1].set_ylabel('Solicitudes en cola');axes[1].legend(ncol=3,fontsize=7)
    axes[2].set(ylabel='vCPU',xlabel='Tiempo de medición (min)',ylim=(0,17));axes[2].legend(fontsize=7,ncol=2)
    for ax in axes:
        ax.axvspan(30,32,color='#e5b2b2',alpha=.45);ax.grid(alpha=.2);ax.set_xlim(0,60)
    fig.savefig(dest/'evolucion.pdf');fig.savefig(dest/'evolucion.png',dpi=150);plt.close(fig)


if __name__=='__main__':
    main()
