import time
import geocoder
import pandas as pd
from multiprocessing import Pool

begin = time.time()
df1 = pd.read_excel('bangalore_dispatch_address_finals.xlsx')

# url = 'http://dev.virtualearth.net/REST/v1/Locations'
# params = {
#     'o': 'json',
#     'key': api_key,
#     'q': address,
# }

addr_pool = []
addresses = df1['address'].to_list()
l = len(addresses)
cnt = 0
while(cnt < l):
    if cnt + 50 < l :
        addr_pool.append(addresses[cnt:cnt+50])
    else :
        addr_pool.append(addresses[cnt:])
    cnt = cnt + 50

def geoloc(addrs) :
    api_key = 'Aj0kdjJUmR5qY-2sgW5uopGoXVWnXDKIAutHIg6e1xyhB-pia3spmJ8jEB1z_vZD'
    g = geocoder.bing(addrs, key=api_key, method='batch')
    latlngs = []
    for result in g:
        # print(result.latlng)
        latlngs.append(result.latlng)
    return latlngs

print("start")
p = Pool()
results = p.map(geoloc, addr_pool)
lats = []
longs = []

for i in range(0,l):
    row = int(i/50)
    col = i%50
    lats.append(results[row][col][0])
    longs.append(results[row][col][1])

df1['Latitude'] = lats
df1['Longitude'] = longs

df1.to_excel("Geocode.xlsx")
end = time.time()
print(end - begin)

# for result in g:
#     print(result.latlng)
# print(g.json)
