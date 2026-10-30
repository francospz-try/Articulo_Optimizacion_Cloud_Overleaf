"""Reproducción visual de las trazas reales, con pausa y control de tiempo."""
import argparse
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button,Slider
import numpy as np
import pandas as pd
from .ejecutar import ROOT


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--captura',help='Guardar una imagen en lugar de abrir la ventana')
    parser.add_argument('--tiempo',type=int,default=0)
    args=parser.parse_args()
    if not 0<=args.tiempo<=3600:
        parser.error('El tiempo debe estar entre 0 y 3600 s')
    frames=[]
    for c,b,color in [(4,'RR','#be5a2c'),(8,'RR','#bb941c'),(8,'MP','#176596')]:
        df=pd.read_csv(ROOT/'resultados'/f'serie_pico_{c}_{b}.csv')
        frames.append((c,b,color,df))
    fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True)
    fig.subplots_adjust(bottom=.2,top=.85,hspace=.25)
    fig.suptitle('Demostración: demanda, colas y fallo de host\nReproducción de la simulación, semilla 0',fontsize=14)
    lines=[]
    for c,b,color,df in frames:
        line,=axes[0].plot([],[],color=color,label=f'{c} VMs, {b}')
        lines.append(line)
    axes[0].set(ylabel='Solicitudes esperando',ylim=(0,430));axes[0].legend()
    df=frames[-1][3]
    busy,=axes[1].plot([],[],label='vCPU ocupadas: 8 VMs MP',color='#176596')
    capacity,=axes[1].plot([],[],label='vCPU disponibles',color='#333333',ls='--')
    axes[1].set(xlim=(0,60),ylim=(0,17),xlabel='Minutos de medición',ylabel='vCPU');axes[1].legend(loc='lower left')
    for ax in axes:
        ax.axvspan(30,32,color='#e5b2b2',alpha=.5);ax.grid(alpha=.2)
    status=fig.text(.09,.89,'')
    slider=Slider(fig.add_axes([.15,.08,.60,.03]),'Tiempo (s)',0,3600,valinit=args.tiempo,valstep=5)
    button=Button(fig.add_axes([.87,.065,.10,.055]),'Pausa')
    state={'playing':True,'t':0,'updating':False}
    def draw(t):
        state['t']=int(t)
        for line,(_,_,_,data) in zip(lines,frames):
            visible=data[data.t<=t];line.set_data(visible.t/60,visible.queue)
        visible=df[df.t<=t]
        busy.set_data(visible.t/60,visible.busy);capacity.set_data(visible.t/60,2*visible.up)
        rate=120 if 1200<=t<2400 else 40
        status.set_text(f't = {int(t):4d} s | Demanda: {rate} solicitudes/s | Host 1: '+('CAÍDO' if 1800<=t<1920 else 'operativo'))
        fig.canvas.draw_idle()
    def change(value):
        if not state['updating']:
            draw(value)
    def toggle(event):
        state['playing']=not state['playing'];button.label.set_text('Pausa' if state['playing'] else 'Continuar')
    def animate(_):
        if state['playing']:
            next_t=(state['t']+5)%3605
            state['updating']=True;slider.set_val(next_t);state['updating']=False
            draw(next_t)
    slider.on_changed(change);button.on_clicked(toggle)
    draw(args.tiempo)
    if args.captura:
        fig.savefig(args.captura,dpi=140)
        plt.close(fig)
    else:
        animation=FuncAnimation(fig,animate,interval=40,cache_frame_data=False)
        plt.show()


if __name__=='__main__':
    main()
