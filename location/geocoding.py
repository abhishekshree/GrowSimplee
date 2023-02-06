import geocoder
import requests
from multiprocessing import Pool
import random


class Geocoding:
    def __init__(self, bing_api_key, address_df=None, address=None):
        # print("API-KEY:______________________"+ str(bing_api_key))
        self.bing_api_key = bing_api_key
        self.address_df = address_df
        self.address = address
        self.result = []
        self.dist_matrix = []
        self.dur_matrix = []

    @staticmethod
    def generate_address_pool(address):
        addr_pool = []
        addresses = address.to_list()
        l = len(addresses)
        cnt = 0
        while cnt < l:
            if cnt + 50 < l:
                addr_pool.append(addresses[cnt : cnt + 50])
            else:
                addr_pool.append(addresses[cnt:])
            cnt = cnt + 50
        return addr_pool

    def geo_loc_single(self):
        g = geocoder.bing(self.address, key=self.bing_api_key)

    def geoloc(self, addrs):
        g = geocoder.bing(addrs, key=self.bing_api_key, method="batch")
        latlngs = []
        for result in g:
            latlngs.append(result.latlng)
        return latlngs

    def calc_distance(self, lat, long):
        bang_coord = [12.97674656, 77.57527924]
        dist_y = ((lat - bang_coord[0]) * 20004) / 180
        dist_x = ((long - bang_coord[1]) * 40075) / 360
        dist = (dist_x**2 + dist_y**2) ** 0.5
        return dist

    def remove_coords(self):
        new_map = []
        # print(len(self.result))
        for addr in self.result:
            if self.calc_distance(addr["latitude"], addr["longitude"]) <= 20:
                new_map.append(addr)
            else:
                print(addr)
        self.result = new_map

    def generate(self):
        addrs = self.address_df["address"]
        location = self.address_df["location"]
        AWB = self.address_df["AWB"]
        names = self.address_df["names"]
        product_id = self.address_df["product_id"]
        # TODO: randomize volume for testing
        # volume = self.address_df["volume"]
        volume = [random.randint(27, 16001) for i in range(len(addrs))]
        # TODO: randomize EDD for testing
        EDD = self.address_df["EDD"]
        # EDD = [random.randint(1000, 18000) for i in range(len(addrs))]
        pickup = [False for i in range(len(addrs))]
        # pickup = self.address_df["pickup"]
        address_pool = self.generate_address_pool(addrs)

        p = Pool()
        results = p.map(self.geoloc, address_pool)
        # print("results --->",results)
        lats = []
        longs = []
        for i in range(0, len(addrs)):
            row = int(i / 50)
            col = i % 50
            # print(row)
            # print(col)
            lats.append(results[row][col][0])
            longs.append(results[row][col][1])

            self.result.append(
                {
                    "address": addrs[i],
                    "latitude": lats[i],
                    "longitude": longs[i],
                    "location": location[i],
                    "AWB": str(AWB[i]),
                    "name": names[i],
                    "product_id": product_id[i],
                    "volume": volume[i],
                    "EDD": 18000,
                    "pickup": pickup[i],  ## DO NOT KNOW THE FORMAT OF THIS YET
                }
            )
        self.remove_coords()
        return self.result
