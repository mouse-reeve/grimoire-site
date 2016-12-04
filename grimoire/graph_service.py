''' neo4j logic '''
import logging
import os

from py2neo import authenticate, Graph
from py2neo.error import Unauthorized
from py2neo.packages.httpstream.http import SocketError

from grimoire.serializer import serialize


class GraphService(object):
    ''' manage neo4j data operations '''

    def __init__(self):
        try:
            user = os.environ['NEO4J_USER']
            password = os.environ['NEO4J_PASS']
        except KeyError:
            logging.error('Environment vars for database auth unavailable')
        else:
            authenticate('localhost:7474', user, password)

        try:
            graph = Graph()
            self.query_method = graph.cypher.execute
        except SocketError:
            logging.error('neo4j failed to load')
            self.query_method = lambda x: {}
        except Unauthorized:
            self.query_method = lambda x: {}

        labels = self.query('MATCH n RETURN DISTINCT LABELS(n)')
        self.labels = [[m for m in list(l)[0] if not 'parent' in m][0] for l in labels]
        self.date_params = ['born', 'died', 'crowned', 'date',
                            'year', 'began', 'ended']
        self.timeline_labels = []
        self.timeline_data = []


    def query(self, query_string, **kwargs):
        ''' wrapper around the neo4j query
        :param query_string: a complete neo4j cypher query
        :return: the results of the neo4j query
        '''
        logging.info('Running query %s', query_string)
        return self.query_method(query_string, **kwargs)


    def get_labels(self):
        ''' list of all types/labels in the db
        :return: an array of text labels
        '''
        return self.labels


    def get_entity_labels(self):
        ''' get a list of all the supernatural entities
        :return: a list of labels under the parent label "entity"
        '''
        query = 'MATCH (n:`parent:entity`) RETURN DISTINCT LABELS(n)'
        labels = self.query(query)

        return [[m for m in list(l)[0] if not 'parent' in m][0] for l in labels]


    def validate_label(self, label):
        ''' check if a label is real
        :param label: the label in question
        :return: boolean value
        '''
        return label in self.labels


    @serialize
    def get_all(self, label, with_connection_label=None):
        ''' load all nodes with a given label
        :param label: the label for the type of node desired
        :param with_connection_label: optional param to also limit to nodes that
        know a node of a given type
        :return: a serialized list of relevent nodes
        '''
        query = 'MATCH (n:%s) ' % label
        if with_connection_label:
            query += ' -- (m:%s) ' % with_connection_label
        query += 'RETURN DISTINCT n'
        return self.query(query)


    @serialize
    def get_node(self, uid):
        ''' load data for a node by uid
        :param uid: the human-readable uid string
        :return: serialized neo4j nodes
        '''
        query = 'MATCH n WHERE n.uid = {uid} ' \
                'OPTIONAL MATCH (n)-[r]-() RETURN n, r'
        return self.query(query, uid=uid)


    @serialize
    def search(self, term):
        ''' match a search term
        :param term: the keyword to search on
        :return: serialized neo4j results
        '''
        if not term:
            return []
        query = 'MATCH n WHERE (n.identifier =~ {term} OR ' \
                'n.alternate_names =~ {term}) ' \
                'AND NOT n:excerpt AND NOT n:image RETURN n'

        return self.query(query, term='(?i)(?s).*%s.*' % term)


    @serialize
    def related(self, uid, label, n=2, limit=5):
        ''' find similar items, based on nth degree relationships
        :param uid: the unique text idea of the reference node
        :param label: the type of nodes to be found
        :param n: the length of connection chains to assess
        :param limit: the max number of results returned
        :return: a serialized list of related nodes
        '''
        query = 'MATCH (m)-[r*%d]-(n:%s) WHERE m.uid = {uid} ' \
                'RETURN DISTINCT n, count(r) ORDER BY count(r) desc ' \
                'LIMIT %d' % (n, label, limit)
        return self.query(query, uid=uid)


    @serialize
    def others_of_type(self, label, uid, exclude):
        ''' get all <blank> related to item <blank>
        :param label: the type of the related nodes
        :param uid: the unique id of the reference node
        :param exclude: specific nodes to ignore
        :return: serialized list of nodes of a type related to a given node
        '''
        query = 'MATCH (n:%s)--(m) ' \
                'WHERE m.uid = {uid} ' \
                'AND NOT n.uid = {exclude} ' \
                'RETURN n LIMIT 5' % label
        return self.query(query, uid=uid, exclude=exclude)


    @serialize
    def get_filtered(self, label, item1, item2=None, operator=None):
        ''' items that connect to nodes
        :param label: the type of the desired items
        :param item1: the first node the items must be connected to
        :param item2: the second node they must be connected to
        :param operator: type of connection
        :return: a list of nodes that are/are not connected to both items
        '''
        if item2 and operator:
            query = 'MATCH (n:%s)--m, p ' \
                    'WHERE m.uid={item1} AND p.uid={item2} ' \
                    'AND ' % label

            if operator == 'not':
                query += 'NOT '
        else:
            query = 'MATCH (n:%s)--p  WHERE p.uid={item1} AND ' % label

        query += '(n)--(p) RETURN n'
        return self.query(query, item1=item1, item2=item2)


    @serialize
    def get_grimoire_entities(self, entity):
        ''' get a list of grimoires with a list of their demons
        :param entity: the demon/angel/fairy/etc list for a grimoire
        :return: a list of the supernatural entities connected to a grimoire
        '''
        query = 'MATCH (n:grimoire)-[:lists]-(m:%s) ' \
                'WITH m, COUNT (n) as cn, COLLECT(n) AS ln ' \
                'WHERE cn > 1 ' \
                'RETURN m, ln ORDER BY SIZE(ln) DESC' % entity
        return self.query(query)


    @serialize
    def get_single_grimoire_entities(self, entity):
        ''' get a list of entities that only appear in one grimoire, by grimoire
        :param entity: the type of entity being assesses
        :return: a list of supernatural entities of the given type in 1 grimoire
        '''
        query = 'MATCH (n:grimoire)-[r:lists]->(m:%s), (p:grimoire) ' \
                'WITH m, COUNT(r) AS cr, p ' \
                'WHERE cr = 1 AND (p)-[:lists]->(m) ' \
                'WITH p, collect(m) as lm ' \
                'RETURN p, lm' % entity
        return self.query(query)


    @serialize
    def get_with_param(self, param):
        ''' get all nodes with a param of given name
        :param param: the field to find on nodes
        :return: serialized list of nodes
        '''
        query = 'MATCH (n) WHERE HAS(n.%s) RETURN n' % param
        return self.query(query)


    @serialize
    def get_spells_by_outcome(self):
        ''' get a list of spells organized by outcome
        :return: serialized list of outcomes and spells
        '''
        query = 'MATCH (n:outcome)--(m:spell) ' \
                'WITH n, COLLECT(m) AS spells RETURN n, spells'
        return self.query(query)


    @serialize
    def get_spells_by_grimoire(self):
        ''' get a list of spells organized by outcome
        :return: serialized list of outcomes and spells
        '''
        query = 'MATCH (n:grimoire)--(m:spell) ' \
                'WITH n, COLLECT(m) AS spells RETURN n, spells'
        return self.query(query)


    @serialize
    def timeline(self):
        ''' get all the requested items to populate the timeline
        :return: an array of nodes with date params
        '''
        if len(self.timeline_data):
            return self.timeline_data

        query = 'MATCH n WHERE '
        checks = ['HAS(n.%s)' % param for param in self.date_params]
        query += ' OR '.join(checks) + ' RETURN n'

        self.timeline_data = self.query(query)
        return self.timeline_data


    @serialize
    def get_frontpage_random(self):
        ''' get a random node to display on the front page
        :return: a serialized node of the given type
        '''
        query = 'MATCH (n:excerpt) ' \
                'WHERE SIZE(n.content) < 500 ' \
                'AND SIZE(n.identifier) < 140 ' \
                'RETURN n ORDER BY rand() LIMIT 1'

        return self.query(query)


    @serialize
    def get_comparisons(self, grimoire, label):
        ''' get a list of grimoires that share nodes '''
        query = 'MATCH (n:grimoire)--(d:%s)--(g:grimoire) ' \
                'WHERE n.uid={grimoire} ' \
                'WITH g, COLLECT(d) as cd ' \
                'RETURN g, cd ORDER BY SIZE(cd) DESC LIMIT 1' % label
        return self.query(query, grimoire=grimoire)

    @serialize
    def get_events(self, start, end):
        ''' get all events within a time range '''
        query = 'MATCH (n:event) ' \
                'WHERE (toInt(n.date) >= {start} and toInt(n.date) <= {end}) ' \
                'AND (NOT has(n.end_date) OR toInt(n.date) <= {end}) ' \
                'RETURN DISTINCT n'
        return self.query(query, start=start, end=end)


    @serialize
    def get_related_events(self, entity):
        ''' get all events related to an item '''
        query = 'MATCH (e:event)--()-[r]-(n) ' \
                'WHERE n.uid={entity} ' \
                'RETURN e, r'
        return self.query(query, entity=entity)
