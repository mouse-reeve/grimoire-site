''' developer API '''
from flask import Response, request
from flask_restful import reqparse
import json
import logging
import random
import urllib
import urllib2

from grimoire import app, graph, api_graph, helpers
from grimoire.helpers import render_template

falsey = ['false', '0']

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
    parser.add_argument('uids_only', case_sensitive=False, default=False)

    args = parser.parse_args()

    if args.uids_only:
        args.uids_only = args.uids_only not in falsey

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
    ''' get a particular node by uid '''
    uid = helpers.sanitize(uid_raw)
    parser = reqparse.RequestParser()
    parser.add_argument('relationships', case_sensitive=False, default=False)
    args = parser.parse_args()

    if args.relationships:
        args.relationships = args.relationships not in falsey

    data = api_graph.get_node(uid, args.relationships)
    try:
        node = data['nodes'][0]
    except IndexError:
        return 'Invalid uid %s' % uid_raw, 404

    if args.relationships:
        node['relationships'] = data['rels']

    return api_response(node)


@app.route('/api/v1/node/<uid_raw>/<label>')
def api_connected_nodes(uid_raw, label):
    ''' get a list of items for a given label for a given node'''
    uid = helpers.sanitize(uid_raw)
    if not graph.validate_label(label):
        error = 'invalid label "%s"' % label
        logging.warn(error)
        return error, 404

    parser = reqparse.RequestParser()
    parser.add_argument('limit', type=int, default=25)
    parser.add_argument('offset', type=int, default=0)
    args = parser.parse_args()

    if args.limit < 1 or args.offset < 0:
        return 'Invalid limit or offset', 403

    if args.limit > 100:
        return 'Max limit is 100', 403


    data = api_graph.get_connected_nodes(uid, label, **args)
    try:
        node = data['nodes']
    except IndexError:
        return 'Invalid uid %s' % uid_raw, 404

    return api_response(node)


def api_response(data):
    ''' format response and headers '''
    # ping piwik
    if not app.debug:
        url = urllib.quote_plus(request.url)
        try:
            referrer = urllib.quote_plus(request.referrer)
        except TypeError:
            referrer = ''
        rand = int(random.random()*100000)
        piwik = 'https://piwik.grimoire.org/piwik/piwik.php?'\
                'idsite=1&rec=1&url=%s&urlref=%s&rand=%d' % (url, referrer, rand)

        urllib2.urlopen(piwik)
    data = json.dumps(data)
    return Response(data, mimetype="application/json")
