import os

import redis
from flask import Flask, request, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from fhirclient import client

from flask_socketio import SocketIO, emit

from flask import make_response
from functools import wraps, update_wrapper
from datetime import datetime

app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
socketio = SocketIO(app)
# db = SQLAlchemy(app)

settings = {
  'app_id': 'MortalityPredictor',
  'api_base': 'http://ehr.hdap.gatech.edu:8080/gt-fhir-webapp/base'
}

smart = client.FHIRClient(settings=settings)
cache = redis.Redis(host='redis', port=6379)

import fhirclient.models.patient as p
import fhirclient.models.condition as conditions

from dbmodels import db, Death, Concept, ConditionOccurence
db.init_app(app)

@app.after_request
def set_response_headers(response):
  print('hello')
  response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
  response.headers['Pragma'] = 'no-cache'
  response.headers['Expires'] = '0'
  return response

@app.route('/', methods=['GET'])
def index():
  errors = []
  deaths = {}
  try:
    deaths = Death.query.limit(10).all()
  except:
    errors.append(
      "Not connected to database")
  return render_template('index.html',errors = errors, deaths=deaths)

@app.route('/chart', methods=['GET', 'POST'])
def chart():
  errors = []
  patients = []
  if request.method == 'POST':
    try:
      name = request.form['name'].upper()
      search = p.Patient.where(struct={'name': name})
      bundle = search.perform(smart.server)
      patients.extend(bundle.entry)
    except:
      errors.append(
        "Error occured trying to find {0}.".format(name)
        )
  return render_template('chart.html', errors = errors, patients=patients)

@app.route('/patient/<patientID>', methods=['GET'])
def patient(patientID):
  errors = []
  icdCodes = []
  try:
    icdCodes = icdSearch(patientID)
  except:
    errors.append("error")
  return render_template('patient.html', errors = errors, codes=icdCodes)

@app.route('/chart2', methods=['GET'])
def chart2():
  return render_template('chart2.html')


@socketio.on('connect', namespace='/')
def handle_message():
    print('user connected', request.sid)

@socketio.on('get patient', namespace='/')
def handle_message(message):
  search = p.Patient.where(struct={'name': message['name'].upper()})
  patients = search.perform_resources(smart.server)
  data = []
  for patient in patients:
    d = {}
    d['birthdate'] = int(patient.birthDate.date.strftime('%s'))

    name = 'N/A'
    if len(patient.name) > 0:
      name = ' '.join(patient.name[0].given) + ' ' + ' '.join(patient.name[0].family)
    d['name'] = name

    data.append(d)

  emit('patient data', data)

def icdSearch(patientID):
  result = []
  codes = conceptSearch(patientID)
  for c in codes:
    concept = Concept.query.filter_by(concept_code=c).limit(1).all()
    conceptID = concept[0].concept_id
    icd = ConditionOccurence.query.filter_by(condition_concept_id=conceptID).limit(1).all()
    result.append(icd[0].condition_source_value)
  return result

def conceptSearch(patientID):
  codeList = set()
  search = conditions.Condition.where(struct={'patient': patientID})
  bundle = search.perform(smart.server)
  if bundle.entry:
    for e in bundle.entry:
      if e.resource.code:
        codes = e.resource.code.coding
        if codes:
          for c in codes:
            codeList.add(c.code)
  return(codeList)
  

if __name__ == "__main__":
  # app.run(host="0.0.0.0")
  socketio.run(app, host="0.0.0.0")
