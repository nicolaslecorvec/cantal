import streamlit as st
import geopandas as gpd
import plotly.express as px
import pandas as pd
import math
from geopy.geocoders import Nominatim

@st.cache(allow_output_mutation=True)
def get_gdf(file_path):
    """Charger les données géospatiales à partir du fichier spécifié."""
    gdf = gpd.read_file(file_path)
    return gdf

def calculate_bounds(gdf):
    """Calculer les limites du geodataframe pour déterminer le centre de la carte et le niveau de zoom."""
    bounds = gdf.total_bounds  # Retourne (minx, miny, maxx, maxy)
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    return center_lat, center_lon

def calculate_zoom_level(gdf):
    """Calculate a zoom level based on the extent of the GeoDataFrame."""
    bounds = gdf.total_bounds
    # Calculate the diagonal of the bounding box
    diagonal = math.sqrt((bounds[2] - bounds[0])**2 + (bounds[3] - bounds[1])**2)
    # This is a heuristic to calculate zoom level based on diagonal length
    # You might need to adjust the multiplier based on your specific dataset
    return max(12 - math.log(diagonal) * 0.5, 1)

def create_interactive_map(gdf, lat, lon, zoom, color_range):
    """Créer une carte interactive avec la plage de couleurs personnalisable."""
    if lat is None or lon is None:
        center_lat, center_lon = calculate_bounds(gdf)
        zoom = calculate_zoom_level(gdf)
    else:
        center_lat, center_lon = lat, lon

    fig = px.scatter_mapbox(gdf.reset_index(),
                            lat="latitude",
                            lon="longitude",
                            color="slope",
                            color_continuous_scale=px.colors.diverging.RdBu,
                            range_color=color_range,  # Updated to use the custom range
                            hover_name=gdf.index,
                            hover_data={"index": True, "slope": True},
                            zoom=zoom,
                            center={"lat": center_lat, "lon": center_lon},
                            height=300)
    fig.update_layout(mapbox_style="open-street-map", margin={"r":0, "t":0, "l":0, "b":0})
    fig.update_traces(marker=dict(size=10))

    return fig

def geocode_address(address):
    """Géocoder l'adresse pour obtenir la latitude et la longitude."""
    geolocator = Nominatim(user_agent="geoapiExercises")
    location = geolocator.geocode(address)
    if location:
        return location.latitude, location.longitude
    else:
        return None, None

@st.cache
def get_time_series_data(selected_index, gdf):
    """Extraire les données de séries temporelles pour le point sélectionné en utilisant son index."""
    date_columns = gdf.columns[11:374]
    dates = pd.to_datetime(date_columns, format='%Y%m%d')
    displacement_values = gdf.iloc[selected_index][date_columns].values

    ts_data = pd.DataFrame({
        'Date': dates,
        'Displacement': displacement_values
    })

    ts_data['Year'] = ts_data['Date'].dt.year
    ts_data['Month'] = ts_data['Date'].dt.month

    return ts_data


