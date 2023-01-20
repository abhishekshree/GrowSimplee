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
    map_id = db.Column(db.Integer)
    input_map = db.Column(db.Text)
    num_drivers = db.Column(db.Integer)
    output_map = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def get_input_map(self):
        return json.loads(self.input_map)

    def get_output_map(self):
        return json.loads(self.output_map)

    def put_input_map(self, input_map):
        self.input_map = json.dumps(input_map)

    def put_output_map(self, output_map):
        self.output_map = json.dumps(output_map)

    def __init__(
        self, id, map_id=None, input_map=None, num_drivers=None, output_map=None
    ):
        self.id = id
        self.map_id = map_id
        self.put_input_map(input_map)
        self.num_drivers = num_drivers
        self.put_output_map(output_map)

    def __repr__(self):
        return f"Admin id: {self.id}"


class Driver(db.Model):
    __tablename__ = "driver"
    id = db.Column(db.String, primary_key=True)  # admin_id + [1,num_drivers]
    name = db.Column(db.String)
    admin_id = db.Column(db.String, db.ForeignKey("admin.id"))
    map_id = db.Column(db.Integer)
    path = db.Column(db.Text)
    date = db.Column(db.DateTime)

    def get_path(self):
        return json.loads(self.path)

    def put_path(self, path):
        self.path = json.dumps(path)

    def assign_admin(self, admin_id):
        self.admin_id = admin_id

    def __init__(self, name, admin_id, map_id=None, path=None, date=None):
        self.admin_id = admin_id
        self.name = name
        self.map_id = map_id
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
    os.remove(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))

    admin=Admin.query.get_or_404(admin_id)
    admin.output_map=json.dumps(res)
    db.session.commit()


def generate_drivers(admin_id, n):
    initial_drivers = len(Driver.query.filter(Driver.id.startswith(admin_id).all()))
    if(initial_drivers<n):
        for i in range(1,1+n-initial_drivers):
            driver = Driver(id=str(admin_id)+"_"+str(initial_drivers+i), admin_id=admin_id)
            db.session.add(driver)
        db.session.commit()


@app.route("/post/input", methods=["GET", "POST"]) #takes admin id, map and number of drivers. Also updates driver db with the required number of drivers
def data():
    # get input as a dataframe and store it in data/ folder
    if request.method == "POST":
        if "file" not in request.files:
            return jsonify({"message": "No file part in the request"}), 400
        if "no_of_drivers" not in request.form:
            return jsonify({"message": "Number of drivers not specified"})
        if "admin_id" not in request.form:
            return jsonify({"message": "Admin id not received"})
        if not allowed_file(file.filename):
            return jsonify({"message": "Allowed file types are xlsx, xls, csv"}), 400
        
        admin_id = request.form["admin_id"]
        n = request.form["num_of_drivers"]

        put_input_map(admin_id=admin_id, file=request.files["file"])
        generate_drivers(admin_id=admin_id, n=n)

        # file = request.files["file"]

        # if file.filename == "":
        #     return jsonify({"message": "No file selected for uploading"}), 400

        # if file and allowed_file(file.filename):
        #     # change filename to input.extension
        #     file.filename = "input." + file.filename.rsplit(".", 1)[1].lower()
        #     file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))

        #     data_df = pd.read_excel(UPLOAD_FOLDER + file.filename)
        #     g = Geocoding(Variables.bingAPIKey, data_df)
        #     res = g.generate()
        #     # return jsonify(res), 200

        #     if "admin_id" in request.form:
        #         if "no_of_drivers" not in request.form:
        #             return jsonify({"message": "Number of drivers not specified"})
                
        #         admin_id=request.form["admin_id"]
        #         n = request.form["num_of_drivers"]
        #         admin = Admin.query.filter_by(admin_id=admin_id)


        #         Admin.query.filter_by(admin_id=request.form["admin_id"]).put_input_map(res)
        #         return
        #     else:
        #         return jsonify({"message": "Admin id not received"})

        #     return jsonify({"message": "File successfully uploaded"}), 200
        # else:
        #     return jsonify({"message": "Allowed file types are xlsx, xls, csv"}), 400


# TODO: Can run the generate just after receiving the file because /get/coordinates would not be used ever imo

@app.route("/")
def hello():
    return  ("hello")


@app.route("/get/coordinates", methods=["GET"])
def coordinates():
    # get coordinates from the dataframe and return it as a json
    if request.method == "GET":
        # TODO: what filename?
        data_df = pd.read_excel(UPLOAD_FOLDER + "input.xlsx")
        g = Geocoding(Variables.bingAPIKey, data_df)
        res = g.generate()
        return jsonify(res), 200


# db-related routes
@app.route("/post/admin/new", methods=["POST"])
def post_admin():
    # get a json and store it in the database
    if request.method == "POST":
        admin_id = str(uuid.uuid4())
        admin = Admin(id=admin_id)

        db.session.add(admin)
        db.session.commit()
        return jsonify({"message": "Admin successfully added", "id": admin_id}), 200


# @app.route("post/admin/addpoint", methods=["POST"])
# # how to store dynamic points
# def post_point():
#     if request.method == "POST":
#         if "admin_id" not in request.form:
#             return jsonify({"message": "Admin id not provided"})





@app.route("/get/admin/output", methods=["GET"])
def get_admin():
    if "admin_id" not in request.args:
        return jsonify({"message": "Admin id not provided"})

    admin_id = request.args.get("admin_id")

    admin = Admin.query.filter_by(id=admin_id).first()
    map_data = admin.get_output_map
    return jsonify(map_data), 200

@app.route("/post/driver/assign", methods=["POST"])
def assign_to_admin():
    if request.method=="POST":
        if "admin_id" not in request.form:
            return jsonify({"message": "Admin id not provided"})
        if "dirver_id" not in request.form:
            return jsonify({"message": "Driver id not provided"})
        Driver.query.filter_by(id=request.form["driver_id"]).assign_admin(request.form["admin_id"])
        return jsonify({"message" : "Driver successfully assigned to admin"})

@app.route("/post/driver/path", methods=["POST"])
def put_driver_path():
    if request.method == "POST":
        if "driver_id" not in request.form:
            return jsonify({"message": "Driver id not provided"})


@app.route("/get/driver/path", methods=["GET"])
def get_driver_path():
    if "driver_id" not in request.args:
        return jsonify({"message": "Driver id not provided"})
    return jsonify(Driver.query.filter_by(id=request.form["driver_id"]).get_path())






# @app.route("put")




if __name__ == "__main__":
    with app.app_context():
        db.session.query(Admin).delete()
        db.create_all()
        db.session.add(Admin(id=3))
        db.session.add(Admin(id=2))
        db.session.commit()
        print(Admin.query.all())
        print(len((Admin.query.filter(Admin.id.startswith(""))).all()))
    app.run(debug=Variables.debug, host=Variables.host, port=Variables.port)

