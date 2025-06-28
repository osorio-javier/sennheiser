import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

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
    Esta función está adaptada a la estructura de tus archivos.
    """
    if not uploaded_files:
        return pd.DataFrame()

    all_data = []
    for file in uploaded_files:
        try:
            df = pd.read_csv(file)
            
            # --- CORRECCIÓN MEJORADA: Manejar 'Fecha', 'fecha', 'Date', 'date' ---
            # Itera sobre una lista de posibles nombres para la columna de fecha.
            date_col = None
            possible_date_cols = ['Fecha', 'fecha', 'Date', 'date']
            for col in possible_date_cols:
                if col in df.columns:
                    date_col = col
                    break # Se encontró la columna, se detiene la búsqueda.
            
            if not date_col:
                # Si no se encuentra ninguna columna de fecha, se salta este archivo.
                st.warning(f"El archivo {file.name} no contiene una columna de fecha válida (se buscó: {', '.join(possible_date_cols)}).")
                continue

            # --- Procesamiento de Fecha ---
            df['fecha_procesada'] = pd.to_datetime(df[date_col], format='%d%m%y', errors='coerce')
            all_data.append(df)
        except Exception as e:
            st.warning(f"No se pudo procesar el archivo {file.name}: {e}")
            continue

    if not all_data:
        return pd.DataFrame()

    full_df = pd.concat(all_data, ignore_index=True)
    full_df.rename(columns={'fecha_procesada': 'fecha'}, inplace=True)

    # --- Limpieza de Datos ---
    full_df.dropna(subset=['fecha'], inplace=True)

    if 'precio' in full_df.columns:
        price_series = full_df['precio'].astype(str)
        price_series = price_series.str.replace(r'[$.]', '', regex=True).str.replace(',', '.', regex=False)
        full_df['precio'] = pd.to_numeric(price_series, errors='coerce')

    if 'dominio' in full_df.columns:
         full_df['dominio'] = full_df['dominio'].astype(str).str.strip()

    full_df.dropna(subset=['precio'], inplace=True)
    
    # --- Cálculo de Precios Mínimos ---
    full_df['precio_minimo'] = full_df.groupby(['fecha', 'producto'])['precio'].transform('min')
    full_df['es_precio_mas_bajo'] = full_df['precio'] == full_df['precio_minimo']

    return full_df


# --- Título y Descripción de la App ---
st.title("📈 Herramienta Interactiva de Análisis de Precios")
st.markdown("""
Sube los archivos CSV de tus relevos de precios para visualizar y analizar las tendencias del mercado.
Esta herramienta te permitirá:
- Rastrear la evolución de tus precios y los de la competencia.
- Identificar qué competidores tienen las estrategias de precios más agresivas.
- Filtrar los datos por producto, competidor, rango de fechas y nivel de precio.
""")

# --- Barra Lateral (Sidebar) para Controles y Filtros ---
with st.sidebar:
    st.header("⚙️ Filtros y Controles")
    uploaded_files = st.file_uploader(
        "1. Carga tus archivos CSV",
        type=['csv'],
        accept_multiple_files=True,
        help="Puedes seleccionar múltiples archivos de relevo. La app los combinará automáticamente."
    )

    if not uploaded_files:
        st.info("Por favor, sube al menos un archivo CSV para comenzar el análisis.")
        st.stop()

    df = load_and_process_data(uploaded_files)

    if df.empty:
        st.error("No se pudieron cargar datos válidos de los archivos. Revisa el formato de los CSV y asegúrate de que contengan una columna de fecha.")
        st.stop()

    st.success(f"{len(df)} registros cargados de {len(uploaded_files)} archivos.")

    # --- Filtros Dinámicos ---
    min_date = df['fecha'].min().date()
    max_date = df['fecha'].max().date()
    
    selected_date_range = st.date_input(
        "2. Selecciona un Rango de Fechas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        help="Selecciona el período que quieres analizar."
    )

    all_products = sorted(df['producto'].unique())
    selected_products = st.multiselect(
        "3. Selecciona Productos",
        options=all_products,
        default=all_products
    )

    all_domains = sorted(df['dominio'].unique())
    selected_domains = st.multiselect(
        "4. Selecciona Competidores",
        options=all_domains,
        default=all_domains
    )
    
    # Usamos try-except por si la columna no existe en todos los archivos
    try:
        all_price_levels = sorted(df['price_level'].dropna().unique())
        selected_price_levels = st.multiselect(
            "5. Filtra por Nivel de Precio",
            options=all_price_levels,
            default=all_price_levels,
        )
    except KeyError:
        # No mostramos advertencia si no existe, simplemente no se muestra el filtro.
        selected_price_levels = []


# --- Filtrado del DataFrame Principal ---
if len(selected_date_range) == 2:
    start_date, end_date = selected_date_range
    filtered_df = df[
        (df['fecha'].dt.date >= start_date) &
        (df['fecha'].dt.date <= end_date) &
        (df['producto'].isin(selected_products)) &
        (df['dominio'].isin(selected_domains))
    ]
    # Aplicar filtro de price_level solo si la columna y selección existen
    if 'price_level' in filtered_df.columns and selected_price_levels:
        filtered_df = filtered_df[filtered_df['price_level'].isin(selected_price_levels)]

else:
    filtered_df = pd.DataFrame() # DataFrame vacío si el rango no es válido


# --- Panel Principal de Visualizaciones ---
st.header("📊 Visualización de Datos")

if filtered_df.empty:
    st.warning("No hay datos para mostrar con los filtros seleccionados. Por favor, ajusta los filtros.")
else:
    # --- Gráfico 1: Evolución de Precios ---
    st.subheader("1. Evolución de Precios por Producto")
    
    if len(selected_products) > 1:
        fig_evolucion = px.line(
            filtered_df, x='fecha', y='precio', color='dominio',
            facet_row='producto', markers=True, title="Evolución de Precios a lo Largo del Tiempo (por Producto)"
        )
        fig_evolucion.update_layout(height=300 * len(selected_products))
        fig_evolucion.update_yaxes(matches=None, title="Precio (AR$)")
    else:
        fig_evolucion = px.line(
            filtered_df, x='fecha', y='precio', color='dominio', markers=True,
            title=f"Evolución de Precios para: {selected_products[0]}" if selected_products else "Evolución de Precios"
        )
        fig_evolucion.update_yaxes(title="Precio (AR$)")

    st.plotly_chart(fig_evolucion, use_container_width=True)

    # --- Gráfico 2: Ranking de Competidores ---
    st.subheader("2. Ranking de Competidores con Precios Bajos")
    
    lowest_price_counts = filtered_df[filtered_df['es_precio_mas_bajo']]['dominio'].value_counts().reset_index()
    lowest_price_counts.columns = ['dominio', 'cantidad_precios_bajos']

    fig_ranking = px.bar(
        lowest_price_counts, x='dominio', y='cantidad_precios_bajos', color='dominio',
        title="Frecuencia con la que un Competidor Ofrece el Precio Más Bajo",
        labels={'dominio':'Competidor', 'cantidad_precios_bajos':'Nº de Veces con Precio Más Bajo'}
    )
    st.plotly_chart(fig_ranking, use_container_width=True)

    # --- Gráfico 3: Comparativa en un Día Específico ---
    st.subheader("3. Comparativa de Precios en un Día Específico")

    col1, col2 = st.columns(2)
    with col1:
        available_dates = sorted(filtered_df['fecha'].dt.date.unique(), reverse=True)
        if available_dates:
            selected_date_for_bar = st.selectbox("Selecciona una Fecha", available_dates)
        else:
            selected_date_for_bar = None
    with col2:
        available_products = sorted(filtered_df['producto'].unique())
        if available_products:
            selected_product_for_bar = st.selectbox("Selecciona un Producto", available_products, key='product_select_snapshot')
        else:
            selected_product_for_bar = None
    
    if selected_date_for_bar and selected_product_for_bar:
        snapshot_df = filtered_df[
            (filtered_df['fecha'].dt.date == selected_date_for_bar) &
            (filtered_df['producto'] == selected_product_for_bar)
        ].sort_values('precio')

        if not snapshot_df.empty:
            fig_snapshot = px.bar(
                snapshot_df, x='dominio', y='precio', color='dominio',
                title=f"Precios para '{selected_product_for_bar}' el {selected_date_for_bar}",
                labels={'dominio':'Competidor', 'precio':'Precio (AR$)'}, text='precio'
            )
            fig_snapshot.update_traces(texttemplate='$%{text:,.0f}', textposition='outside')
            st.plotly_chart(fig_snapshot, use_container_width=True)
        else:
            st.info(f"No hay datos para '{selected_product_for_bar}' en la fecha seleccionada.")
    
    # --- Expander para ver los datos crudos ---
    with st.expander("Ver tabla de datos filtrados"):
        # Preparamos las columnas a eliminar para evitar errores si no existen
        cols_to_drop = [col for col in ['precio_minimo', 'es_precio_mas_bajo', 'Fecha', 'fecha', 'Date', 'date'] if col in filtered_df.columns]
        display_df = filtered_df.drop(columns=cols_to_drop)
        st.dataframe(display_df.style.format({'precio': "AR$ {:,.2f}", 'fecha': '{:%Y-%m-%d}'}))
