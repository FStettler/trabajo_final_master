import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
from PIL import Image
from dataclean import clean

st.set_page_config(page_title='TFM', page_icon=':bar_chart:', layout='wide')

image = Image.open('./media/Logo.jpg')
st.image(image, width=50)

st.title('DASHBOARD REVENUE MANAGER')

#CARGA LOS DATOS DE LAS RESERVAS
@st.cache
def read_data():
    data = pd.read_excel('./data/reservas.xlsx',sheet_name='RESERVAS')

    data = data[['Reserva','Fecha de reserva','Acrónimo','País','Adultos','Niños','Origen','Entrada','Salida','Noches'
          ,'Comisión de intermediación','Total','Extras','Gastos de gestión','Gastos de limpieza',
          'Comisión al propietario','Estancia','Establecimiento','Propietario','Tarifa','ESTADO',
         'FECHA CANCELACION']]

    data = clean(data,directas=False)
    
    data['antelacion'] = round((data['Entrada'] - data['Fecha de reserva']) / np.timedelta64(1,'D')) + 1

    return data

df = read_data()


#CANTIDAD DE RESERVAS POR DÍAS

st.header('Cantidad de Reservas por días')

dias = st.slider('Qué cantidad de días?',7,30)

df_activas = df[df['ESTADO'] == 'ACTIVA']
df_activas = df_activas.groupby(df_activas['Fecha de reserva'])['Acrónimo'].count().tail(dias)

df_anuladas = df[df['ESTADO'] == 'ANULADA']
df_anuladas = df_anuladas.groupby(df_anuladas['Fecha de reserva'])['Acrónimo'].count().tail(dias)

df_aa = pd.merge(df_activas.to_frame(), df_anuladas.to_frame(), how='left',on='Fecha de reserva')
df_aa = df_aa.fillna(0)

fig = go.Figure()
fig.add_traces(go.Bar(name='Activas',x=df_aa.index,y=df_aa.Acrónimo_x,marker_color='green'))
fig.add_traces(go.Bar(name='Anuladas',x=df_aa.index,y=df_aa.Acrónimo_y,marker_color='red'))

custom_data = [[activas + anuladas,
                round(anuladas / (activas+anuladas) * 100,2),
                activas,
                anuladas] 
                
                for activas, anuladas 
                
                in zip(df_aa.Acrónimo_x, df_aa.Acrónimo_y)]

fig.update_traces(hovertemplate='Total: %{customdata[0]}<br>' +
                                 '% Anuladas: %{customdata[1]}<br>' +
                                 'Activas: %{customdata[2]}<br>' +
                                 'Anuladas: %{customdata[3]}<extra></extra>')



fig.update_layout(barmode='stack')
fig.update_traces(customdata=custom_data)

st.write(fig)

#ANTELACION DE LAS RESERVAS
st.header('Distribución antelación de reservas activas en días')

desde = st.date_input("Desde cuando?")
hasta = st.date_input("Hasta cuando?")

mask = (df['Fecha de reserva'] >= desde) & (df['Fecha de reserva'] <= hasta) & (df['ESTADO'] == 'ACTIVA')
df_antelacion = round(df.loc[mask].groupby(df['Fecha de reserva'])['antelacion'].mean())
df_antelacion = df_antelacion.to_frame()

fig = go.Figure(data=[go.Histogram(x=df.loc[mask]['antelacion'],nbinsx=20)])

fig.update_layout(xaxis=dict(title='Días'), yaxis=dict(title='Cantidad de reservas',range=[0, 15]), 
                  bargap=0.05, bargroupgap=0.2)

st.write(fig)

#PAISES
st.header('Distribución de países por fecha de reserva')

df_agg_paises = df.loc[mask].groupby(df['País']).count()['Reserva'].to_frame()
df_agg_paises = df_agg_paises.reset_index()
df_agg_paises = df_agg_paises.sort_values('Reserva',ascending=True).tail(10)


fig = go.Figure()
fig.add_trace(go.Bar(name='País',y=df_agg_paises['País'],x=df_agg_paises['Reserva'],marker_color='green',orientation='h',hovertemplate='%{x} reservas'))

st.write(fig)







