import requests
import random
from functools import partial
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from config.config import Variables

class PathGen:
    def __init__(self, input_map, num_drivers, hub_node):
        self.input_map = input_map
        self.output_map = []
        self.num_drivers = num_drivers
        self.hub_node = hub_node
        self.distance_matrix = []
        self.duration_matrix = []

    def calc_distance(self, lat, long):
        bang_coord = [12.97674656, 77.57527924]
        dist_y = ((lat - bang_coord[0]) * 20004) / 180
        dist_x = ((long - bang_coord[1]) * 40075) / 360
        dist = (dist_x**2 + dist_y**2) ** 0.5
        return dist

    def remove_coords(self):
        new_map = []
        for addr in self.input_map:
            if self.calc_distance(addr["latitude"], addr["longitude"]) <= 20:
                new_map.append(addr)
        self.input_map = new_map

    def distance_duraton_matrix(self):
        coord_str = ""
        for addr in self.input_map:
            coord_str += str(addr["longitude"]) + "," + str(addr["latitude"]) + ";"
        coord_str = coord_str[:-1]
        # url = f"http://osrm:{Variables.port2}/table/v1/driving/" + coord_str
        url = f"{Variables.osrm}/table/v1/driving/" + coord_str
        r = requests.get(url, params={"annotations": "distance,duration"})
        r = r.json()
        self.distance_matrix = r["distances"]
        self.duration_matrix = r["durations"]

        for i in range(0, len(self.distance_matrix)):
            for j in range(0, len(self.distance_matrix)):
                self.distance_matrix[i][j] = int(self.distance_matrix[i][j])
                self.duration_matrix[i][j] = int(self.duration_matrix[i][j]) + 300
        
        return self.distance_matrix, self.duration_matrix

    def create_data_model(self):
        data = {}
        data["distance"] = self.distance_matrix
        data["time"] = self.duration_matrix
        data["num_locations"] = len(self.distance_matrix)
        # The time windows are based on the edd of different items
        data["time_windows"] = [(0, 15000) for i in range(data['num_locations'])]
        #the demands are based on the output of the cv model
        data["demands"] = [random.randint(27, 16001) for i in range(data['num_locations'])]
        data["num_vehicles"] = self.num_drivers
        #Fixed to use the bigger bag out of the two
        data["vehicle_capacity"] = 6400000
        data["depot"] = self.hub_node
        return data

    def create_distance_evaluator(self, data):
        _distances = data["distance"]
        def distance_evaluator(manager, from_node, to_node):
            return _distances[manager.IndexToNode(from_node)][manager.IndexToNode(to_node)]
        return distance_evaluator


    def create_demand_evaluator(self, data):
        _demands = data["demands"]
        def demand_evaluator(manager, node):
            """Returns the demand of the current node"""
            return _demands[manager.IndexToNode(node)]
        return demand_evaluator


    def add_capacity_constraints(self, routing, data, demand_evaluator_index):
        capacity = "Capacity"
        routing.AddDimension(
            demand_evaluator_index,
            0,  # null capacity slack
            data["vehicle_capacity"],
            True,  # start cumul to zero
            capacity,
        )

    def create_time_evaluator(self, data):
        _total_time = data["time"]
        def time_evaluator(manager, from_node, to_node):
            """Returns the total time between the two nodes"""
            return _total_time[manager.IndexToNode(from_node)][manager.IndexToNode(to_node)]
        return time_evaluator

    def add_time_window_constraints(self, routing, manager, data, time_evaluator_index):
        time = "Time"
        #TODO: check horizon whether valid to keep constant or not
        horizon = 15000
        routing.AddDimension(
            time_evaluator_index,
            horizon,  # allow waiting time
            horizon,  # maximum time per vehicle
            True,  # don't force start cumul to zero since we are giving TW to start nodes // try false as well
            time,
        )
        time_dimension = routing.GetDimensionOrDie(time)
        # Add time window constraints for each location except depot
        # and 'copy' the slack var in the solution object (aka Assignment) to print it
        for location_idx, time_window in enumerate(data["time_windows"]):
            if location_idx == 0:
                continue
            index = manager.NodeToIndex(location_idx)
            time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])
            routing.AddToAssignment(time_dimension.SlackVar(index))
        # Add time window constraints for each vehicle start node
        # and 'copy' the slack var in the solution object (aka Assignment) to print it
        for vehicle_id in range(data["num_vehicles"]):
            index = routing.Start(vehicle_id)
            time_dimension.CumulVar(index).SetRange(
                data["time_windows"][0][0], data["time_windows"][0][1]
            )
            routing.AddToAssignment(time_dimension.SlackVar(index))
            # Warning: Slack var is not defined for vehicle's end node
            # routing.AddToAssignment(time_dimension.SlackVar(self.routing.End(vehicle_id)))

    def print_solution(self, manager, routing, assignment):
        for vehicle_id in range(manager.GetNumberOfVehicles()):
            index = routing.Start(vehicle_id)
            print(f"Route for vehicle {vehicle_id}:")
            route = []
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                print(f"{node_index}->", end="")
                route.append(node_index)
                index = assignment.Value(routing.NextVar(index))
            print(f"{manager.IndexToNode(index)}")
            route.append(manager.IndexToNode(index))
            if len(route) > 2:
                self.output_map.append(route)


    def get_output_map(self):
        self.distance_duraton_matrix()
        data = self.create_data_model()
        print(data["num_locations"])
        print(data["num_vehicles"])
        print(data["depot"])
        manager = pywrapcp.RoutingIndexManager(
            data["num_locations"], data["num_vehicles"], data["depot"]
        )
        routing = pywrapcp.RoutingModel(manager)

        distance_evaluator_index = routing.RegisterTransitCallback(
            partial(self.create_distance_evaluator(data), manager)
        )
        routing.SetArcCostEvaluatorOfAllVehicles(distance_evaluator_index)

        demand_evaluator_index = routing.RegisterUnaryTransitCallback(
            partial(self.create_demand_evaluator(data), manager)
        )
        self.add_capacity_constraints(routing, data, demand_evaluator_index)

        time_evaluator_index = routing.RegisterTransitCallback(
            partial(self.create_time_evaluator(data), manager)
        )
        self.add_time_window_constraints(routing, manager, data, time_evaluator_index)

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.FromSeconds(100)
        search_parameters.log_search = False

        solution = routing.SolveWithParameters(search_parameters)

        # TODO: What to do if a solution is not found
        if solution:
            self.print_solution(manager, routing, solution)
        else:
            print("No solution found!")

        return self.output_map
