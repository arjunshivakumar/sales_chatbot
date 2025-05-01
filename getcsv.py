from kaggle.api.kaggle_api_extended import KaggleApi
from dotenv import load_dotenv
import os
DATA_FILE = "coffee_sales.csv"


print("Downloading dataset from Kaggle...")

api = KaggleApi()
api.authenticate()

# Download the dataset and extract only index_1.csv
api.dataset_download_file('ihelon/coffee-sales', file_name='index_1.csv', path='.')

# Unzip the file
import zipfile
with zipfile.ZipFile('index_1.csv.zip', 'r') as zip_ref:
    zip_ref.extractall(".")

# Rename for consistency
os.rename("index_1.csv", DATA_FILE)
os.remove("index_1.csv.zip")  # clean up
print("Download and extraction complete.")
