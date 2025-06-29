import streamlit as st
import pandas as pd
import plotly.express as px
from urllib.parse import urlparse
import io

# --- Configuración de la Página de Streamlit ---
st.set_page_config(
    layout="wide",
    page_title="Análisis de Precios SERP",
    page_icon="📈"
)

# --- Funciones de Procesamiento de Datos ---

@st.cache_data # Cache para mejorar el rendimiento.
def load_and_process_data(uploaded_files):
    """
    Carga, une y limpia los datos de los archivos CSV subidos.
    Versión final adaptada al formato de fecha DD-MM-YY.
    """
    if not uploaded_files:
        return pd.DataFrame()

    all_data = []
    required_cols = ['Keyword', 'price', 'URL', 'date']

    for file in uploaded_files:
        try:
            # Leer el archivo con el delimitador correcto y limpiar encabezados
            file_content = file.getvalue()
            df = pd.read_csv(io.BytesIO(file_content), sep=',', skipinitialspace=True)
            df.columns = df.columns.str.strip()

            # Verificar si las columnas necesarias existen
            if not all(col in df.columns for col in required_cols):
                st.warning(f"El archivo {file.name} no contiene todas las columnas requeridas ({', '.join(required_cols)}). Se omitirá.")
                continue

            # --- Formato de fecha con guiones ---
            df['fecha'] = pd.to_datetime(df['date'], format='%d-%m-%y', errors='coerce')

            # --- Procesamiento del resto de los datos ---
            df['dominio'] = df['URL'].apply(lambda url: urlparse(str(url)).netloc.replace('www.', ''))
            df.rename(columns={'Keyword': 'producto'}, inplace=True)
            
            all_data.append(df)
        except Exception as e:
            st.error(f"Ocurrió un error crítico al procesar el archivo {file.name}: {e}")
            continue

    if not all_data:
        return pd.DataFrame()

    full_df = pd.concat(all_data, ignore_index=True)

    # --- Limpieza y Transformación de Datos ---
    full_df.dropna(subset=['fecha'], inplace=True)
    if full_df.empty:
        st.error("Error en el formato de fecha. Asegúrate que las fechas tengan el formato DD-MM-YY.")
        return pd.DataFrame()

    # Limpieza de la columna 'price'
    price_series = full_df['price'].astype(str)
    price_series = price_series.str.replace(r'[^\d,.]', '', regex=True).str.replace(',', '', regex=True)
    full_df['price'] = pd.to_numeric(price_series, errors='coerce')
    full_df.dropna(subset=['price'], inplace=True)

    # --- Conversión de 'price_level' a valor numérico ---
    if 'price_level' in full_df.columns:
        level_map = {'bajo': 1, 'medio': 2, 'alto': 3}
        full_df['price_level_numeric'] = full_df['price_level'].str.lower().map(level_map)
    
    # --- Cálculo de Precios Mínimos ---
    full_df['precio_minimo'] = full_df.groupby(['fecha', 'producto'])['price'].transform('min')
    full_df['es_precio_mas_bajo'] = full_df['price'] == full_df['precio_minimo']

    return full_df


# --- Interfaz de Usuario de Streamlit ---

st.title("📈 Herramienta Interactiva de Análisis de Precios")
st.markdown("Sube los archivos CSV de tus relevos de precios para analizar la evolución del mercado.")

