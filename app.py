from datetime import datetime
from config.config import Variables
from statistics import mean 
import pandas as pd
import numpy as np
from location.geocoding import Geocoding
from or_tools.paths import PathGen
from flask import Flask, request, jsonify
import os
from flask_sqlalchemy import SQLAlchemy
import uuid
import json
from flask_cors import CORS, cross_origin
import requests
import sys
import geocoder
from twilio.rest import Client
import copy
from statistics import mean
from math import dist
import numpy as np


UPLOAD_FOLDER = Variables.uploadFolder
ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}

db = SQLAlchemy()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SQLALCHEMY_DATABASE_URI"] = Variables.databaseURI

db.init_app(app)
cors = CORS(app)


########DATABASES########
class Admin(db.Model):
    __tablename__ = "admin"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    input_map = db.Column(db.Text, default="[]")
    num_drivers = db.Column(db.Integer, default=0)
    day_started = db.Column(db.Boolean, default=False)
    output_map = db.Column(db.Text, default=None)
    # date = db.Column(db.DateTime, default=datetime.utcnow)
    dynamic_point = db.Column(db.Text)
    unrouted_points = db.Column(db.Text, default="[]")

    def get_input_map(self):
        return json.loads(self.input_map)

    def get_output_map(self):
        return json.loads(self.output_map)

    def put_input_map(self, input_map):
        self.input_map = json.dumps(input_map)

    def put_output_map(self, output_map):
        self.output_map = json.dumps(output_map)

    def __repr__(self):
        return f"Admin id: {self.id}"


class Driver(db.Model):
    __tablename__ = "driver"
    id = db.Column(db.String, primary_key=True)  # admin_id + [1,num_drivers]
    name = db.Column(db.String)
    admin_id = db.Column(db.String, db.ForeignKey("admin.id"))
    path = db.Column(db.Text)
    date = db.Column(db.DateTime)
    remaining_capacity = db.Column(db.Integer, default=640000)

    def get_path(self):
        return json.loads(self.path)

    def put_path(self, path):
        self.path = json.dumps(path)

    def __init__(
        self,
        id,
        admin_id,
        name=None,
        path=None,
        date=None,
    ):
        self.id = id
        self.admin_id = admin_id
        self.name = name
        self.put_path(path)
        self.date = date


###########################

#########HELPER FUNCTIONS########

# def remove_outliers(admin_id):
#     admin = Admin.query.get_or_404(admin_id)
#     input_map = json.loads(admin.input_map)
#     def norm(point1, point2):
#         return ((int(point1[0]) - int(point2[0])) **2 + (int(point1[1]) - int(point2[1])) **2) ** 0.5 
#     avg = [mean(map(lambda point: int(point["latitude"]), input_map)), mean(map(lambda point: int(point["longitude"]), input_map))] 
#     std= np.std(map(lambda point: norm([point["latitude"], point["longitude"]], avg), input_map))

#     z_scores = map(lambda point: norm([point["latitude"], point["longitude"]], avg)/std, input_map)
#     return z_scores
    

def get_undelivered_points(driver_id):
    driver = Driver.query.get_or_404(driver_id)
    path = json.loads(driver.path)
    undelivered_points = []
    for point in path:
        if point["delivered"] == False:
            undelivered_points.append(point)
    return undelivered_points

def remove_ridiculous_points(admin_id):
    admin = Admin.query.get_or_404(admin_id)
    input_map = json.loads(admin.input_map)
    
    removed=0
    n = len(input_map)
    while True:
        flag = True
        lats = []
        longs = []
        for point in input_map:
            lats.append(point["latitude"])
            longs.append(point["longitude"])
        
        avg = [mean(lats), mean(longs)]
        dists = [dist([x,y], avg) for x,y in zip(lats,longs)]
        avg_dist = mean(dists)
        std_dist= np.std(dists)
        new_input_map = []
        for i in range(len(dists)):
            if dists[i] < avg_dist + 5*std_dist:
                new_input_map.append(input_map[i])
            else:
                flag = False
                removed+=1
                if removed>n/20:
                    break
        input_map = new_input_map
        if removed>n/20:
            break
        if flag:
            break
    admin.input_map = json.dumps(input_map)
    db.session.commit()


def get_geocoding_for(address):
    g = geocoder.bing(address, key=Variables.bingAPIKey)
    return g.latlng


