from config.config import Variables
import pandas as pd
from location.geocoding import Geocoding
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import os


# example for location module
# data_df = pd.read_excel("data/bangalore_dispatch_address_finals.xlsx")
# g = Geocoding(Variables.bingAPIKey, data_df)

# res = g.generate()


UPLOAD_FOLDER = Variables.uploadFolder
ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv"}


app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


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


if __name__ == "__main__":
    app.run(debug=Variables.debug, host=Variables.host, port=Variables.port)
