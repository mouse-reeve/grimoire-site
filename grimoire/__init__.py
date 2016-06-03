''' webserver for grimoire graph data '''
from flask import Flask
import os

from grimoire.graph_service import GraphService

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config.from_object('config')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['PSQL_URI']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

graph = GraphService()
entities = graph.get_entity_labels()
date_params = graph.date_params

templates = {}

import grimoire.models as temporospatial
temporospatial.db.init_app(app)

import grimoire.views
import grimoire.item_views