def distance_between(point1, point2):
    long1 = point1["longitude"]
    long2 = point2["longitude"]
    lat1 = point1["latitude"]
    lat2 = point2["latitude"]

    r = requests.get(
        f"{Variables.osrm}/table/v1/driving/{long1},{lat1};{long2},{lat2}",
        params={"annotations": "distance"},
    )
    r = r.json()
    return int(r["distances"][0][1])


def duration_between(point1, point2):
    long1 = point1["longitude"]
    long2 = point2["longitude"]
    lat1 = point1["latitude"]
    lat2 = point2["latitude"]

    r = requests.get(
        f"{Variables.osrm}/table/v1/driving/{long1},{lat1};{long2},{lat2}",
        params={"annotations": "duration"},
    )
    r = r.json()
    return int(r["durations"][0][1])

def distance_duration_between(url, point):
    url = f"{point['longitude']},{point['latitude']};{url}"

    r = requests.get(
        f"{Variables.osrm}/table/v1/driving/{url}",
        params={
            "annotations": "distance,duration",
            "destinations": "0"
            },
    )
    r = r.json()

    r1 = requests.get(
        f"{Variables.osrm}/table/v1/driving/{url}",
        params={
            "annotations": "distance,duration",
            "sources": "0"
            },
    )
    r1 = r1.json()
    return r["distances"], r["durations"], r1["distances"][0], r1["durations"][0]

