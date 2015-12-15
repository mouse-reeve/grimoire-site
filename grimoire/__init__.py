''' webserver for grimoire graph data '''
from flask import Flask
app = Flask(__name__)

import grimoire.views
