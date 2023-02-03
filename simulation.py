import sys
import requests
import json
from config.config import Variables
import numpy as np
import time as t

#TODO: normalize with resepct to prefix sums

admin_id = sys.argv[1]
print(admin_id)
drivers_url = f"http://localhost:5050/get/admin/drivers?admin_id={admin_id}"
paths_url = "http://localhost:5050/get/driver/path?"

r = requests.request("GET", drivers_url)
drivers = r.json()
print (r)

osrm = "http://localhost:5000"
coords=""

time_frame=100.0

driver_prefix=[0] #prefix sum of driver path lengths to locate where a driver's points start on duration matrix
times_to_reach=[] #time at which the driver reaches point i
driver_paths=[] # coordinates of driver's path
driver_locs = [0]*len(drivers) # index of last location visited
driver_pos= [[0,0]]*len(drivers) # current position of the driver at time t
driver_completed = [False]*len(drivers)


for driver in drivers:
    driver_path=[]
    path = requests.get(paths_url + f"driver_id={driver['driver_id']}").json()

    if len(driver_prefix) == 0:
        driver_prefix.append(len(path))    
    else:
        driver_prefix.append(driver_prefix[-1] + len(path))
    for point in path:
        driver_path.append([point["latitude"], point["longitude"]])
        coords += str(point["longitude"]) + "," + str(point["latitude"]) + ";"
    driver_paths.append(driver_path)
coords = coords[:-1]

distance_duration_url = f"{osrm}/table/v1/driving/" + coords
r = requests.get(distance_duration_url, params={"annotations": "distance,duration"})
r = r.json()
distance_matrix = r["distances"]
duration_matrix = r["durations"]

# print(driver_prefix)

max_duration=0


for i in duration_matrix:
    for j in i:
        max_duration=max(max_duration,j)
# print(max_duration)

for i in range(len(duration_matrix)):
    for j in range(len(duration_matrix[i])):
        duration_matrix[i][j] = duration_matrix[i][j]*time_frame/max_duration


# print(duration_matrix)

# print(r)

# print(driver_locs)

# print(driver_paths)

for i in range(len(driver_prefix[:-1])):
    driver_path_durations=[0]
    for j in range(driver_prefix[i], driver_prefix[i+1]-1):
        driver_path_durations.append(duration_matrix[j][j+1])
    times_to_reach.append(driver_path_durations)


# print(times_to_reach)

for d in times_to_reach:
    for i in range(1,len(d)):
        d[i]+=d[i-1]

# print(times_to_reach)
# print("LEN D ", len(times_to_reach[0]))
# print("LEN P ", len(driver_paths[0]))
# print("LEN L ", len(driver_locs[0]))
test = [0]*len(driver_paths[0])

# print(driver_paths[0][-1])


for time in range(1,int(time_frame)):
    t.sleep(0.55)
    print("TIME: ", time)
    for i in range(1,2):
        if driver_completed[i]:
            driver_pos[i]=driver_paths[i][-1]
        else:
            if time>=times_to_reach[i][-1]:
                driver_completed[i]=True
                driver_pos[i]=driver_paths[i][-1]
                continue
            while driver_locs[i]-1< len(times_to_reach) and time>=times_to_reach[i][driver_locs[i]]:
                driver_locs[i]+=1


                # driver_locs[i]+=1
                # if driver_locs[i]>=len(driver_paths[i])-1:
                #     driver_completed[i]=True
                #     break
            driver_locs[i]-=1 # gives last point visited
            print("DRIVER LOC ", driver_locs[i])
            if driver_completed[i]:
                driver_pos[i]=driver_paths[i][-1]
            else:
                curr_point = driver_paths[i][driver_locs[i]]
                next_point = driver_paths[i][driver_locs[i]+1]
                duration_between_points = times_to_reach[i][driver_locs[i]+1]-times_to_reach[i][driver_locs[i]]
                time_elapsed = time - times_to_reach[i][driver_locs[i]]
                x_curr = curr_point[0]+ (next_point[0]-curr_point[0])*time_elapsed*1.0/duration_between_points
                y_curr = curr_point[1]+ (next_point[1]-curr_point[1])*time_elapsed*1.0/duration_between_points
                driver_pos[i]=[x_curr,y_curr]
            print("CURR POINT ", driver_pos[i])

        
        