def insert_dynamic_points(admin_id):
    def cost(dist, time):
        return dist + 100 * time

    admin = Admin.query.get_or_404(admin_id)
    dynamic_point = json.loads(admin.dynamic_point)
    input_map = json.loads(admin.input_map)
    input_map.append(dynamic_point)
    admin.input_map = json.dumps(input_map)
    db.session.commit()
    drivers = Driver.query.filter(Driver.admin_id == admin_id).all()
    # undelivered_routes=[]
    # for driver in drivers:
    #     undelivered_routes.append(get_undelivered_points(driver.id))

    # distance increment
    # time window lapse
    # capacity check
    # trip_window check

    routes = []
    for driver in drivers:
        routes.append(json.loads(driver.path))

    min_cost = 1e18

    route_idx = -1
    point_idx = -1
    time_change = 0

    coord_url = ""
    for k, route in enumerate(routes):
        for i, point in enumerate(route):
            coord_url += f"{point['longitude']},{point['latitude']};"

    coord_url = coord_url[:-1]
    dist_to_matrix, dur_to_matrix, dist_from_matrix, dur_from_matrix = distance_duration_between(coord_url, dynamic_point)

    idx = 1
    for k, route in enumerate(routes):
        for i, point in enumerate(route[:-1]):
            if point["delivered"] == True:
                continue

            max_capacity = 0
            curr_capacity = 0
            for j in range(0, len(route)):
                # TODO: make hub node volume to be zero
                if route[j]["pickup"] == False:
                    curr_capacity += route[j]["volume"]
            for j in range(0, len(route)):
                if route[j]["pickup"] == False:
                    curr_capacity -= route[j]["volume"]
                else:
                    curr_capacity += route[j]["volume"]
                if j >= i:
                    max_capacity = max(max_capacity, curr_capacity)

            if max_capacity + dynamic_point["volume"] > 640000:
                continue

            next_point = route[i + 1]
            extra_dist = (
                int(dist_to_matrix[idx][0])
                + int(dist_from_matrix[idx+1])
                - next_point["prev_distance"]
            )

            extra_time = (
                int(dur_to_matrix[idx][0])
                + int(dur_from_matrix[idx+1])
                - (next_point["EDT"] - point["EDT"]) + 600
            )

            if int(dur_to_matrix[idx][0]) == 0 and int(dur_from_matrix[idx+1]) == 0:
                extra_time -= 600
            elif int(dur_to_matrix[idx][0]) == 0 or int(dur_from_matrix[idx+1]) == 0:
                extra_time -= 300
            
            time_window_penalty = 0
            idx += 1

            route_end_time = route[-1]["EDT"]
            # TODO: change 21600 to hub node ka end time
            if route_end_time + extra_time > 21600:
                continue
            # curr_time = extra_time #TODO: ask about the metric for time like what is lasttime, i think arpit's algo tries to take into account the time take for subsequest deliveries if the dynamic deilvery is done but that info is not available so makes no sense

            for j in range(i + 1, len(route)):
                time_window_penalty += max(
                    0, route[j]["EDT"] + extra_time - route[j]["EDD"]
                ) - max(0, route[j]["EDT"] - route[j]["EDD"])

            curr_cost = cost(extra_dist, time_window_penalty)
            if curr_cost < min_cost:
                min_cost = curr_cost
                route_idx = k
                point_idx = i
                time_change = extra_time
        idx += 1

    dynamic_point["delivered"] = False
    driver = Driver.query.get_or_404(
        str(admin_id) + "_" + str(route_idx + 1)
    )  # driver id is 1 indexed
    new_path = json.loads(driver.path)
    offset = duration_between(new_path[point_idx], dynamic_point)

    if(offset == 0):
        dynamic_point["EDT"] = offset + new_path[point_idx]["EDT"]
    else:
        dynamic_point["EDT"] = offset + new_path[point_idx]["EDT"] + 300

    dynamic_point["prev_distance"] = distance_between(new_path[point_idx], dynamic_point)
    new_path[point_idx + 1]["prev_distance"] = distance_between(dynamic_point, new_path[point_idx + 1])

    for i in range(point_idx + 1, len(new_path)):
        new_path[i]["EDT"] += time_change

    new_path.insert(point_idx + 1, dynamic_point)
    driver.path = json.dumps(new_path)

    db.session.commit()
    return route_idx + 1


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def put_input_map(file, admin_id):
    file.filename = "input." + file.filename.rsplit(".", 1)[1].lower()
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
    data_df = pd.read_excel(UPLOAD_FOLDER + file.filename)
    g = Geocoding(Variables.bingAPIKey, data_df)
    res = g.generate()

    admin = Admin.query.get_or_404(admin_id)
    admin.input_map = json.dumps(res)
    os.remove(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
    db.session.commit()


def generate_drivers(admin_id, n):
    inital_drivers = Driver.query.filter(Driver.admin_id == admin_id).all()
    for driver in inital_drivers:
        db.session.delete(driver)
    for i in range(1, 1 + n):
        driver = Driver(id=str(admin_id) + "_" + str(i), admin_id=admin_id)
        db.session.add(driver)
    admin = Admin.query.get_or_404(admin_id)
    admin.num_drivers = n
    db.session.commit()
    # print(len(Driver.query.filter(Driver.id.startswith(admin_id)).all()))


################################


###################ADMIN ROUTES####################


@app.route("/post/admin/new", methods=["POST"])  # creates a new admin
def post_admin():
    # get a json and store it in the database
    if request.method == "POST":
        # admin_id = str(uuid.uuid4())

        admin = Admin()

        db.session.add(admin)
        db.session.commit()
        return jsonify({"message": "Admin successfully created", "id": admin.id})   


@app.route(
    "/post/admin/input", methods=["GET", "POST"]
)  # takes admin id, map and number of drivers. Also updates driver db with the required number of drivers
def input():
    # get input as a dataframe and store it in data/ folder

    if request.method == "POST":
        form = request.form

        if "file" not in request.files:
            return jsonify({"message": "No file part in the request"}), 400
        if "no_of_drivers" not in form:
            return jsonify({"message": "Number of drivers not specified"})
        if "admin_id" not in form:
            return jsonify({"message": "Admin id not received"})
        file = request.files["file"]
        if not allowed_file(file.filename):
            return jsonify({"message": "Allowed file types are xlsx, xls, csv"}), 400

        admin_id = form["admin_id"]
        admin = Admin.query.get_or_404(admin_id)
        n = int(form["no_of_drivers"])
        if len(sys.argv) > 1:
            print("In API not working mode")
            preloaded = pd.read_excel("Geocode.xlsx")
            preloaded = preloaded.to_dict()
            admin.input_map = json.dumps(preloaded)
            return jsonify(
                {
                    "message": "Input successful",
                    "map": Admin.query.get_or_404(admin_id).input_map,
                    "debug": True,
                }
            )

        put_input_map(admin_id=admin_id, file=file)
        remove_ridiculous_points(admin_id=admin_id)
        generate_drivers(admin_id=admin_id, n=n)

        return jsonify(
            {
                "message": "Input successful",
                "map": json.loads(Admin.query.get_or_404(admin_id).input_map),
            }
        )


@app.route(
    "/post/admin/dynamicPoint", methods=["POST"]
)  # Allows admin to add a dynamic point
def add_dynamic_point():
    if request.method == "POST":
        print(request.get_json())
        if "admin_id" not in request.get_json():
            return jsonify({"message": "Admin id not received"})

        if "address" not in request.get_json():
            return jsonify({"message": "Address not received"})

        if "location" not in request.get_json():
            return jsonify({"message": "Location not received"})

        if "awb" not in request.get_json():
            return jsonify({"message": "AWB not received"})

        if "name" not in request.get_json():
            return jsonify({"message": "Name not received"})

        if "product_id" not in request.get_json():
            return jsonify({"message": "Product ID not received"})

        if "volume" not in request.get_json():
            return jsonify({"message": "Volume not received"})

        admin_id = request.get_json()["admin_id"]
        admin = Admin.query.get_or_404(admin_id)

        address = request.get_json()["address"]
        location = request.get_json()["location"] if request.get_json()["location"] else ""
        awb = request.get_json()["awb"]
        name = request.get_json()["name"]
        product_id = request.get_json()["product_id"]
        volume = float(request.get_json()["volume"])

        latitude, longitude = get_geocoding_for(address)

        # address = pd.read_json(json.dumps([data]))
        # result = Geocoding(Variables.bingAPIKey, address).generate()

        point = {
            "address": address,
            "location": location,
            "AWB": awb,
            "name": name,
            "product_id": product_id,
            "latitude": latitude,
            "longitude": longitude,
            "pickup": True,
            # TODO: see to the EDD of random points based on the input format
            "EDD": 21600,
            "volume": volume,
        }

        # TODO: Append the dynamic points to a list not a single dynamic point
        admin.dynamic_point = json.dumps(point)
        db.session.commit()

        driver_id_1 = insert_dynamic_points(admin_id)
        return jsonify(
            {
                "message": f"Point successfully added in the route of driver with id {driver_id_1}",
                "driver_id": driver_id_1
            }
        )


@app.route("/get/admin/dynamicPoint")  # returns the dynamic points added by an admin
def get_dynamic_point():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not specified"})
    admin_id = request.args.get("admin_id")
    admin = Admin.query.get_or_404(admin_id)

    return (
        jsonify(json.loads(admin.dynamic_point)) if admin.dynamic_point else jsonify([])
    )


@app.route("/")
def hello():
    # output = json.loads(Admin.query.get_or_404(1).output_map)
    # return jsonify(len(output))
    sum =0
    drivers = Driver.query.filter(Driver.admin_id == 1).all()
    for d in drivers:
        path = json.loads(d.path)
        sum += len(path)
    
    return jsonify(sum)


@app.route("/post/admin/end", methods=["POST"])
def end_day():
    if request.method == "POST":
        if "admin_id" not in request.get_json():
            return jsonify({"message": "Admin id not received"})

        admin_id = request.get_json()["admin_id"]
        admin = Admin.query.get_or_404(admin_id)
        admin.day_started = False
        db.session.commit()
        return jsonify({"message": "Day ended"})


@app.route("/post/admin/start", methods=["POST"])
def gen_map():
    if request.method == "POST":
        if "admin_id" not in request.get_json():
            return jsonify({"message": "Admin id not received"})
        if "hub_node" not in request.get_json():
            return jsonify({"message": "Hub node not received"})

        admin_id = request.get_json()["admin_id"]
        admin = Admin.query.get_or_404(admin_id)
        input_map = json.loads(admin.input_map)
        # return jsonify((input_map))

        num_drivers = int(admin.num_drivers)
        hub_node = int(request.get_json()["hub_node"])
        input_map[hub_node]["EDD"] = 18000
        # print(input_map)
        idx_map = []
        for i in range(0, len(input_map)):
            idx_map.append(
                {
                    "latitude": input_map[i]["latitude"],
                    "longitude": input_map[i]["longitude"],
                    "EDD": input_map[i]["EDD"],
                    "volume": input_map[i]["volume"],
                }
            )

        # print("generate path")
        pg = PathGen(idx_map, num_drivers, hub_node)
        # print("Enter output")
        output_map, unrouted_idx = pg.get_output_map()

        unrouted_points = []
        for idx in unrouted_idx:
            unrouted_points.append(input_map[idx])

        admin.unrouted_points = json.dumps(unrouted_points)

        # print("output map", output_map)

        final_output = {}
        final_output["Routes"] = []
        final_output["Unrouted_points"] = unrouted_points
        for driver_path in output_map:
            driver_map = []
            for loc in driver_path:
                output_loc = copy.deepcopy(input_map[loc[0]])
                output_loc["EDT"] = loc[1]
                output_loc["prev_distance"] = loc[2]
                driver_map.append(output_loc)
            final_output["Routes"].append(driver_map)
        admin.output_map = json.dumps(final_output["Routes"])
        admin.day_started = True
        db.session.commit()
        drivers = Driver.query.filter_by(admin_id=admin_id).all()
        driver_idx = 0
        for route in final_output["Routes"]:
            for point in route:
                point["delivered"] = False
            route[0]["delivered"] = True
            drivers[driver_idx].path = json.dumps(route)
            driver_idx += 1

        db.session.commit()
        return jsonify(final_output), 200


# @app.route("/get/admin/output", methods=["GET"])  # returns the output map of the admin
# def get_admin():
#     if "admin_id" not in request.args:
#         return jsonify({"message": "Admin id not provided"})

#     admin_id = request.args.get("admin_id")

#     admin = Admin.query.get_or_404(admin_id)
#     map_data = json.loads(admin.output_map) if admin.output_map else []
#     return jsonify(map_data), 200


@app.route("/get/admin/unrouted", methods=["GET", "POST"])
def get_unrouted_points():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})
    return jsonify(
        json.loads(Admin.query.get_or_404(request.args.get("admin_id")).unrouted_points)
    )


