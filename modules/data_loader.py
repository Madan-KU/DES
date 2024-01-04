import os
import logging
import pyarrow as pa
import pyarrow.parquet as pq

## Reads Parquet data
def read_data(directory):
    if not os.path.exists(directory):
        logging.warning(f"Directory {directory} does not exist.")
        return None,'None'
    
    for file in os.listdir(directory):
        if file.endswith(".parquet"):
            try:
                file_path = os.path.join(directory, file)
                parquet_table = pq.read_table(file_path)
                df=parquet_table.to_pandas()
                logging.info(f"Successfully read {file}, shape {df.shape}")
                return df, file
            
            except Exception as e:
                logging.error(f"Error reading {file}: {e}")
                continue

    logging.warning(f"No data file found in {directory}.")
    return None, 'None'