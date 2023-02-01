import sys
import requests
import json

admin_id = sys.argv[1]
print(admin_id)
drivers_url = f"http://localhost:5050/get/admin/drivers?admin_id={admin_id}"
paths_url = "http://localhost:5050/get/driver/path?"

coords_str=""

payload={}
headers = {}

r = requests.request("GET", drivers_url, headers=headers, data=payload)
r = r.json()
print(r)
driver_ids = []
for driver in r:
    driver_ids.append(driver["driver_id"])

for driver_id in driver_ids:
    path = requests.get(paths_url + f"driver_id={driver_id}")
    path = path.json()
    for point in path:
        coords_str+=str(point["longitude"]) + "," + str(point["latitude"]) + ";"
    print(coords_str)