@app.route(
    "/get/admin/drivers", methods=["GET"]
)  # returns all drivers for a particular admin
def get_drivers_for_admin():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})
    out = []

    drivers = Driver.query.filter(Driver.admin_id == request.args["admin_id"]).all()

    for driver in drivers:
        out.append({"driver_id": driver.id, "admin_id:": driver.admin_id})
    return jsonify(out)

@app.route(
    "/get/admin/output", methods=["GET"]
)  
def get_driver_routes_for_admin():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})
    out = []

    drivers = Driver.query.filter(Driver.admin_id == request.args["admin_id"]).all()

    for driver in drivers:
        out.append(json.loads(driver.path))
    return jsonify(out)


@app.route("/get/admin/input", methods=["GET"])  # returns the output map of the admin
def get_admin_input():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})

    admin_id = request.args.get("admin_id")

    admin = Admin.query.get_or_404(admin_id)
    map_data = json.loads(admin.input_map) if admin.input_map else []
    return jsonify(map_data), 200


@app.route("/get/coordinates", methods=["GET", "POST"])
def coordinates():
    # get coordinates from the dataframe and return it as a json
    if request.method == "GET":
        # TODO: what filename?
        data_df = pd.read_excel(UPLOAD_FOLDER + "input.xlsx")
        g = Geocoding(Variables.bingAPIKey, data_df)
        res = g.generate()
        return jsonify(res), 200


