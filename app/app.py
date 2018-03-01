import os

import redis
from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

cache = redis.Redis(host='redis', port=6379)

from models import *


@app.route('/')
def index():
    print(os.environ['DBUSER'])
    deaths = Death.query.limit(10).all()
    return render_template('index.html', deaths=deaths)

if __name__ == "__main__":
    app.run(host="0.0.0.0")