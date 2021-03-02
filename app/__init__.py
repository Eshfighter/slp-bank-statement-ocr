from flask import Flask, request
from flask_cors import CORS
from flask_cdn import CDN
import os
import json
from app.routes import process_pdf

# Define WSGI object
app = Flask(__name__)
cdn = CDN()
cdn.init_app(app)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configurations
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["BASE_DIR"] = BASE_DIR
app.config["PDF_PATH"] = os.path.join(BASE_DIR, 'assets', 'temp_file')


@app.route("/pdf", methods=['POST'])
def pdf():
    # Construct payload
    payload = {
        'bankName': request.json['bankName'],
        'fileContent': request.json['fileContent'],
        'topOrg': '',
        'fileId': ''
    }
    return json.dumps(process_pdf.start(payload), ensure_ascii=False), 200
