import os

import redis
from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

#cache = redis.Redis(host='redis', port=6379)

from models import *


from flask import make_response
from functools import wraps, update_wrapper
from datetime import datetime


@app.after_request
def set_response_headers(response):
    print('hello')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    print(os.environ['DBUSER'])
    deaths = Death.query.limit(10).all()
    return render_template('index.html', deaths=deaths)

@app.route('/chart')
def chart():
    print(os.environ['DBUSER'])
    deaths = Death.query.limit(10).all()
    return render_template('chart.html', deaths=deaths)

if __name__ == "__main__":
    app.run(host="0.0.0.0")