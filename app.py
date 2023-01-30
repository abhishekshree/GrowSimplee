from datetime import datetime
from config.config import Variables
import pandas as pd
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
    output_map = db.Column(db.Text, default="[]")
    # date = db.Column(db.DateTime, default=datetime.utcnow)
    dynamic_point = db.Column(db.Text)
    unrouted_points = db.Column(db.Text, default= '[]')

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



def get_undelivered_points(driver_id):
    driver = Driver.query.get_or_404(driver_id)
    path = json.loads(driver.path)
    undelivered_points = []
    for point in path:
        if point["delivered"] == False:
            undelivered_points.append(point)
    return undelivered_points

def get_geocoding_for(address):
    g = geocoder.bing(address, key=Variables.bingAPIKey)
    return g.latlng


def distance_between(point1, point2):
    long1 = point1["longitude"]
    long2 = point2["longitude"]
    lat1 = point1["latitude"]
    lat2 = point2["latitude"]

    r= requests.get(f"http://router.project-osrm.org/table/v1/driving/{long1},{lat1};{long2},{lat2}", params = {"annotations":"distance,duration"})
    r = r.json()
    return r["distances"][0][1]  


def duration_between(point1, point2):
    long1 = point1["longitude"]
    long2 = point2["longitude"]
    lat1 = point1["latitude"]
    lat2 = point2["latitude"]

    r= requests.get(f"http://router.project-osrm.org/table/v1/driving/{long1},{lat1};{long2},{lat2}", params = {"annotations":"distance,duration"})
    r = r.json()
    return r["durations"][0][1]
   


def insert_dynamic_points(admin_id):
    def cost(dist,time):
        return 0.5*dist + 0.5*time

    admin = Admin.query.get_or_404(admin_id)
    dynamic_point = json.loads(admin.dynamic_point)

    admin.input_map = json.dumps(json.loads(admin.input_map).append(dynamic_point))

    drivers =Driver.query.filter(Driver.admin_id ==admin_id).all()
    # undelivered_routes=[]
    # for driver in drivers:
    #     undelivered_routes.append(get_undelivered_points(driver.id))

    routes = []
    for driver in drivers:
        routes.append(json.loads(driver.path))

    min_cost = 1e9

    route_idx=-1
    point_idx=-1

    
    for k, route in enumerate(routes): 
        for i, point in enumerate(route[:-1]):
            if(point["delivered"] == True):
                continue
            next_point = route[i+1]
            curr_dist = distance_between(point, dynamic_point) + distance_between(dynamic_point, next_point)- distance_between(point, next_point)
            curr_time = 0
            extra_time = duration_between(point, dynamic_point) + duration_between(dynamic_point, next_point)- duration_between(point, next_point)
            curr_time = extra_time #TODO: ask about the metric for time like what is lasttime, i think arpit's algo tries to take into account the time take for subsequest deliveries if the dynamic deilvery is done but that info is not available so makes no sense

            curr_cost = cost(curr_dist, curr_time)
            if (curr_cost<min_cost):
                min_cost = curr_cost
                route_idx = k
                point_idx = i
    
    dynamic_point["delivered"] = False
    driver = Driver.query.get_or_404(route_idx+1) #driver id is 1 indexed
    new_path = driver.path
    new_path.insert(point_idx+1, dynamic_point)
    driver.path = json.dumps(new_path)

    db.session.commit()
    



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
        driver = Driver(
            id=str(admin_id) + "_" + str(i), admin_id=admin_id
        )
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
        # return jsonify({"message": "Admin successfully added", "id": admin_id}), 200




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
        if (len(sys.argv)>1):
            print("In API not working mode")
            preloaded = pd.read_excel("Geocode.xlsx")
            preloaded=preloaded.to_dict()
            admin.input_map = json.dumps(preloaded)
            return jsonify({"message": "Input successful", "map": Admin.query.get_or_404(admin_id).input_map, "debug":True})


        put_input_map(admin_id=admin_id, file=file)
        generate_drivers(admin_id=admin_id, n=n)

        return jsonify({"message": "Input successful", "map": json.loads(Admin.query.get_or_404(admin_id).input_map)})


@app.route(
    "/post/admin/dynamicpoint", methods=["POST"]
)  # Allows admin to add a dynamic point
def add_dynamic_point():
    if request.method == "POST":
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

        admin_id = request.get_json()["admin_id"]
        admin = Admin.query.get_or_404(admin_id)
        print(admin_id)

        address = request.get_json()["address"]
        location = request.get_json()["location"]
        awb = request.get_json()["awb"]
        name = request.get_json()["name"]
        product_id = request.get_json()["product_id"]

        latitude, longitude = get_geocoding_for(address)
        
        # address = pd.read_json(json.dumps([data]))
        # result = Geocoding(Variables.bingAPIKey, address).generate()

        point = {
            "address": address,
            "location": location,
            "awb": awb,
            "name": name,
            "product_id": product_id,
            "latitude": latitude,
            "longitude": longitude
        }

        # Append the dynamic points to a list not a single dynamic point
        admin.dynamic_point = json.dumps(point)       
        db.session.commit()

        insert_dynamic_points(admin_id)
        db.session.commit()
        return jsonify({"message": "Point successfully added"})