def plot_annual_trend(ts_data):
    """Plot the displacement for each year superimposed in the same figure."""

    # Normalize the dates to the same year
    # First, find the earliest year in the data
    earliest_year = ts_data['Date'].dt.year.min()

    # Then adjust all dates to occur within that year
    ts_data['NormalizedDate'] = ts_data.apply(lambda row: row['Date'].replace(year=earliest_year), axis=1)

    # Now plot the data, using the color to distinguish between different years
    fig = px.line(ts_data, x='NormalizedDate', y='Displacement', color='Year',
                  labels={'Displacement': 'Déplacement', 'NormalizedDate': 'Date (normalisée)', 'Year': 'Année'},
                  line_shape='spline', render_mode='svg')  # Spline makes the line smoother

    fig.update_traces(line=dict(width=2))
    fig.update_layout(
        title='Déplacement au cours du temps pour chaque année',
        xaxis=dict(title='Date (normalisée)'),
        yaxis=dict(title='Déplacement (mm)'),
        legend_title='Année'
    )

    # Update xaxis to show only one year and set a custom range if needed
    fig.update_xaxes(
        tickmode='array',
        tickvals=pd.date_range(start=f'{earliest_year}-01-01', periods=12, freq='MS'),
        ticktext=[f'{month}' for month in ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']]
    )

    return fig


def main():
    st.title('Carte du mouvement des sols dans le Cantal')
    st.write("""
        Cette carte permet de visualiser la tendance de mouvements plurianuels grâce aux données InSAR
        de l'European Ground Motion Service (EGMS). Les séries temporelles obtenues via l'EGMS ont subi une régression linéaire
        et la pente est représentée sur la carte pour des p-value inférieures à 0.05 et un
        coefficient de détermination (R²) supérieur à 0.75.
    """)

    # Load the geospatial data
    file_path = 'linregress_results.geojson'
    gdf = get_gdf(file_path)

    # Calculate the maximum slope for the default range
    max_slope = float(gdf['slope'].abs().max())

    # Allow the user to set a custom range for the color scale
    color_range = st.sidebar.slider(
        'Définir la plage de valeurs pour la couleur de la pente:',
        min_value=-max_slope,
        max_value=max_slope,
        value=[-max_slope, max_slope],  # Ensure this is a list of Python floats
        step=max_slope / 20,
        format="%.2f",
        key='color_range'
    )

    # User inputs the address
    address = st.text_input("Entrez une adresse pour zoomer sur la carte", "")

    # Now in your main function, use the calculate_zoom_level function without manually setting zoom to 5
    # if the address is provided:
    if address:
        lat, lon = geocode_address(address)
    else:
        # If no address is provided, calculate the center and zoom to fit all points
        lat, lon = calculate_bounds(gdf)
        zoom = calculate_zoom_level(gdf)

    # Create and display the interactive map with the user-defined color range
    fig = create_interactive_map(gdf, lat, lon, zoom, color_range)
    st.plotly_chart(fig, use_container_width=True)

    selected_index = st.selectbox('Sélectionnez un indice de point', gdf.index.tolist())

    # Initialize session state for ts_data if it does not exist
    if 'ts_data' not in st.session_state:
        st.session_state.ts_data = None

    # Initialize session state for ts_fig if it does not exist
    if 'ts_fig' not in st.session_state:
        st.session_state.ts_fig = None

    # Button to load the time series data
    if st.button('Afficher les séries temporelles', key='show_time_series'):
        st.session_state.ts_data = get_time_series_data(selected_index, gdf)
        st.session_state.ts_fig = px.line(
            x=st.session_state.ts_data['Date'],
            y=st.session_state.ts_data['Displacement'],
            title='Mouvements au cours du temps'
        )
        # Update axis labels
        st.session_state.ts_fig.update_layout(
        xaxis_title='Dates',
        yaxis_title='Déplacement (mm)'
    )
        st.plotly_chart(st.session_state.ts_fig, use_container_width=True)

    # Check if ts_data is available to set up the multiselect widget
    if 'ts_data' in st.session_state and st.session_state.ts_data is not None:
        years_to_plot = st.multiselect(
            'Choisissez les années à afficher',
            options=st.session_state.ts_data['Year'].unique(),  # Get unique years from the loaded data
            default=st.session_state.ts_data['Year'].unique(),  # Set all years as default
            key='years_to_plot'
        )

        # Button to show the annual trend plot
        if st.button('Afficher la tendance annuelle', key='show_annual_trend'):
            # Filter the data based on the years selected
            filtered_data = st.session_state.ts_data[st.session_state.ts_data['Year'].isin(years_to_plot)]
            st.session_state.trend_fig = plot_annual_trend(filtered_data)
            st.plotly_chart(st.session_state.trend_fig, use_container_width=True)

if __name__ == "__main__":
    main()
