from datetime import datetime
from config.config import Variables
import pandas as pd
from location.geocoding import Geocoding
from flask import Flask, request, jsonify
import os
from flask_sqlalchemy import SQLAlchemy
import uuid
import json


UPLOAD_FOLDER = Variables.uploadFolder
ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}

db = SQLAlchemy()

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SQLALCHEMY_DATABASE_URI"] = Variables.databaseURI

db.init_app(app)


class Admin(db.Model):
    __tablename__ = "admin"
    id = db.Column(db.String, primary_key=True)
    input_map = db.Column(db.Text)
    num_drivers = db.Column(db.Integer)
    output_map = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    dynamic_points = db.Column(db.Text)

    def get_input_map(self):
        return json.loads(self.input_map)

    def get_output_map(self):
        return json.loads(self.output_map)

    def put_input_map(self, input_map):
        self.input_map = json.dumps(input_map)

    def put_output_map(self, output_map):
        self.output_map = json.dumps(output_map)

    def __init__(
        self,
        id,
        input_map=None,
        num_drivers=None,
        output_map=None,
        dynamic_points=None,
    ):
        self.id = id
        self.put_input_map(input_map)
        self.num_drivers = num_drivers
        self.put_output_map(output_map)
        self.dynamic_points = dynamic_points

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
    initial_drivers = len(Driver.query.filter(Driver.id.startswith(admin_id)).all())
    if initial_drivers < n:
        for i in range(1, 1 + n + initial_drivers):
            driver = Driver(
                id=str(admin_id) + "_" + str(initial_drivers + i), admin_id=admin_id
            )
            db.session.add(driver)
        db.session.commit()


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

        return {"message": "Input successful"}


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


# db-related routes
@app.route("/post/admin/new", methods=["POST"])  # creates a new admin
def post_admin():
    # get a json and store it in the database
    if request.method == "POST":
        admin_id = str(uuid.uuid4())
        admin = Admin(id=admin_id)

        db.session.add(admin)
        db.session.commit()
        return jsonify({"message": "Admin successfully added", "id": admin_id}), 200


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
