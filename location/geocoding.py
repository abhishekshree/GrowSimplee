import geocoder
import requests
from multiprocessing import Pool


class Geocoding:
    def __init__(self, bing_api_key, address_df=None, address=None):
        # print("API-KEY:______________________"+ str(bing_api_key))
        self.bing_api_key = bing_api_key
        self.address_df = address_df
        self.address=address
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

    def generate(self):
        addrs = self.address_df["address"]
        location = self.address_df["location"]
        AWB = self.address_df["AWB"]
        names = self.address_df["names"]
        product_id = self.address_df["product_id"]
        volume = self.address_df["volume"]
        EDD = self.address_df["EDD"]
        pickup = self.address_df["pickup"]
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
                    "EDD": EDD[i],
                    "pickup": pickup[i]                    
                }
            )
        return self.result

    def calc_distance(self, lat, long):
        bang_coord = [12.97674656, 77.57527924]
        dist_y = ((lat - bang_coord[0]) * 20004) / 180
        dist_x = ((long - bang_coord[1]) * 40075) / 360
        dist = (dist_x**2 + dist_y**2) ** 0.5
        return dist

    def remove_coords(self):
        new_result = []
        for addr in self.result:
            if self.calc_distance(addr["latitude"], addr["longitude"]) <= 20:
                new_result.append(addr)

        # print(new_result)
        self.result = new_result

    def distance_duraton_matrix(self):
        coord_str = ""
        for addr in self.result:
            coord_str += str(addr["longitude"]) + "," + str(addr["latitude"]) + ";"
        coord_str = coord_str[:-1]
        url = f"http://localhost:{self.port2}/table/v1/driving/" + coord_str
        r = requests.get(url, params={"annotations": "distance,duration"})
        r = r.json()
        self.dist_matrix = r["distances"]
        self.dur_matrix = r["durations"]
        return self.dist_matrix, self.dur_matrix
