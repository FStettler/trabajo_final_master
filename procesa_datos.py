import streamlit as st
import calendar
import pandas as pd
import numpy as np
from datetime import datetime, date
from sklearn.impute import KNNImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import make_column_transformer
from dataclean import clean



@st.cache
def read_pisos():
    df_pisos = pd.read_excel('./data/pisos.xlsx',sheet_name='Hoja1',parse_dates=True)

    df_pisos['apertura'] = df_pisos['apertura'].dt.date
    df_pisos['cierre'] = df_pisos['cierre'].dt.date

    return df_pisos



@st.cache
def procesa_data(df, categoria, hab, zona, date_string):
    #PREPROCESAMIENTO -------------------------------------------------------------------------------------------

    df_pisos = read_pisos()


    #En función a la fecha ingresada por el usuario, calcula el mes, año y último día del mes
    try:
        mes = date_string.month
        año = date_string.year
        fin_de_mes = calendar.monthrange(año,mes)[1]
    except Exception:
        return None,None

    #Selecciona las reservas que que al menos tienen un día dentro del período ingresado por el usuario
    df_analisis = df[(df['Entrada']<= date(año,mes,fin_de_mes)) & (df['Salida']>= date(año,mes,1))]

    #Selecciona solamente reservas activas
    df_analisis = df_analisis[df_analisis['ESTADO'] == 'ACTIVA']

    #Selecciona solamente columnas relevantes
    df_analisis = df_analisis[['Reserva','Acrónimo','País','Adultos','Niños','Origen','Entrada','Salida','Noches',
                            'Estancia','Establecimiento','Tarifa']]

    df_analisis.rename(columns={"Establecimiento": "id"},inplace=True)

    #Crea la columna PAX en función a la columna tarifa: toma solo el número (integer) de PAX
    df_analisis['PAX'] = df_analisis['Tarifa'].str[:2].astype('int')
    
    #Crea la columna NR en función a la columna tarifa: toma si existe la palabra "NR" en el campo tarifa o no
    df_analisis['NR'] = df_analisis['Tarifa'].str[2:]
    df_analisis['NR'] = df_analisis['NR'].str.strip()
    df_analisis.loc[df_analisis["NR"] == "PAX NR", "NR"] = True
    df_analisis.loc[df_analisis["NR"] == "PAX", "NR"] = False
    df_analisis.drop('Tarifa',axis=1,inplace=True)

    #Crea la columna ADR (average daily rate) dividienco el valor de la estancia por el número de noches de la reserva
    df_analisis['ADR'] = df_analisis['Estancia'] / df_analisis['Noches']

    #TRANSFORMACIÓN DE ADR:
    #Cada reserva tiene 
        #1. un descuento de acuerdo a condiciones específicas, por ejemplo: 7 noches + NR ==> 15%
        #2. un incremento de acuerdo a la cantidad de PAX. La tarifa base es la de 2 PAX sin descuentos, sumándole €20 a cada PAX posterior.

    #Quita los descuentos del ADR calculado anteriormente de acuerdo al descuento de cada caso, por ejemplo: 7 noches + NR ==> 15%
    def conditions(s):
        if s['Noches']>=7 and s['NR'] == True:
            return s['ADR']/0.85
        elif s['Noches']>=4 and s['NR'] == True:
            return s['ADR']/0.87
        elif s['Noches']>=7 and s['NR'] == False:
            return s['ADR']/0.95
        elif s['Noches']>=4 and s['NR'] == True:
            return s['ADR']/0.97
        elif s['NR'] == True:
            return s['ADR']/0.90
        elif s['NR'] == False:
            return s['ADR']

    #Modifica la columna ADR de acuerdo a la función conditions        
    df_analisis['ADR'] = df_analisis.apply(conditions,axis=1)

    #Quita los €20 de cada PAX adicional para llegar al valor de la 2 PAX base
    def pax(s):
        for i in range(3,17):
            
            if s['PAX'] == 2:
                return s['ADR']
            elif s['PAX'] == i:
                s['ADR'] = s['ADR'] - 20 * (i-2)
                return s['ADR']

    #Modifica la columna ADR de acuerdo a la función pax       
    df_analisis['ADR'] = df_analisis.apply(pax,axis=1)

    #Adiciona la información de categoría, zona y habitaciones a la data de las reservas
    df_analisis = pd.merge(df_analisis,df_pisos[['id','categoria','zona','hab']],how='left',on='id')
    df_analisis['Entrada'] = pd.to_datetime(df_analisis['Entrada'])
    df_analisis['Salida'] = pd.to_datetime(df_analisis['Salida'])

    #Obtiene las combinaciones únicas de categoría, zona y hab registradas en la data de las reservas
    unicos = df_analisis[['categoria','zona','hab']].value_counts().reset_index()
    unicos.drop(0,axis=1,inplace=True)

    #Crea un DataFrame (llamado 'x') con una fila por cada día del mes en análisis, por cada una de las combinaciones únicas calculadas anteriormente
    y = pd.DataFrame(pd.date_range(start=datetime(año,mes,1), end=datetime(año,mes,fin_de_mes)),columns=['Fecha'])
    x = pd.DataFrame()

    for i,r in unicos.iterrows():
        
        z = pd.DataFrame()
        z['fecha'] = y
        z['categoria'] = r['categoria']
        z['zona'] = r['zona']
        z['hab'] = r['hab']
        
        x = pd.concat([x,z])

    x.reset_index(drop=True,inplace=True)
    x['adr'] = 0

    #Calcula la media de ADRs para cada día en el DataFrame x
    for i,r in x.iterrows():
        
        adr = df_analisis[(df_analisis['categoria']==r['categoria'])&(df_analisis['zona']==r['zona'])&(df_analisis['hab']==r['hab'])&(df_analisis['Entrada']<=r['fecha'])&(df_analisis['Salida']>r['fecha'])]['ADR'].mean()
        x['adr'].loc[i] = adr

    x['estimado'] = np.where(x['adr'].isnull() == True, True, False)

    z = x.copy()

    #MACHINE LEARNING -----------------------------------------------------------------------------------

    #Convierte la variable fecha a formato número
    z['fecha'] = pd.to_numeric(z['fecha'])
    
    #Convierte las categorías a enteros. Las categorías son en orde de peor a mejor: Economy, Confort, Superior y Premium. Por eso se le da un valor ordinal entero
    z.loc[z['categoria']=='Economy','categoria'] = 0
    z.loc[z['categoria']=='Confort','categoria'] = 1
    z.loc[z['categoria']=='Superior','categoria'] = 2
    z.loc[z['categoria']=='Premium','categoria'] = 3

    #Convierte las zonas a valores numéricos con OneHotEncoder
    transformer = make_column_transformer((OneHotEncoder(), ['zona']),remainder='passthrough')

    transformed = transformer.fit_transform(z)
    z = pd.DataFrame(transformed,columns=transformer.get_feature_names_out())

    headers = list(z.columns)

    #Se crea un objeto KNNImputer para imputar ADRs a los días de 'x' sin data
    imputer = KNNImputer()
    imputer.fit(z)
    x_imputada = imputer.transform(z)
    x = pd.DataFrame(x_imputada)
    x.columns = headers

    #Se rearma el DataFrame reconvirtiendo las variables categoricas a su valor original
    x['fecha'] = pd.to_datetime(x['remainder__fecha'])
    x.loc[x['remainder__categoria']==0,'categoria'] = 'Economy'
    x.loc[x['remainder__categoria']==1,'categoria'] = 'Confort'
    x.loc[x['remainder__categoria']==2,'categoria'] = 'Superior'
    x.loc[x['remainder__categoria']==3,'categoria'] = 'Premium'
    x.drop(['remainder__categoria','remainder__fecha'],inplace=True,axis=1)
    x.rename(columns={"remainder__adr": "adr",
                      'remainder__hab':'hab',
                      'remainder__estimado':'estimado'},
                      inplace=True)

    cols = list(x.columns.values)
    cols = [s for s in cols if 'onehotencoder' in s]

    encoder = transformer.transformers_[0][1]
    original_categories = pd.DataFrame(
        encoder.inverse_transform(x.loc[:, cols]), 
        columns=['zona'])

    x['zona'] = original_categories
    x.drop(cols,inplace=True,axis=1)

    #Se filtra el DataFrame resultante de acuerdo a los criterios elegidos por el usuario
    df_filtrado = x[(x['categoria']==categoria) & (x['zona']==zona) & (x['hab']==hab)]

    adr_maximo = x['adr'].max()
    
    return df_filtrado, adr_maximo


