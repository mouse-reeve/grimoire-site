''' developer API '''
from flask import Response, request
from flask_restful import reqparse
import json
import logging

from grimoire import app, graph, api_graph, helpers
from grimoire.helpers import render_template

falsey = ['False', 'false', '0']

@app.route('/api')
@app.route('/api/v1')
def api_docs():
    ''' API documentation page '''
    return render_template(request.url, 'api.html', title='API Documentation')

@app.route('/api/v1/label')
def api_labels():
    ''' get a list of labels '''
    return api_response(graph.get_labels())


@app.route('/api/v1/label/<label>')
def api_label(label):
    ''' get a list of items for a given label '''
    if not graph.validate_label(label):
        error = 'invalid label "%s"' % label
        logging.warn(error)
        return error, 404


    parser = reqparse.RequestParser()
    parser.add_argument('limit', type=int, default=25)
    parser.add_argument('offset', type=int, default=0)
    parser.add_argument('sort', type=str, case_sensitive=False)
    parser.add_argument('sort_direction', choices=['asc', 'desc'],
                        case_sensitive=False, default='asc')
    parser.add_argument('uids_only', type=bool, default=False)

    args = parser.parse_args()

    if args.sort:
        args.sort = helpers.sanitize(args.sort)

    if args.limit < 1 or args.offset < 0:
        return 'Invalid limit or offset', 403

    if args.limit > 100:
        return 'Max limit is 100', 403

    # --- load data
    data = api_graph.get_label(label, **args)
    if args.uids_only:
        data = data['lists']
    else:
        data = data['nodes']
    return api_response(data)


@app.route('/api/v1/node/<uid_raw>')
def api_node(uid_raw):
    ''' get a list of items for a given label '''
    uid = helpers.sanitize(uid_raw)
    rels = request.args.get('relationships', False)
    if rels:
        rels = rels not in falsey

    data = api_graph.get_node(uid, rels)
    try:
        node = data['nodes'][0]
    except IndexError:
        return 'Invalid uid %s' % uid_raw, 404

    if rels:
        node['relationships'] = data['rels']

    return api_response(node)

def api_response(data):
    ''' format response and headers '''
    data = json.dumps(data)
    return Response(data, mimetype="application/json")
