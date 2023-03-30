import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from dataclean import clean
from procesa_datos import procesa_data, read_pisos, ocupacion, revpar

st.header('Estimador de adr próximo año')

#Lee los pisos de la base
df_pisos = read_pisos()

#Obtiene las categorías, zonas y habitaciones únicas del df_pisos
categorias_unicas = df_pisos['categoria'].unique()
zonas_unicas = df_pisos['zona'].unique()
hab_unicas = list(df_pisos['hab'].unique())
hab_unicas.sort()


#Procesa la fecha ingresada por el usuario
def parse_date(date_string):
    try:
        return datetime.strptime(date_string, '%m/%Y')
    except ValueError:
        return None

date_string = st.text_input("Ingrese el período mensual a evaluar (MM/YYYY):")

date_string = parse_date(date_string)

if date_string is not None:
    control = True
else:
    control = False
    st.write("El formato ingresado es inválido. Por favor ingrese un período con le formado MM/YYYY.")


#Crea los selectboxes en función a las categorías, habitaciones y zonas únicas anteriormente procesadas
categoria = st.selectbox('Seleccione la categoría',options=categorias_unicas)
hab = st.selectbox('Seleccione la cantidad de habitaciones',options=hab_unicas)
zona = st.selectbox('Seleccione la zona',options=zonas_unicas)
boton_descarga = st.button('Descargar xlsx')
boton = st.button('Run!')

#Lee la información de reservas y limpia la data dejando solo la relevante
@st.cache
def read_data_reservas():
    df = pd.read_excel('./data/reservas.xlsx',sheet_name='RESERVAS')

    df = clean(df)

    return df

#BOTON DESCARGA
try:
    if boton_descarga and control:
        df = read_data_reservas()

        df_descarga, adr_maximo = procesa_data(df,categoria,hab,zona,date_string)

        path = './descargas/Data_' + categoria + '_hab_' + str(hab) + '_' + zona + '.xlsx'

        df_descarga.to_excel(path,index=False)
        st.success('Data descargada exitosamente!', icon="✅")

    elif boton_descarga and control == False:
        st.warning('Error en la descarga. Revisar el formato de la fecha.', icon="⚠️")

except Exception:
    st.warning('Error en la descarga.', icon="⚠️")


def grafico_adr(df_filtrado, adr_maximo):
    
    color_map = lambda val: 'blue' if val == 0 else 'red'
    colors = df_filtrado['estimado'].apply(color_map)

    df_tooltip = df_filtrado.copy()

    df_tooltip['adr'] = df_tooltip['adr'].round(decimals=2)
    
    def cambia_valores_estimado(s):    
        if s['estimado'] == 0.0:
            s['estimado'] = 'No'
            return s['estimado']
        else:
            s['estimado'] = 'Si'
            return s['estimado']
   
    df_tooltip['estimado'] = df_tooltip.apply(cambia_valores_estimado, axis=1)

    custom_data = df_tooltip[['fecha','adr','estimado']].values.tolist()

    trace = go.Scatter(
        x=df_filtrado.fecha, 
        y=df_filtrado.adr, 
        mode='markers+lines', 
        marker={'color': colors}, 
        line={'color': 'gray'}
    )

    fig = go.Figure(data=trace)
    
    fig.update_traces(hovertemplate = 'Fecha: %{x}<br>' + 
                    'ADR: €%{customdata[1]}<br>' + 
                    'Estimado: %{customdata[2]}')
    
    fig.update_traces(customdata = custom_data)
    fig.update_yaxes(range = [0, adr_maximo])
    fig.update_layout(title = categoria + ' ' + zona + ' ' + 'Habitaciones: ' + str(hab))

    st.write(fig)


def grafico_ocupacion(df_ocupacion):

    st.header('OCUPACIÓN')

    fig = go.Figure()
    fig.add_traces(go.Bar(x=df_ocupacion['fecha'],
                          y=df_ocupacion['ocupacion']))

    fig.update_traces(hovertemplate='Fecha: %{x}<br>' +
                                    'Ocupacion: %{y}%<br>')

    st.write(fig)


def grafico_revpar(df_adr, df_ocupacion):

    st.header('REVPAR')

    df_revpar = revpar(df_adr, df_ocupacion)


    fig = go.Figure()
    fig.add_traces(go.Bar(x=df_revpar['fecha'],
                          y=df_revpar['revpar']))

    fig.update_traces(hovertemplate='Fecha: %{x}<br>' +
                                    'Revpar: €%{y}<br>')

    st.write(fig)


#BOTON RUN
if boton and control:

    df = read_data_reservas()
    df_filtrado, adr_maximo = procesa_data(df, categoria, hab, zona, date_string)
    grafico_adr(df_filtrado, adr_maximo)

    df_ocupacion = ocupacion(categoria, hab, zona, date_string)
    grafico_ocupacion(df_ocupacion)

    grafico_revpar(df_filtrado, df_ocupacion)


elif boton and control == False:

        st.warning('Error en el procesamiento. Revisar el formato de la fecha.', icon="⚠️")




