from config.config import Variables
import pandas as pd
from location.geocoding import Geocoding



# example for location module
data_df = pd.read_excel("data/bangalore_dispatch_address_finals.xlsx")
g = Geocoding(Variables.bingAPIKey, data_df)

res = g.generate()

print(res)
