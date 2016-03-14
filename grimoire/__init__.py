''' webserver for grimoire graph data '''
from flask import Flask

from grimoire.graph_service import GraphService

app = Flask(__name__)
app.config.from_object('config')
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/temporospatial'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

graph = GraphService()
entities = graph.get_entity_labels()

import grimoire.models as temporospatial
temporospatial.db.init_app(app)

import grimoire.views
import grimoire.item_views
