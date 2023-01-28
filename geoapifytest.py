import requests
from requests.structures import CaseInsensitiveDict
import time
import pandas as pd
from config.config import Variables

class GeoApify:
    def __init__(self, api_key, address_df):
        self.api_key = api_key
        self.address_df = address_df
        self.result = []
    

    @staticmethod
    def generate_address_pool(address):
        addr_pool = []
        addresses = address.to_list()
        l = len(addresses)
        cnt = 0
        incr = 1000
        while cnt < l:
            if cnt + incr < l:
                addr_pool.append(addresses[cnt : cnt + incr])
            else:
                addr_pool.append(addresses[cnt:])
            cnt = cnt + incr
        return addr_pool

    def geocode(self,addrs):
        data = addrs
        url = f"https://api.geoapify.com/v1/batch/geocode/search?&apiKey={self.api_key}"
        r = requests.post(url, json=data)
        latlongs=[]
                 

        



url = "https://api.geoapify.com/v1/geocode/search?text=38%20Upper%20Montagu%20Street%2C%20Westminster%20W1H%201LJ%2C%20United%20Kingdom&apiKey=295dd37df0674ff9ade5603ac2e14baf"

headers = CaseInsensitiveDict()
headers["Accept"] = "application/json"

data = pd.read_excel("data/bangalore_dispatch_address_finals.xlsx")
data = data["address"].to_list()[0:1000]


api_key = Variables.GeoApifyKey

# print((data["address"].to_list()))
url = f"https://api.geoapify.com/v1/batch/geocode/search?&apiKey={api_key}"


r1 = requests.post(url, json=data)
get_url = r1.json()["url"]
r=requests.get("https://api.geoapify.com/v1/batch/geocode/search?id=86e827aeed8b4499b9ad45c19343897e&apiKey=295dd37df0674ff9ade5603ac2e14baf")


out=[]

start = time.time()
end = -1
while True:
    r2 = requests.get(get_url)
    if (type(r2.json())==list):
        print(r2.json())
        end = time.time()
        break

print("time: ", end-start)
  


# r = requests.post(url, json=data)


# start=time.time()
# resp = requests.get(url, headers=headers)
# end=time.time()

# print(resp.json()["features"][0]['properties']['lon'])
# print("TIME: ", end-start)