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



UPLOAD_FOLDER = Variables.uploadFolder
ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}

db = SQLAlchemy()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SQLALCHEMY_DATABASE_URI"] = Variables.databaseURI

db.init_app(app)
cors = CORS(app)



class Admin(db.Model):
    __tablename__ = "admin"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    input_map = db.Column(db.Text, default="[]")
    num_drivers = db.Column(db.Integer, default=0)
    output_map = db.Column(db.Text, default="[]")
    # date = db.Column(db.DateTime, default=datetime.utcnow)
    dynamic_points = db.Column(db.Text, default="[]")

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
    inital_drivers = Driver.query.filter(Driver.id.startswith(admin_id)).all()
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
        n = int(form["no_of_drivers"])

        put_input_map(admin_id=admin_id, file=file)
        generate_drivers(admin_id=admin_id, n=n)

        return {"message": "Input successful", "map": Admin.query.get_or_404(admin_id).input_map}


@app.route(
    "/post/admin/dynamicpoint", methods=["POST"]
)  # Allows admin to add a dynamic point
def add_dynamic_point():
    if request.method == "POST":
        if "admin_id" not in request.get_json():
            return jsonify({"message": "Admin id not received"})

        if "data" not in request.get_json():
            return jsonify({"message": "Data not received"})

        if "address" not in request.get_json()["data"]:
            return jsonify({"message": "Address not received"})

        admin_id = request.get_json()["admin_id"]
        admin = Admin.query.get_or_404(admin_id)
        print(admin_id)

        data = request.get_json()["data"]
        address = pd.read_json(json.dumps([data]))
        result = Geocoding(Variables.bingAPIKey, address).generate()

        point = data
        point["latitude"] = result[0]["latitude"]
        point["longitude"] = result[0]["longitude"]

        d_points = None
        if not admin.dynamic_points:
            d_points = []
        else:
            d_points = json.loads(admin.dynamic_points)
        d_points.append(point)

        admin.dynamic_points = json.dumps(d_points)

        db.session.commit()
        return jsonify({"message": "Point successfully added"})


@app.route("/get/admin/dynamicpoints")  # returns the dynamic points added by an admin
def get_dynamic_points():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not specified"})
    admin_id = request.args.get("admin_id")
    admin = Admin.query.get_or_404(admin_id)
    # dynamic_point=json.loads(admin.dynamic_points)
    # print(dynamic_point)
    return (
        jsonify(json.loads(admin.dynamic_points))
        if admin.dynamic_points
        else jsonify([])
    )


@app.route("/")
def hello():
    return "hello"


@app.route("/get/coordinates", methods=["GET", "POST"])
def coordinates():
    # get coordinates from the dataframe and return it as a json
    if request.method == "GET":
        # TODO: what filename?
        data_df = pd.read_excel(UPLOAD_FOLDER + "input.xlsx")
        g = Geocoding(Variables.bingAPIKey, data_df)
        res = g.generate()
        return jsonify(res), 200


@app.route("/post/admin/start", methods=["POST"])
def gen_map():
    if request.method == "POST":
        if "admin_id" not in request.get_json():
            return jsonify({"message": "Admin id not received"})
        if "hub_node" not in request.get_json():
            return jsonify({"message": "Hub node not received"})

        admin_id = request.get_json()["admin_id"]
        admin = Admin.query.get_or_404(admin_id)
        # print(admin_id)
        input_map = json.loads(admin.input_map)
        num_drivers = int(admin.num_drivers)
        # print(input_map)
        idx_map = []
        for i in range(0, len(input_map)):
            idx_map.append({
                "latitude": input_map[i]["latitude"],
                "longitude": input_map[i]["longitude"],
            })
        
        # num_drivers = request.args.get("num_drivers")
        hub_node = int(request.get_json()["hub_node"])
        print("generate path")
        pg = PathGen(idx_map, num_drivers, hub_node)
        pg.remove_coords()
        print("Enter output")
        output_map = pg.get_output_map()

        print("output map", output_map)
        # return jsonify(output_map)
        
        final_output = []
        for driver_path in output_map:
            driver_map = []
            for loc in driver_path:
                driver_map.append(input_map[loc])
            final_output.append(driver_map)
        admin.output_map = json.dumps(final_output)

        drivers = Driver.query.filter_by(admin_id=admin_id).all()
        for route, driver in zip (final_output, drivers):
                for point in route: 
                    point["delivered"] = False
                driver.path = json.dumps(route)
            
        db.session.commit()
        return jsonify(final_output), 200


# db-related routes
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


@app.route("/get/admin/output", methods=["GET"])  # returns the output map of the admin
def get_admin():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})

    admin_id = request.args.get("admin_id")

    admin = Admin.query.get_or_404(admin_id)
    map_data = admin.output_map if admin.output_map else "[]"
    return jsonify(map_data), 200


@app.route("/get/admin/input", methods=["GET"])  # returns the output map of the admin
def get_admin_input():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})

    admin_id = request.args.get("admin_id")

    admin = Admin.query.get_or_404(admin_id)
    map_data = admin.input_map if admin.input_map else "[]"
    return jsonify(map_data), 200

@app.route("/get/driver/path", methods=["GET", "POST"])
def get_driver_path():
    if "driver_id" not in request.args:
        return jsonify({"message": "Driver id not provided"})
    driver_id = request.args.get("driver_id")
    driver = Driver.query.get_or_404(driver_id)
    path = driver.path if driver.path else "[]"
    return jsonify(path), 200

@app.route("/get/admins", methods=["GET", "POST"])  # returns all admins
def get_admins():
    admins = Admin.query.all()
    out = ""
    for admin in admins:
        out += f"Admin ID:\t{admin.id}\n"
    return out, 200


@app.route("/get/drivers", methods=["GET", "POST"])  # returns all drivers
def get_drivers():
    drivers = Driver.query.all()
    out = ""
    for driver in drivers:
        out += f"Driver ID:\t{driver.id}\tAdmin ID:\t{driver.admin_id}\n"
    return out, 200


@app.route(
    "/get/admin/drivers", methods=["GET"]
)  # returns all drivers for a particular admin
def get_drivers_for_admin():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})
    out = ""

    drivers = Driver.query.filter(Driver.admin_id == request.args["admin_id"]).all()
    for driver in drivers:
        out += ("Driver id:\t" + driver.id + "\t Admin:\t" + driver.admin_id) + "\n"
    return out


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        db.session.commit()
    app.run(debug=Variables.debug, host=Variables.host, port=Variables.port)
