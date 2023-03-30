import pandas as pd

def clean(df, directas = True):

    if directas == True:
        origenes = ['idealista','NO VACACIONAL','CUNA', 'PRUEBA','Parking','Propietario','LETMALAGA','DIRECTAS']
    else:
        origenes = ['idealista','NO VACACIONAL','CUNA', 'PRUEBA','Parking','Propietario','LETMALAGA']

    df = df.drop_duplicates(subset='Reserva', keep="first")
    
    df = df[(~df['Acrónimo'].str.contains('Provisional')) & 
            (~df['Acrónimo'].str.contains('Park')) & 
            (df['Acrónimo'] != 'Puerto_7_5-209') & 
            (df['Acrónimo'] != 'Puerto_7_5-210')]
    
    df = df[~df['Origen'].isin(origenes)]

    df['Entrada'] = pd.to_datetime(df['Entrada']).dt.date
    df['Salida'] = pd.to_datetime(df['Salida']).dt.date
    df['Fecha de reserva'] = pd.to_datetime(df['Fecha de reserva']).dt.date

    return df
