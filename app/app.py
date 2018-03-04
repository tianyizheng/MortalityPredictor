import os

import redis
from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from fhirclient import client

app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

settings = {
    'app_id': 'MortalityPredictor',
    'api_base': 'http://ehr.hdap.gatech.edu:8080/gt-fhir-webapp/base'
}
smart = client.FHIRClient(settings=settings)
cache = redis.Redis(host='redis', port=6379)
import fhirclient.models.patient as p
from models import *


@app.route('/')
def index():
    # deaths = Death.query.limit(10).all()
    # return render_template('index.html', deaths=deaths)
    search = p.Patient.where(struct={'_id': '1'})
    patients = search.perform_resources(smart.server)
    return render_template('chart.html', patients=patients)

if __name__ == "__main__":
    app.run(host="0.0.0.0")