import pandas as pd
import numpy as np
import geopandas as gpd
from pyproj import Transformer
from scipy.stats import linregress
from joblib import Parallel, delayed
import os



def load_and_transform_data(file_path, epsg_from='epsg:3035', epsg_to='epsg:4326'):
    # Load the data
    df = pd.read_csv(file_path)

    # Initialize the Transformer
    transformer = Transformer.from_crs(epsg_from, epsg_to, always_xy=True)

    # Transform coordinates without using apply for efficiency
    coords = np.vectorize(transformer.transform)(df['easting'].values, df['northing'].values)
    df['longitude'], df['latitude'] = coords

    # Directly create GeoDataFrame with geometry
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs=epsg_to)

def calculate_differences(row):
    y_values = row[11:374].astype(float).values
    x_values = np.arange(len(y_values))
    slope, intercept, r_value, p_value, std_err = linregress(x_values, y_values)

    return {'slope': slope, 'intercept': intercept, 'r_squared': r_value**2, 'p_value': p_value, 'std_err': std_err}

def save_geojson_chunk(gdf_subset, chunk_id, output_directory):
    """Saves a subset of the GeoDataFrame as a GeoJSON file."""
    filename = f"{output_directory}/chunk_{chunk_id}.geojson"
    gdf_subset.to_file(filename, driver='GeoJSON')
    print(f"Saved {filename}")

def main():
    file_path = '/mnt/d/Optimaize/Cantal/EGMS_L3_E37N24_100km_U/EGMS_L3_E37N24_100km_U.csv'
    output_directory = 'geojson_chunks'
    os.makedirs(output_directory, exist_ok=True)  # Create output directory if it doesn't exist

    gdf = load_and_transform_data(file_path)

    # Parallel processing without tqdm for progress reporting
    results = Parallel(n_jobs=-1, batch_size=100, verbose=10)(
        delayed(calculate_differences)(row) for index, row in gdf.iterrows()
    )

    # Constructing results DataFrame
    results_df = pd.DataFrame(results)

    # Filter the results based on statistical significance and regression quality
    significant_results_df = results_df[(results_df['p_value'] <= 0.05) & (results_df['r_squared'] > 0.75)]

    # Concatenate filtered results to the GeoDataFrame
    gdf_final = pd.concat([gdf.reset_index(drop=True), significant_results_df], axis=1)
    gdf_final = gdf_final.dropna(subset=['slope'])  # Remove rows that became NaN after filtering

    # Assuming gdf_final is your final GeoDataFrame ready to be saved in chunks
    chunk_size = 1000  # Define your chunk size
    chunks = [gdf_final.iloc[start:start + chunk_size] for start in range(0, len(gdf_final), chunk_size)]

    # Save chunks in parallel
    Parallel(n_jobs=-1, verbose=10)(
        delayed(save_geojson_chunk)(chunk, i, output_directory) for i, chunk in enumerate(chunks)
    )
    #gdf_final.to_file(output_file_path, driver='GeoJSON')

if __name__ == '__main__':
    main()
