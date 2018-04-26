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
import operator

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
import fhirclient.models.observation as observation

from dbmodels import db, Death, Concept, ConditionOccurence
db.init_app(app)


model = MortalityPredictor('models/mimic3.model.npz', 'models/mimic3.types')

@app.after_request
def set_response_headers(response):
  ''' mainly for not to cache '''

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
  prediction = []
  incrementalPredictions = []
  incremental_contributions = []

  try:
    # get icdCodes form patientID
    encounters, icdCodes = getPatientDataAndCodes(patientID)

    encounterData = []
    keys = []

    for encounter in encounters:
      encounterId = encounter["id"]
      keys.append(encounterId)
      diagnoses = [codeDict["code"] for codeDict in icdCodes[encounterId]]
      encounterData.append(diagnoses)

    #rounding_factor = 10000.0
    
    preds, contributions = model.predict_icd9(encounterData)
    prediction = round(preds * 100) if preds is not None else 'N/A'

    
    incremental_preds, incremental_contributions = model.incremental_predict_icd9(encounterData)
    incrementalPredictions = [pred for pred in list(map(lambda x: None if x is None else round(x * 100), incremental_preds)) if pred is not None]
                
  except Exception as e:
    errors.append("error")
    print(e)

  return render_template('patient.html', patientID = patientID,
    mortalityPrediction = prediction, incrementalPredictions = incrementalPredictions, incrementalContributions = incremental_contributions,
    errors = errors, keys=keys, codeDict = icdCodes, encounters = encounters)


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


@socketio.on('get observations', namespace='/')
def get_observations(message):
  observationSearch = observation.Observation.where(struct={'patient': str(message['patientId'])})
  observationBundle = observationSearch.perform(smart.server)
  observationData = {}
  if observationBundle.entry:
    for e in observationBundle.entry:
      if e.resource.encounter and e.resource.code:

        encounterId = e.resource.encounter.reference[10:]
        codes = e.resource.code.coding
        value = e.resource.valueQuantity

        if codes and encounterId:

          thisEncounterObservations = []
          c = codes[0]
          if c:
            thisObservation = {}
            thisObservation["system"] = c.system
            thisObservation["code"] = c.code
            thisObservation["name"] = c.display
            thisObservation["units"] = value.unit if value else ""
            thisObservation["value"] = value.value if value else ""
            thisEncounterObservations.append(thisObservation)
          if encounterId not in observationData:
            observationData[encounterId] = thisEncounterObservations
          else:
            observationData[encounterId].append(thisObservation)
  emit('get observations', {'observationData': observationData})

def icdToSnomed(snowmed):
  ''' Translates given snowmed code into icd9 code  '''

  # query the concept table to get corresponding conceptID to SNOWMED code
  icdCodeAndName = ConditionOccurence.query.join(Concept, Concept.concept_id==ConditionOccurence.condition_concept_id) \
        .add_columns(Concept.concept_name) \
        .filter(Concept.concept_code==snowmed) \
        .first()

  icdDict = {}
  icdDict["code"] = MortalityPredictor.parseIcd9(icdCodeAndName[0].condition_source_value)
  icdDict["name"] = icdCodeAndName[1]

  return icdDict

def getPatientDataAndCodes(patientID):

  ''' given patientID, returns encounters and codes

  encounters = [
                {
                    startDate: Date,
                    endDate: Date,
                    prediction: Number,
                    contributions: [
                        [Number, Number, ...],
                    ],
                    observations: [
                        {
                            code: String,
                            name: String,
                            units: String,
                            value: Number,
                        }
                    ],
                }
            ];

  '''

  encounterDict = {}
  codeDict = {}

  result = ()
  # search for patient's conditions
  
  conditionSearch = conditions.Condition.where(struct={'patient': patientID})
  observationSearch = observation.Observation.where(struct={'patient': patientID})

  # TODO: pagination of bundles
  conditionBundle = conditionSearch.perform(smart.server)
  # observationBundle = observationSearch.perform(smart.server)

  if conditionBundle.entry:
    # each entry's resource contains one encounter and its codes
    for e in conditionBundle.entry:
      if e.resource.encounter and e.resource.code:

        # get the encounterID and code list for an individual encounter
        encounterId = e.resource.encounter.reference[10:]
        codes = e.resource.code.coding

        if codes and encounterId:

          # if encounter already exist
          if encounterId in encounterDict:
            for c in codes:

            # append new code to collection of existing codes
              if c.code not in codeDict[encounterId]:

                # translates snowmed to icd9
                codeDict[encounterId].append(icdToSnomed(c.code))

          else:
            codeList = []
            for c in codes:
              codeList.append(icdToSnomed(c.code))
            codeDict[encounterId] = codeList

            thisEncounter = {}
            thisEncounter["id"] = encounterId
            if e.resource.onsetPeriod:
              thisEncounter["startDate"] = e.resource.onsetPeriod.start.date
              thisEncounter["endDate"] = e.resource.onsetPeriod.end.date

            encounterDict[encounterId] = thisEncounter

  # if observationBundle.entry:
  #   for e in observationBundle.entry:
  #     if e.resource.encounter and e.resource.code:

  #       encounterId = e.resource.encounter.reference[10:]
  #       codes = e.resource.code.coding
  #       value = e.resource.valueQuantity

  #       if codes and encounterId and value:
          
  #         if encounterId in encounterDict:

  #           thisEncounterObservations = []
  #           for c in codes:
  #             thisObservation = {}
  #             thisObservation["code"] = c.code
  #             thisObservation["name"] = c.display
  #             thisObservation["units"] = value.unit
  #             thisObservation["value"] = value.value
  #             thisEncounterObservations.append(thisObservation)

  #           encounterDict[encounterId]["observations"] = thisEncounterObservations

  encounters = [value for key, value in sorted(encounterDict.items(),
               key=lambda x: x[1]["startDate"])]

  return encounters, codeDict


if __name__ == "__main__":
  # app.run(host="0.0.0.0")
  socketio.run(app, host="0.0.0.0")
# use_reloader=False