with st.sidebar:
    st.header("⚙️ Filtros y Controles")
    uploaded_files = st.file_uploader(
        "1. Carga tus archivos CSV",
        type=['csv'],
        accept_multiple_files=True
    )

    if not uploaded_files:
        st.info("Por favor, sube al menos un archivo CSV para comenzar.")
        st.stop()

    df = load_and_process_data(uploaded_files)

    if df.empty:
        st.warning("No se pudieron cargar datos válidos. Revisa el mensaje de error de arriba.")
        st.stop()

    st.success(f"{len(df)} registros cargados de {len(uploaded_files)} archivos.")

    min_date = df['fecha'].min().date()
    max_date = df['fecha'].max().date()
    
    selected_date_range = st.date_input(
        "2. Selecciona Rango de Fechas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    all_products = sorted(df['producto'].unique())
    selected_products = st.multiselect("3. Selecciona Productos (Keywords)", options=all_products, default=all_products)

    all_domains = sorted(df['dominio'].unique())
    selected_domains = st.multiselect("4. Selecciona Competidores", options=all_domains, default=all_domains)
    
    if 'price_level' in df.columns:
        all_price_levels = sorted(df['price_level'].dropna().unique())
        selected_price_levels = st.multiselect("5. Filtra por Nivel de Precio", options=all_price_levels, default=all_price_levels)
    else:
        selected_price_levels = []

# --- Filtrado del DataFrame ---
if len(selected_date_range) == 2:
    start_date, end_date = selected_date_range
    mask_date = (df['fecha'].dt.date >= start_date) & (df['fecha'].dt.date <= end_date)
    
    filtered_df = df[
        mask_date &
        (df['producto'].isin(selected_products)) &
        (df['dominio'].isin(selected_domains))
    ]
    if 'price_level' in filtered_df.columns and selected_price_levels:
        if selected_price_levels:
            filtered_df = filtered_df[filtered_df['price_level'].isin(selected_price_levels)]
else:
    filtered_df = pd.DataFrame()

# --- Panel Principal de Visualizaciones ---
st.header("📊 Visualización de Datos")

if filtered_df.empty:
    st.warning("No hay datos para mostrar con los filtros seleccionados.")
else:
    # --- Gráfico único con selector de producto ---
    st.subheader("1. Evolución de Precios por Producto")
    
    product_options = sorted(filtered_df['producto'].unique())
    if product_options:
        selected_product_for_line_chart = st.selectbox(
            "Selecciona un producto para ver su evolución de precios:",
            options=product_options
        )

        # Filtrar el dataframe para el producto seleccionado
        line_chart_df = filtered_df[filtered_df['producto'] == selected_product_for_line_chart]

        # Crear el gráfico de línea único
        fig_evolucion = px.line(
            line_chart_df,
            x='fecha',
            y='price',
            color='dominio',
            markers=True,
            title=f"Evolución de Precios para: {selected_product_for_line_chart}"
        )
        fig_evolucion.update_yaxes(matches=None, title="Precio")
        st.plotly_chart(fig_evolucion, use_container_width=True)
    else:
        st.info("No hay productos disponibles en el DataFrame filtrado para mostrar este gráfico.")

    
    # --- Gráfico de Evolución de Nivel de Precio ---
    st.subheader("2. Evolución de Nivel de Precio por Competidor")
    if 'price_level_numeric' in filtered_df.columns:
        price_level_evolution = filtered_df.groupby(['fecha', 'dominio'])['price_level_numeric'].mean().reset_index()

        fig_level = px.line(
            price_level_evolution,
            x='fecha',
            y='price_level_numeric',
            color='dominio',
            markers=True,
            title="Estrategia de Posicionamiento de Precios en el Tiempo"
        )
        
        fig_level.update_yaxes(
            title="Nivel de Precio Promedio",
            tickvals=[1, 2, 3],
            ticktext=['Bajo', 'Medio', 'Alto']
        )
        st.plotly_chart(fig_level, use_container_width=True)
    else:
        st.info("La columna 'price_level' no se encontró en los datos para generar este gráfico.")


    # --- CAMBIO: Gráfico de ranking dinámico por price_level ---
    st.subheader("3. Ranking de Competidores por Rango de Precio")
    if 'price_level' in filtered_df.columns:
        # Crear opciones para el selector, incluyendo 'Todos'
        level_options = ['Todos'] + sorted(filtered_df['price_level'].dropna().unique())
        
        selected_level_for_ranking = st.selectbox(
            "Selecciona un rango de precio para el ranking:",
            options=level_options
        )

        # Filtrar datos según la selección
        ranking_df = filtered_df
        if selected_level_for_ranking != 'Todos':
            ranking_df = filtered_df[filtered_df['price_level'] == selected_level_for_ranking]

        # Calcular la frecuencia de aparición
        ranking_counts = ranking_df['dominio'].value_counts().reset_index()
        ranking_counts.columns = ['dominio', 'frecuencia']

        # Crear el gráfico de barras
        fig_ranking = px.bar(
            ranking_counts, 
            x='dominio', 
            y='frecuencia', 
            color='dominio',
            title=f"Frecuencia de Aparición en Rango de Precio: '{selected_level_for_ranking.title()}'",
            labels={'dominio':'Competidor', 'frecuencia':'Número de Apariciones'}
        )
        st.plotly_chart(fig_ranking, use_container_width=True)

    else:
        st.info("La columna 'price_level' no se encontró, no se puede generar el ranking por rango.")


    st.subheader("4. Comparativa de Precios en un Día Específico")
    col1, col2 = st.columns(2)
    with col1:
        available_dates = sorted(filtered_df['fecha'].dt.date.unique(), reverse=True)
        selected_date_for_bar = st.selectbox("Selecciona una Fecha", available_dates) if available_dates else None
    with col2:
        available_products = sorted(filtered_df['producto'].unique())
        selected_product_for_bar = st.selectbox("Selecciona un Producto", available_products, key='product_select_snapshot') if available_products else None
    
    if selected_date_for_bar and selected_product_for_bar:
        snapshot_df = filtered_df[
            (filtered_df['fecha'].dt.date == selected_date_for_bar) &
            (filtered_df['producto'] == selected_product_for_bar)
        ].sort_values('price')
        if not snapshot_df.empty:
            fig_snapshot = px.bar(
                snapshot_df, x='dominio', y='price', color='dominio',
                title=f"Precios para '{selected_product_for_bar}' el {selected_date_for_bar}",
                labels={'dominio':'Competidor', 'price':'Precio'}, text='price'
            )
            fig_snapshot.update_traces(texttemplate='%{text}', textposition='outside')
            st.plotly_chart(fig_snapshot, use_container_width=True)
        else:
            st.info(f"No hay datos para '{selected_product_for_bar}' en la fecha seleccionada.")
    
    with st.expander("Ver tabla de datos filtrados"):
        cols_to_display = ['fecha', 'producto', 'price', 'dominio', 'price_level', 'title', 'position', 'URL']
        display_cols = [col for col in cols_to_display if col in filtered_df.columns]
        st.dataframe(filtered_df[display_cols].style.format({'fecha': '{:%Y-%m-%d}'}))
