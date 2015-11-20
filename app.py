''' webserver for grimoire graph data '''
from flask import Flask, render_template
from graph_service import GraphService

app = Flask(__name__)
graph = GraphService()


# ----- routes
@app.route('/', methods=['GET'])
def index():
    ''' render the basic template for angular '''
    return render_template('index.html')


if __name__ == '__main__':
    app.debug = True
    app.run(port=4080)
