import geocoder
from multiprocessing import Pool


class Geocoding:
    def __init__(self, bing_api_key, address_df):
        self.bing_api_key = bing_api_key
        self.address_df = address_df
        self.result = []

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

    def geoloc(self, addrs):
        g = geocoder.bing(addrs, key=self.bing_api_key, method="batch")
        latlngs = []
        for result in g:
            latlngs.append(result.latlng)
        return latlngs

    def generate(self):
        addrs = self.address_df["address"]
        address_pool = self.generate_address_pool(addrs)


        p = Pool()
        results = p.map(self.geoloc, address_pool)
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
                {"address": addrs[i], "latitude": lats[i], "longitude": longs[i]}
            )
        return self.result
