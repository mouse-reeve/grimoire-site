''' webserver for grimoire graph data '''
from flask import Flask, render_template
from graph_service import GraphService

app = Flask(__name__)
graph = GraphService()


# ----- routes
@app.route('/', methods=['GET'])
def index():
    ''' render the basic template for angular '''
    data = graph.get_all('grimoire')
    grimoires = []
    for g in data['nodes']:
        g = g['properties']
        if 'year' in g and g['year']:
            date = g['year']
        elif 'decade' in g and g['decade']:
            date = '%ss' % g['decade']
        elif 'century' in g and g['century']:
            try:
                cent = int(g['century'][:-2])
                date = '%dth century' % (cent + 1)
            except ValueError:
                date = '%ss' % g['century']
        else:
            date = ''

        grimoires.append({
            'uid': g['uid'],
            'identifier': g['identifier'],
            'date': date
        })
        grimoires = sorted(grimoires, key=lambda g: g['identifier'])
    return render_template('home.html', grimoires=grimoires)


@app.route('/<label>/<uid>', methods=['GET'])
def item(label, uid):
    ''' generic page for an item '''
    #TODO: error handling, sanitization
    data = graph.get_node(uid)
    return render_template('item.html', data=data)


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=4080)
