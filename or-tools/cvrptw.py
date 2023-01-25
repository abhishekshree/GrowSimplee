import pandas as pd
import time
import requests
import random
#40075 kms
#20,004 kms

begin = time.time()

bang_coord = [
       12.97674656,
       77.57527924
      ]

def distance_calc(lat_diff, long_diff):
    dist = ((lat_diff * 20004) / 180) + ((long_diff * 40075) / 360)
    return dist

df = pd.read_excel("Geocode.xlsx")
l = len(df['Latitude'])
distance_matrix = []
addr = []
lats = []
longs = []
lat_longs = []
info_pass = []

for i in range(0, l):
    d = distance_calc(abs(df['Latitude'][i] - bang_coord[0]), abs(df['Longitude'][i] - bang_coord[1])) 
    if(d <= 20):
        lats.append(df['Latitude'][i])
        longs.append(df['Longitude'][i])
        lat_longs.append([df['Latitude'][i], df['Longitude'][i]])
        info_pass.append({'lat': df['Latitude'][i], 'lng': df["Longitude"][i]})
        addr.append(df['address'][i])
    else:
        pass
        # print(d)
        # print(df['address'][i])

l = len(lats)
# print(info_pass)
# for i in range(0, l):
#     distance_list = []
#     for j in range(0, l):
#         d = distance_calc(abs(lats[i] - lats[j]), abs(longs[i] - longs[j]))
#         distance_list.append(d)
#     distance_matrix.append(distance_list)


coord_str = ""
for latlng in lat_longs:
    coord_str += str(latlng[1]) + "," + str(latlng[0]) + ";"
coord_str = coord_str[:-1]

url = "http://localhost:5000/table/v1/driving/" + coord_str

# def distance_fetch(sources):
#     source_str = ""
#     for s in sources:
#         source_str += str(s) + ";"
#     source_str = source_str[:-1]
#     params = {
#         'annotations': 'distance',
#         'sources': source_str
#     }
#     r = requests.get(url, params=params)
#     try:
#         r = r.json()
#     except:
#         print(r.content)
#         exit(0)
#     return r['distances']


max1 = 0
max2 = 0 
curr_node = 144

source_mat = []
cnt = 0
while(cnt < l):
    if cnt + 10 < l:
        sm = [i for i in range(cnt, cnt + 10)]
        source_mat.append(sm)
    else:
        sm = [i for i in range(cnt, l)]
        source_mat.append(sm)
    cnt += 10
    
# p = Pool()
# res = p.map(distance_fetch, source_mat)

# for r in res:
#     for distances in r:
#         distance_matrix.append(distances)

params = {
    'annotations' : 'distance,duration'
}

r = requests.get(url, params=params)
r = r.json()
distance_matrix = r['distances']
duration_matrix = r['durations']

for i in range(0,l):
    max2 = max(distance_matrix[curr_node][i], max2)
    for j in range(0, l):
        distance_matrix[i][j] = int(distance_matrix[i][j])
        duration_matrix[i][j] = int(duration_matrix[i][j]) + 300
        max1 = max(distance_matrix[i][j], max1)

print("Max distance from curr node = ", max2)
print("Max distance between nodes in total", max1)

print()
print("Routing started")
print()

# [START import]
from functools import partial
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
# [END import]

num_loc = len(distance_matrix)

# [START data_model]
def create_data_model():
    """Stores the data for the problem."""
    data = {}
    
    data['distance'] = distance_matrix
    data['time'] = duration_matrix
    data['num_locations'] = num_loc
    data['time_windows'] = [(0, 15000) for i in range(num_loc)]
    data['demands'] = [random.randint(27, 16001) for i in range(num_loc)]
    data['num_vehicles'] = random.randint(int(num_loc / 20), int(num_loc / 15) + 1)
    data['vehicle_capacity'] = 6400000
    data['depot'] = curr_node
    return data
    # [END data_model]


#######################
# Problem Constraints #
#######################


def create_distance_evaluator(data):
    """Creates callback to return distance between points."""
    _distances = data['distance']

    def distance_evaluator(manager, from_node, to_node):
        """Returns the manhattan distance between the two nodes"""
        return _distances[manager.IndexToNode(from_node)][manager.IndexToNode(
            to_node)]

    return distance_evaluator


def create_demand_evaluator(data):
    """Creates callback to get demands at each location."""
    _demands = data['demands']

    def demand_evaluator(manager, node):
        """Returns the demand of the current node"""
        return _demands[manager.IndexToNode(node)]

    return demand_evaluator


def add_capacity_constraints(routing, data, demand_evaluator_index):
    """Adds capacity constraint"""
    capacity = 'Capacity'
    routing.AddDimension(
        demand_evaluator_index,
        0,  # null capacity slack
        data['vehicle_capacity'],
        True,  # start cumul to zero
        capacity)


def create_time_evaluator(data):

    _total_time = data['time']

    def time_evaluator(manager, from_node, to_node):
        """Returns the total time between the two nodes"""
        return _total_time[manager.IndexToNode(from_node)][manager.IndexToNode(
            to_node)]

    return time_evaluator


