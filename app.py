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

    def __init__(self, name, admin_id, map_id=None, path=None, date=None):
        self.admin_id = admin_id
        self.name = name
        self.map_id = map_id
        self.put_path(path)
        self.date = date

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/post/data", methods=["GET", "POST"])
def data():
    # get input as a dataframe and store it in data/ folder
    if request.method == "POST":
        if "file" not in request.files:
            return jsonify({"message": "No file part in the request"}), 400

        file = request.files["file"]

        if file.filename == "":
            return jsonify({"message": "No file selected for uploading"}), 400

        if file and allowed_file(file.filename):
            # change filename to input.extension
            file.filename = "input." + file.filename.rsplit(".", 1)[1].lower()
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
            return jsonify({"message": "File successfully uploaded"}), 200
        else:
            return jsonify({"message": "Allowed file types are xlsx, xls, csv"}), 400


# TODO: Can run the generate just after receiving the file because /get/coordinates would not be used ever imo


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


@app.route("/get/admin")
def get_admin():
    admin_id = request.args.get("id")
    admin = Admin.query.filter_by(id=admin_id).first()
    return jsonify(admin), 200


if __name__ == "__main__":
    app.run(debug=Variables.debug, host=Variables.host, port=Variables.port)
