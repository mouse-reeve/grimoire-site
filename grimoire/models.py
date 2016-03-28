''' Temporospatial database (Postgres) '''
from flask.ext.sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Temporospatial(db.Model):
    ''' time/space references to Neo4j nodes '''
    __tablename__ = 'temporospatial'

    # Metadata
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, server_default=db.func.now())
    updated = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    # Location
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    location_precision = db.Column(db.Enum('exact',
                                           'city',
                                           'state',
                                           'country',
                                           'continent', name='location_precision'), nullable=False)
    location_name = db.Column(db.String(140), nullable=False)

    # Date
    date = db.Column(db.DateTime, nullable=False)
    date_precision = db.Column(db.Enum('exact',
                                       'day',
                                       'month',
                                       'year',
                                       'decade',
                                       'century', name='date_precision'), nullable=False)

    # Content
    node_id = db.Column(db.Integer, nullable=False)
    event_type = db.Column(db.Enum('publication',
                                   'birth',
                                   'death',
                                   'coronation',
                                   'edition',
                                   'law',
                                   'trial',
                                   'other', name='event_type'), nullable=False)
    description = db.Column(db.Text, nullable=False)

    def __init__(self, latitude, longitude, loc_precision,
                 loc_name, date, date_precision, node, event_type, description):
        ''' Create a temporospatial node '''
        self.latitude = latitude
        self.longitude = longitude
        self.location_precision = loc_precision
        self.location_name = loc_name

        self.date = date
        self.date_precision = date_precision

        self.node_id = node
        self.event_type = event_type
        self.description = description

    def serialize(self):
        ''' json-exportable data '''
        data = {
            'latitude': self.latitude
        }

        return data