@app.route("/get/admin/dynamicpoint")  # returns the dynamic points added by an admin
def get_dynamic_point():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not specified"})
    admin_id = request.args.get("admin_id")
    admin = Admin.query.get_or_404(admin_id)
    
    return (
        jsonify(json.loads(admin.dynamic_point))
        if admin.dynamic_point
        else jsonify([])
    )


@app.route("/")
def hello():
    return "LEN:   "+str(len(sys.argv))


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
        # print(input_map)
        idx_map = []
        for i in range(0, len(input_map)):
            idx_map.append({
                "latitude": input_map[i]["latitude"],
                "longitude": input_map[i]["longitude"],
            })
        
        hub_node = int(request.get_json()["hub_node"])
        # print("generate path")
        pg = PathGen(idx_map, num_drivers, hub_node)
        pg.remove_coords()
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
                driver_map.append(input_map[loc])
            final_output["Routes"].append(driver_map)
        admin.output_map = json.dumps(final_output["Routes"])

        drivers = Driver.query.filter_by(admin_id=admin_id).all()
        for route, driver in zip (final_output["Routes"], drivers):
                for point in route: 
                    point["delivered"] = False
                driver.path = json.dumps(route)
            
        db.session.commit()
        return jsonify(final_output), 200

@app.route("/get/admin/output", methods=["GET"])  # returns the output map of the admin
def get_admin():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})

    admin_id = request.args.get("admin_id")

    admin = Admin.query.get_or_404(admin_id)
    map_data = json.loads(admin.output_map) if admin.output_map else []
    return jsonify(map_data), 200

@app.route("/get/admin/unrouted", methods=["GET", "POST"])  
def get_unrouted_points():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})
    return jsonify(json.loads(Admin.query.get_or_404(request.args.get("admin_id")).unrouted_points))


@app.route(
    "/get/admin/drivers", methods=["GET"]
)  # returns all drivers for a particular admin
def get_drivers_for_admin():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})
    out = []

    drivers = Driver.query.filter(Driver.admin_id == request.args["admin_id"]).all()
    ## TODO: improve the format of this output
    for driver in drivers:
        out.append("Driver id:\t" + driver.id + "\t Admin:\t" + driver.admin_id + "\n")
    return out


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

@app.route(
    "/get/admin/dayStarted", methods=["GET"]
)
def get_all_admin_daystarted():
    admins = Admin.query.all()
    admin_daystarted = {}
    for admin in admins:
        if(len(eval(admin.output_map)) > 0):
            admin_daystarted[admin.id] = True
        else:
            admin_daystarted[admin.id] = False
    return jsonify(admin_daystarted), 200

@app.route("/get/drivers", methods=["GET", "POST"])  # returns all drivers
def get_drivers():
    drivers = Driver.query.all()
    out = ""
    for driver in drivers:
        out += f"Driver ID:\t{driver.id}\tAdmin ID:\t{driver.admin_id}\n"
    return out, 200

##TODO: ye kya baat hui
@app.route("/post/driver/delivered", methods=["POST"])
def driver_delivered():
    if request.method =="POST":
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
        driver.path = json.dumps(path)
        db.session.commit()
        # print("TSUFSOIFSOIFB")
        return jsonify({"message":"Delivery updated"})

@app.route("/get/driver/remainingPath", methods=["GET"])
def get_remaining_path():
    if "driver_id" not in request.args:
        return jsonify({"message": "Driver id not provided"})
    driver_id = request.args.get("driver_id")
    return jsonify(get_undelivered_points(driver_id)), 200

@app.route("/post/driver/reorder", methods=["POST"])
def reorder():
    if requests.method=="POST":
        if "driver_id" not in request.get_json():
            return jsonify({"message": "Driver id not provided"})
        if "new_path" not in request.get_json():
            return jsonify({"message": "New path not provided"})
        
        driver = Driver.query.get_or_404(request.get_json()["driver_id"])
        driver.path = json.dumps(request.get_json()["new_path"])
        db.session.commit()

@app.route("/post/driver/removepoint", methods=["POST"])
def remove_point():
    if requests.method == "POST":
        if "driver_id" not in request.get_json():
            return jsonify({"message": "Driver id not provided"})
        if "point" not in request.get_json():
            return jsonify({"message": "Point not provided"})
        
        driver = Driver.query.get_or_404(request.get_json()["driver_id"])
        path = json.loads(driver.path)
        path.pop(int(request.get_json()["point"]))
        driver.path = json.dumps(path)
        db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        db.session.commit()
        print("LEN :",len(sys.argv))
    app.run(debug=Variables.debug, host=Variables.host, port=Variables.port)


# def add_dynamic_point