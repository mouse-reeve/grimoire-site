''' webserver for grimoire graph data '''
from flask import Flask, render_template
from graph_service import GraphService
import logging
import re

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
    return render_template('home.html', grimoires=grimoires, title='Grimoire Metadata')


@app.route('/index', methods=['GET'])
def content_index():
    ''' list everything available by category '''
    data = []
    for label in graph.get_labels():
        data.append({
            'label': label,
            'nodes': graph.get_all(label)['nodes']
        })
    return render_template('index.html', data=data, title='Index')

@app.route('/support', methods=['GET'])
def support():
    ''' the "give me money" page '''
    return render_template('support.html')


@app.route('/<label>/<uid>', methods=['GET'])
def item(label, uid):
    ''' generic page for an item '''
    #TODO: error handling, sanitization
    logging.info('loading %s: %s', label, uid)
    data = graph.get_node(uid)
    title = '%s (%s)' % (data['nodes'][0]['properties']['identifier'],
                         (label[0].upper() + label[1:]))
    return render_template('item.html', data=data, title=title)


# ----- filters
@app.template_filter('format_rel')
def format_rel_filter(rel):
    ''' cleanup _ lines '''
    return re.sub('_', ' ', rel)


@app.template_filter('capitalize')
def capitalize_filter(text):
    ''' capitalize words '''
    return text[0].upper() + text[1:]


@app.template_filter('pluralize')
def pluralize(text):
    ''' fishs '''
    return text + 's'


if __name__ == '__main__':
    app.debug = True
    app.run(host='0.0.0.0', port=4080)