##############DRIVER ROUTES#####################



@app.route("/get/driver/path", methods=["GET", "POST"])
def get_driver_path():
    if "driver_id" not in request.args:
        return jsonify({"message": "Driver id not provided"})
    driver_id = request.args.get("driver_id")
    driver = Driver.query.get_or_404(driver_id)
    path = json.loads(driver.path) if driver.path else []
    return jsonify(path), 200


@app.route("/get/admins", methods=["GET", "POST"])  # returns all admins
def get_admins():
    admins = Admin.query.all()
    out = []
    for admin in admins:
        out.append(admin.id)
    return out, 200


@app.route("/get/admin/dayStarted", methods=["GET"])
def get_all_admin_daystarted():
    admins = Admin.query.all()
    admin_daystarted = {}
    for admin in admins:
        admin_daystarted[admin.id] = admin.day_started
    return jsonify(admin_daystarted), 200


@app.route("/get/drivers", methods=["GET", "POST"])  # returns all drivers
def get_drivers():
    drivers = Driver.query.all()
    out = []
    for driver in drivers:
        out.append({"driver_id":driver.id, "admin_id":driver.admin_id})
    return out, 200




@app.route("/post/driver/delivered", methods=["POST"])
def driver_delivered():
    if request.method == "POST":
        if "driver_id" not in request.get_json():
            return jsonify({"message": "Driver id not provided"})
        driver_id = request.get_json()["driver_id"]
        driver = Driver.query.get_or_404(driver_id)
        if not driver.path:
            return jsonify({"message": "No path for driver"}), 400
        path = json.loads(driver.path)
        for point in path:
            if not point["delivered"]:
                point["delivered"] = True
                break
        volume = point["volume"]
        if point["pickup"] == True:
            driver.remaining_capacity -= volume
        else:
            driver.remaining_capacity += volume

        driver.path = json.dumps(path)
        db.session.commit()
        # print("TSUFSOIFSOIFB")
        return jsonify({"message": "Delivery updated"})