@st.cache
def ocupacion(categoria, hab, zona, date_string):

    df_pisos = read_pisos()

    try:
        mes = date_string.month
        año = date_string.year
        fin_de_mes = calendar.monthrange(año,mes)[1]
    except Exception:
        return None,None
    
    df_pisos = df_pisos[(df_pisos['apertura']<= date(año,mes,fin_de_mes)) & (df_pisos['cierre']>= date(año,mes,1))]

    y = pd.DataFrame(pd.date_range(start=datetime(año,mes,1), end=datetime(año,mes,fin_de_mes)),columns=['fecha'])
    x = pd.DataFrame()

    for i,r in y.iterrows():

        
        df = df_pisos[
            (df_pisos['apertura'] <= r['fecha']) & 
            (df_pisos['cierre'] > r['fecha'])]
        
        df = df.groupby(['categoria','zona','hab'])['id'].count().reset_index()

        df['fecha'] = r['fecha']
        x = pd.concat([x,df])

    x.reset_index(drop=True,inplace=True)
    x.rename(columns={"id": "rn"},inplace=True)


    df_reservas = pd.read_excel('./data/reservas.xlsx',sheet_name='RESERVAS',parse_dates=True)

    df_reservas = clean(df_reservas, directas= False)


    df_analisis = df_reservas[(df_reservas['Entrada']<= date(año,mes,fin_de_mes)) & (df_reservas['Salida']> date(año,mes,1))]
    df_analisis = df_analisis[df_analisis['ESTADO'] == 'ACTIVA']
    df_analisis = df_analisis[['Reserva','Acrónimo','País','Adultos','Niños','Origen','Entrada','Salida','Noches',
                            'Estancia','Establecimiento','Tarifa']]
    df_analisis.rename(columns={"Establecimiento": "id"},inplace=True)

    df_analisis = pd.merge(df_analisis,df_pisos[['id','categoria','zona','hab']],how='left',on='id')

    z = pd.DataFrame()

    for i,r in y.iterrows():

        
        df = df_analisis[
            (df_analisis['Entrada'] <= r['fecha']) & 
            (df_analisis['Salida'] > r['fecha'])]

        df = df.groupby(['categoria','zona','hab'])['id'].count().reset_index()
        
        
        
        df['fecha'] = r['fecha']
        z = pd.concat([z,df])

    z.reset_index(drop=True,inplace=True)
    z.rename(columns={"id": "rn"},inplace=True)

    df_ocupacion = pd.merge(x,z,how='left',on=['categoria','zona','hab','fecha'])
    df_ocupacion['rn_y'] = df_ocupacion['rn_y'].fillna(0)

    df_ocupacion.rename(columns={
         'rn_x': 'rn_disponibles',
         'rn_y': 'rn_vendidas'
     }, inplace = True)

    df_ocupacion['ocupacion'] = round((df_ocupacion['rn_vendidas'] / df_ocupacion['rn_disponibles']) * 100, 2)

    return df_ocupacion[(df_ocupacion['categoria'] == categoria) & (df_ocupacion['zona'] == zona) & (df_ocupacion['hab'] == hab)]


@st.cache
def revpar(df_adr, df_ocupacion):

    df_ocupacion = df_ocupacion[['ocupacion','fecha']]
    df_adr = df_adr[['adr','fecha']]
    df_revpar = pd.merge(df_adr, df_ocupacion, how='left', on='fecha')
    df_revpar['revpar'] = round((df_revpar['adr'] * df_revpar['ocupacion']) / 100, 2)

    return df_revpar[['revpar','fecha']]




