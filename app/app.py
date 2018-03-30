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
  ''' mainly for not to cache '''
  print('hello')
  response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
  response.headers['Pragma'] = 'no-cache'
  response.headers['Expires'] = '0'
  return response

@app.route('/', methods=['GET'])
def index():
  ''' index page. links to chart and chart2 '''

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
  '''displays a list of patient when name is querried '''

  errors = []
  patients = []

  # if a name is entered 
  if request.method == 'POST':

    try:

      # form query parameter to uppercase for FHIR
      name = request.form['name'].upper()

      # search for possible patients
      search = p.Patient.where(struct={'name': name})

      # TODO: pagination for patient bundle
      bundle = search.perform(smart.server)

      # add to list of patients for display
      patients.extend(bundle.entry)

    except:

      errors.append(
        "Error occured trying to find {0}.".format(name)
        )

  return render_template('chart.html', errors = errors, patients=patients)


@app.route('/patient/<patientID>', methods=['GET'])
def patient(patientID):
  ''' handles individual patient's list of code '''

  errors = []

  # icdCodes kept in dictionary
  # with each visit having a lsit of codes
  icdCodes = {}

  try:
    # get icdCodes form patientID
    icdCodes = conceptSearch(patientID)

    # get sorted keys from dictionary
    keys = sorted(icdCodes)
  except:
    errors.append("error")

  return render_template('patient.html', patientID = patientID, errors = errors, codes=icdCodes, keys=keys)


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


def icdSearch(snowmed):
  ''' Translates given snowmed code into icd9 code  '''

  # query the concept table to get corresponding conceptID to SNOWMED code
  concept = Concept.query.filter_by(concept_code=snowmed).limit(1).all()

  # get the ID
  conceptID = concept[0].concept_id

  # query condition table for icd9 code corresponding to conceptID
  icd = ConditionOccurence.query.filter_by(condition_concept_id=conceptID).limit(1).all()
  
  # get the icd9Code
  result = icd[0].condition_source_value

  return result

def conceptSearch(patientID):

  ''' given patientID, returns a dictionary of icd9Codes 
      ordered by visits '''

  result = {}

  # search for patient's conditions
  search = conditions.Condition.where(struct={'patient': patientID})
  
  # TODO: pagination of bundles
  bundle = search.perform(smart.server)

  if bundle.entry:
    # each entry's resource contains one visit and its codes
    for e in bundle.entry:


      if e.resource.encounter and e.resource.code:
        
        # get the encounterID and code list for an individual visit
        encounter = e.resource.encounter.reference[10:]
        codes = e.resource.code.coding

        if codes and encounter:

          # if visits already exist
          if encounter in result:

            for c in codes:

            # append new code to collection of existing codes
              if c.code not in result[encounter]:

                # translates snowmed to icd9
                result[encounter].add(icdSearch(c.code))

          else:

            # creat new set collection
            # set ensures no duplicates
            codeList = set()
            for c in codes:
              codeList.add(icdSearch(c.code))
            result[encounter] = codeList


  return(result)
  

if __name__ == "__main__":
  # app.run(host="0.0.0.0")
  socketio.run(app, host="0.0.0.0")
