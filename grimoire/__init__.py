# noinspection PySingleQuotedDocstring
''' webserver for grimoire graph data '''
from flask import Flask

from grimoire.graph_service import GraphService

app = Flask(__name__)
app.url_map.strict_slashes = False
app.config.from_object('config')

graph = GraphService()
entities = graph.get_entity_labels()
internal_labels = ['image', 'event', 'excerpt']
date_params = graph.date_params

templates = {}

from grimoire.api_graph_service import APIGraphService
api_graph = APIGraphService()

import grimoire.views
import grimoire.item_views
import grimoire.api