@app.route("/get/driver/remainingPath", methods=["GET"])
def get_remaining_path():
    if "driver_id" not in request.args:
        return jsonify({"message": "Driver id not provided"})
    driver_id = request.args.get("driver_id")
    return jsonify(get_undelivered_points(driver_id)), 200


@app.route("/post/driver/reorder", methods=["POST"])
def reorder():
    if request.method == "POST":
        if "driver_id" not in request.get_json():
            return jsonify({"message": "Driver id not provided"})
        if "new_path" not in request.get_json():
            return jsonify({"message": "New path not provided"})

        driver = Driver.query.get_or_404(request.get_json()["driver_id"])
        new_path = request.get_json()["new_path"]
        for i in range(1, len(new_path)):
            dur = duration_between(new_path[i - 1], new_path[i])
            if dur != 0 and i < len(new_path) - 1:
                dur += 300
            new_path[i]["EDT"] = new_path[i - 1]["EDT"] + dur

        for i in range(1, len(new_path)):
            new_path[i]["prev_distance"] = distance_between(new_path[i - 1], new_path[i])

        driver.path = json.dumps(new_path)
        db.session.commit()


@app.route("/post/driver/removepoint", methods=["POST"])
def remove_point():
    if request.method == "POST":
        if "driver_id" not in request.get_json():
            return jsonify({"message": "Driver id not provided"})
        if "point" not in request.get_json():
            return jsonify({"message": "Point not provided"})

        driver = Driver.query.get_or_404(request.get_json()["driver_id"])
        path = json.loads(driver.path)
        idx_to_remove = int(request.get_json()["point"])
        path.pop(idx_to_remove)
        for i in range(idx_to_remove - 1, len(path) - 1):
            dur = duration_between(path[i], path[i + 1])
            if dur != 0 and i < len(path) - 2:
                dur += 300
            path[i + 1]["EDT"] = path[i]["EDT"] + dur

        path[idx_to_remove]["prev_distance"] = distance_between(
            path[idx_to_remove - 1], path[idx_to_remove]
        )

        driver.path = json.dumps(path)
        db.session.commit()


@app.route("/post/generateOTP", methods=["POST"])
def generate_otp():
    account_sid = Variables.twilioAccountSID
    auth_token = Variables.twilioAuthToken
    client = Client(account_sid, auth_token)
    verification = client.verify.v2.services(
        Variables.twilioSMSserviceSID
    ).verifications.create(to="+918317084914", channel="sms")
    return jsonify({"message": "OTP generated"}), 200


@app.route("/post/verifyOTP", methods=["POST"])
def verify_otp():
    if "otp" not in request.get_json():
        return jsonify({"message": "OTP not provided"})
    otp = request.get_json()["otp"]
    account_sid = Variables.twilioAccountSID
    auth_token = Variables.twilioAuthToken
    client = Client(account_sid, auth_token)
    try:
        verification_check = client.verify.v2.services(
            Variables.twilioSMSserviceSID
        ).verification_checks.create(to="+918317084914", code=otp)
        print(verification_check.status)
        if verification_check.status == "approved":
            return jsonify({"message": "OTP verified"}), 200

        else:
            return jsonify({"message": "OTP incorrect"}), 400
    except Exception as e:
        return jsonify({"Error": "Error validating code"}), 400

@app.route("/put/admin/dayEnd",methods=["PUT"])
def day_end():
    if "admin_id" not in request.args:
        return jsonify({"message":"Admin id not provided"})
    admin_id = request.args.get("admin_id")
    admin = Admin.query.get_or_404(admin_id)
    admin.day_started = False
    db.session.commit()
    return jsonify({"message":"Day ended"}),200

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        db.session.commit()
        print("LEN :", len(sys.argv))
    app.run(debug=Variables.debug, host=Variables.host, port=Variables.port)



# def add_dynamic_point
