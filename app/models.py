from app import db

class Death(db.Model):
  __tablename__ = 'death'

  person_id = db.Column(db.Integer, primary_key=True, nullable=False)
  death_date = db.Column(db.Date, nullable=False)
  death_type_concept_id = db.Column(db.Integer, nullable=False)
  cause_concept_id = db.Column(db.Integer)
  cause_source_value = db.Column(db.String(50))
  cause_source_concept_id = db.Column(db.Integer)
  x_srcid = db.Column(db.Integer)
  x_srcfile = db.Column(db.String(20))
  x_createdate = db.Column(db.Date)
  x_updatedate = db.Column(db.Date)

  def __init__(self, death_date, death_type_concept_id, 
    cause_concept_id=None, cause_source_value=None, cause_source_concept_id=None,
    x_srcid=None, x_srcfile=None, x_createdate=None, x_updatedate=None):
        self.death_date = death_date
        self.death_type_concept_id = death_type_concept_id
        self.cause_concept_id = cause_concept_id
        self.cause_source_value = cause_source_value
        self.cause_source_concept_id = cause_source_concept_id
        self.x_srcid=x_srcid,
        self.x_srcfile=x_srcfile
        self.x_createdate=x_createdate
        self.x_updatedate=x_updatedate