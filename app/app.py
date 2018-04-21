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

from MortalityPredictor import MortalityPredictor

app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
socketio = SocketIO(app)
# db = SQLAlchemy(app)

settings = {
  'app_id': 'MortalityPredictor',
  'api_base': 'https://ehr.hdap.gatech.edu/gt-fhir-webapp/base'
}

smart = client.FHIRClient(settings=settings)
cache = redis.Redis(host='redis', port=6379)

import fhirclient.models.patient as p
import fhirclient.models.condition as conditions

from dbmodels import db, Death, Concept, ConditionOccurence
db.init_app(app)


model = MortalityPredictor('models/mimic3.model.npz', 'models/mimic3.types')

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
  keys = []
  prediction = []
  incrementalPredictions = []
  # icdCodes kept in dictionary
  # with each encounter having a lsit of codes
  icdCodes = {}

  icdCodes = conceptSearch(patientID)

  try:
    # get icdCodes form patientID
    icdCodes = conceptSearch(patientID)
    codesAndScores = {}

    # get sorted keys from dictionary
    keys = sorted(icdCodes[0])

    encounterData = []

    for encounterId in keys:
        diagnoses = list(icdCodes[0][encounterId])
        encounterData.append(diagnoses)

    rounding_factor = 10000.0
    
    preds, contributions = model.predict_icd9(encounterData)
    prediction = round(preds * rounding_factor) / rounding_factor
    
    incremental_preds, incremental_contributions = model.incremental_predict_icd9(encounterData)
    incrementalPredictions = list(map(lambda x: round(x * rounding_factor) / rounding_factor, incremental_preds))
    
    # TODO: This is only valid for the last prediction. Use incremental_contributions to get the contribution
    # scores for the previous steps
    # Zip each code with its corresponding contribution score
    for i, encounterId in enumerate(keys):
        codesAndScores[encounterId] = []
        for j, code in enumerate(encounterData[i]):
            score = round(contributions[i][j] * rounding_factor) / rounding_factor
            codesAndScores[encounterId].append((code, score))
                
  except Exception as e:
    errors.append("error")
    print(e)

  return render_template('patient.html', patientID = patientID,
    mortalityPrediction = prediction, incrementalPredictions = incrementalPredictions,
    errors = errors, codes=codesAndScores, keys=keys, period=icdCodes[1])


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

  icd = ConditionOccurence.query.join(Concept, Concept.concept_id==ConditionOccurence.condition_concept_id) \
        .filter(Concept.concept_code==snowmed) \
        .first().condition_source_value

  return icd

def conceptSearch(patientID):

  ''' given patientID, returns a dictionary of icd9Codes
      ordered by encounters '''

  encounterCodesDict = {}
  encounterPeriodDict = {}

  result = []
  # search for patient's conditions
  search = conditions.Condition.where(struct={'patient': patientID})

  # TODO: pagination of bundles
  bundle = search.perform(smart.server)

  if bundle.entry:
    # each entry's resource contains one encounter and its codes
    for e in bundle.entry:


      if e.resource.encounter and e.resource.code:

        # get the encounterID and code list for an individual encounter
        encounter = e.resource.encounter.reference[10:]
        codes = e.resource.code.coding
        period = [e.resource.onsetPeriod.start, e.resource.onsetPeriod.end]

        if codes and encounter:

          # if encounter already exist
          if encounter in encounterCodesDict:

            for c in codes:

            # append new code to collection of existing codes
              if c.code not in encounterCodesDict[encounter]:

                # translates snowmed to icd9
                encounterCodesDict[encounter].add(icdSearch(c.code))

          else:

            # creat new set collection
            # set ensures no duplicates
            codeList = set()
            for c in codes:
              codeList.add(icdSearch(c.code))
            encounterCodesDict[encounter] = codeList
            if period:
              encounterPeriodDict[encounter] = period
  result = [encounterCodesDict, encounterPeriodDict]


  return(result)


if __name__ == "__main__":
  # app.run(host="0.0.0.0")
  socketio.run(app, host="0.0.0.0")