def add_time_window_constraints(routing, manager, data, time_evaluator_index):
    """Add Global Span constraint"""
    time = 'Time'
    horizon = 15000
    routing.AddDimension(
        time_evaluator_index,
        horizon,  # allow waiting time
        horizon,  # maximum time per vehicle
        True,  # don't force start cumul to zero since we are giving TW to start nodes // try false as well
        time)
    time_dimension = routing.GetDimensionOrDie(time)
    # Add time window constraints for each location except depot
    # and 'copy' the slack var in the solution object (aka Assignment) to print it
    for location_idx, time_window in enumerate(data['time_windows']):
        if location_idx == 0:
            continue
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])
        routing.AddToAssignment(time_dimension.SlackVar(index))
    # Add time window constraints for each vehicle start node
    # and 'copy' the slack var in the solution object (aka Assignment) to print it
    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        time_dimension.CumulVar(index).SetRange(data['time_windows'][0][0],
                                                data['time_windows'][0][1])
        routing.AddToAssignment(time_dimension.SlackVar(index))
        # Warning: Slack var is not defined for vehicle's end node
        #routing.AddToAssignment(time_dimension.SlackVar(self.routing.End(vehicle_id)))


# [START solution_printer]
def print_solution(manager, routing, assignment):  # pylint:disable=too-many-locals
    """Prints assignment on console"""
    print(f'Objective: {assignment.ObjectiveValue()}')
    time_dimension = routing.GetDimensionOrDie('Time')
    capacity_dimension = routing.GetDimensionOrDie('Capacity')
    total_distance = 0
    total_load = 0
    total_time = 0

    routes=[]
    for vehicle_id in range(manager.GetNumberOfVehicles()):
        index = routing.Start(vehicle_id)
        print(f'Route for vehicle {vehicle_id}:')
        route=[]
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            print(f'{node_index}->', end='')
            route.append(lat_longs[node_index])
            index = assignment.Value(routing.NextVar(index))
        print(f'{manager.IndexToNode(index)}')
        route.append(lat_longs[manager.IndexToNode(index)])
        if(len(route)>2):
            routes.append(route)
    print(routes)

    # for vehicle_id in range(manager.GetNumberOfVehicles()):
    #     index = routing.Start(vehicle_id)
    #     print('Route for vehicle {}:\n'.format(vehicle_id), end='')
    #     distance = 0
    #     while not routing.IsEnd(index):
    #         load_var = capacity_dimension.CumulVar(index)
    #         time_var = time_dimension.CumulVar(index)
    #         slack_var = time_dimension.SlackVar(index)
    #         print(' {0} Load({1}) Time({2},{3}) Slack({4},{5}) ->'.format(
    #             manager.IndexToNode(index),
    #             assignment.Value(load_var),
    #             assignment.Min(time_var),
    #             assignment.Max(time_var),
    #             assignment.Min(slack_var), assignment.Max(slack_var)), end='')
    #         previous_index = index
    #         index = assignment.Value(routing.NextVar(index))
    #         distance += routing.GetArcCostForVehicle(previous_index, index,
    #                                                  vehicle_id)
    #     load_var = capacity_dimension.CumulVar(index)
    #     time_var = time_dimension.CumulVar(index)
    #     slack_var = time_dimension.SlackVar(index)
    #     print(' {0} Load({1}) Time({2},{3})\n'.format(
    #         manager.IndexToNode(index),
    #         assignment.Value(load_var),
    #         assignment.Min(time_var), assignment.Max(time_var)), end='')
    #     print('Distance of the route: {0}m\n'.format(distance), end='')
    #     print('Load of the route: {}\n'.format(
    #         assignment.Value(load_var)), end="")
    #     print('Time of the route: {}\n'.format(
    #         assignment.Value(time_var)), end='')
    #     print()
    #     total_distance += distance
    #     total_load += assignment.Value(load_var)
    #     total_time += assignment.Value(time_var)
    # print('Total Distance of all routes: {0}m'.format(total_distance))
    # print('Total Load of all routes: {}'.format(total_load))
    # print('Total Time of all routes: {0}min'.format(total_time))
    # [END solution_printer]


def main():
    """Solve the Capacitated VRP with time windows."""
    # Instantiate the data problem.
    # [START data]
    data = create_data_model()
    # [END data]

    # Create the routing index manager.
    # [START index_manager]
    manager = pywrapcp.RoutingIndexManager(data['num_locations'],
                                           data['num_vehicles'], data['depot'])
    # [END index_manager]

    # Create Routing Model.
    # [START routing_model]
    routing = pywrapcp.RoutingModel(manager)
    # [END routing_model]

    # Define weight of each edge.
    # [START transit_callback]
    distance_evaluator_index = routing.RegisterTransitCallback(
        partial(create_distance_evaluator(data), manager))
    # [END transit_callback]

    # Define cost of each arc.
    # [START arc_cost]
    routing.SetArcCostEvaluatorOfAllVehicles(distance_evaluator_index)
    # [END arc_cost]

    # Add Capacity constraint.
    # [START capacity_constraint]
    demand_evaluator_index = routing.RegisterUnaryTransitCallback(
        partial(create_demand_evaluator(data), manager))
    add_capacity_constraints(routing, data, demand_evaluator_index)
    # [END capacity_constraint]

    # Add Time Window constraint.
    # [START time_constraint]
    time_evaluator_index = routing.RegisterTransitCallback(
        partial(create_time_evaluator(data), manager))
    add_time_window_constraints(routing, manager, data, time_evaluator_index)
    # [END time_constraint]

    # Setting first solution heuristic (cheapest addition).
    # [START parameters]
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_parameters.time_limit.FromSeconds(100)
    search_parameters.log_search = False
    # [END parameters]

    # Solve the problem.
    # [START solve]
    solution = routing.SolveWithParameters(search_parameters)
    # [END solve]

    # Print solution on console.
    # [START print_solution]
    if solution:
        print_solution(manager, routing, solution)
    else:
        print('No solution found!')
    # [END print_solution]


if __name__ == '__main__':
    main()
# [END program]
