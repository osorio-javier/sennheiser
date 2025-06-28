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
    Esta versión es robusta contra espacios en blanco en los encabezados
    y diferentes delimitadores (coma o punto y coma).
    """
    if not uploaded_files:
        return pd.DataFrame()

    all_data = []
    required_cols = ['Keyword', 'price', 'URL', 'date']

    for file in uploaded_files:
        try:
            # Leer el archivo en memoria para poder reutilizarlo
            file_content = file.getvalue()
            
            # Intentar con coma como delimitador
            df = pd.read_csv(io.BytesIO(file_content), sep=',', skipinitialspace=True)
            
            # Si solo hay una columna, el delimitador probablemente es incorrecto. Intentar con punto y coma.
            if len(df.columns) == 1:
                df = pd.read_csv(io.BytesIO(file_content), sep=';', skipinitialspace=True)

            # --- CORRECCIÓN CLAVE: Limpiar nombres de columnas ---
            # Elimina cualquier espacio en blanco al principio o al final de los nombres de las columnas.
            df.columns = df.columns.str.strip()

            # Verificar si todas las columnas necesarias existen DESPUÉS de limpiarlas.
            if not all(col in df.columns for col in required_cols):
                st.warning(f"El archivo {file.name} no contiene todas las columnas requeridas ({', '.join(required_cols)}). Se omitirá.")
                continue

            # --- 1. Extracción del Dominio desde la URL ---
            df['dominio'] = df['URL'].apply(lambda url: urlparse(str(url)).netloc.replace('www.', ''))
            
            # --- 2. Procesamiento de la Fecha ---
            df['fecha'] = pd.to_datetime(df['date'], format='%d%m%y', errors='coerce')

            # --- 3. Renombrar 'Keyword' a 'producto' para claridad ---
            df.rename(columns={'Keyword': 'producto'}, inplace=True)
            
            all_data.append(df)
        except Exception as e:
            st.error(f"Ocurrió un error crítico al procesar el archivo {file.name}: {e}")
            continue

    if not all_data:
        return pd.DataFrame()

    full_df = pd.concat(all_data, ignore_index=True)

    # --- Limpieza de Datos ---
    full_df.dropna(subset=['fecha', 'dominio'], inplace=True)

    price_series = full_df['price'].astype(str)
    price_series = price_series.str.replace(r'[$.]', '', regex=True).str.replace(',', '.', regex=False).str.strip()
    full_df['price'] = pd.to_numeric(price_series, errors='coerce')
    
    full_df.dropna(subset=['price'], inplace=True)
    
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
        st.error("No se pudieron cargar datos válidos de los archivos subidos. Revisa su contenido y formato.")
        st.stop()

    st.success(f"{len(df)} registros cargados de {len(uploaded_files)} archivos.")

    # --- Filtros dinámicos basados en los datos cargados ---
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

# --- Filtrado del DataFrame Principal ---
if len(selected_date_range) == 2:
    start_date, end_date = selected_date_range
    mask_date = (df['fecha'].dt.date >= start_date) & (df['fecha'].dt.date <= end_date)
    
    filtered_df = df[
        mask_date &
        (df['producto'].isin(selected_products)) &
        (df['dominio'].isin(selected_domains))
    ]
    if 'price_level' in filtered_df.columns and selected_price_levels:
        # Asegurarse de que el filtro de price_level no falle si el usuario no selecciona nada
        if selected_price_levels:
            filtered_df = filtered_df[filtered_df['price_level'].isin(selected_price_levels)]
else:
    filtered_df = pd.DataFrame()

# --- Panel Principal de Visualizaciones ---
st.header("📊 Visualización de Datos")

if filtered_df.empty:
    st.warning("No hay datos para mostrar con los filtros seleccionados.")
else:
    st.subheader("1. Evolución de Precios por Producto")
    # Para evitar errores, solo hacer facet_row si hay más de un producto
    if len(filtered_df['producto'].unique()) > 1:
        fig_evolucion = px.line(
            filtered_df, x='fecha', y='price', color='dominio',
            facet_row='producto', markers=True, title="Evolución de Precios a lo Largo del Tiempo"
        )
        fig_evolucion.update_layout(height=300 * len(filtered_df['producto'].unique()))
    else:
         fig_evolucion = px.line(
            filtered_df, x='fecha', y='price', color='dominio',
            markers=True, title="Evolución de Precios a lo Largo del Tiempo"
        )
    fig_evolucion.update_yaxes(matches=None, title="Precio (AR$)")
    st.plotly_chart(fig_evolucion, use_container_width=True)

    st.subheader("2. Ranking de Competidores con Precios Bajos")
    lowest_price_counts = filtered_df[filtered_df['es_precio_mas_bajo']]['dominio'].value_counts().reset_index()
    lowest_price_counts.columns = ['dominio', 'cantidad_precios_bajos']
    fig_ranking = px.bar(
        lowest_price_counts, x='dominio', y='cantidad_precios_bajos', color='dominio',
        title="Frecuencia con la que un Competidor Ofrece el Precio Más Bajo",
        labels={'dominio':'Competidor', 'cantidad_precios_bajos':'Nº de Veces con Precio Más Bajo'}
    )
    st.plotly_chart(fig_ranking, use_container_width=True)

    st.subheader("3. Comparativa de Precios en un Día Específico")
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
                labels={'dominio':'Competidor', 'price':'Precio (AR$)'}, text='price'
            )
            fig_snapshot.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
            st.plotly_chart(fig_snapshot, use_container_width=True)
        else:
            st.info(f"No hay datos para '{selected_product_for_bar}' en la fecha seleccionada.")
    
    with st.expander("Ver tabla de datos filtrados"):
        cols_to_display = ['fecha', 'producto', 'price', 'dominio', 'price_level', 'title', 'position', 'URL']
        display_cols = [col for col in cols_to_display if col in filtered_df.columns]
        st.dataframe(filtered_df[display_cols].style.format({'price': "AR$ {:,.2f}", 'fecha': '{:%Y-%m-%d}'}))

