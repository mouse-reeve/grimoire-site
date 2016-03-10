""" neo4j logic """
import logging
import os

from py2neo import authenticate, Graph
from py2neo.error import Unauthorized
from py2neo.packages.httpstream.http import SocketError

from grimoire.serializer import serialize


class GraphService(object):
    """ manage neo4j data operations """

    def __init__(self):
        try:
            user = os.environ['NEO4J_USER']
            password = os.environ['NEO4J_PASS']
        except KeyError:
            logging.error('Environment variables for database authentication unavailable')
        else:
            authenticate('localhost:7474', user, password)

        try:
            graph = Graph()
            self.query = graph.cypher.execute
        except SocketError:
            logging.error('neo4j failed to load')
            self.query = lambda x: {}
        except Unauthorized:
            self.query = lambda x: {}

        labels = self.query('MATCH n RETURN DISTINCT LABELS(n)')
        self.labels = [l[0][0] for l in labels if not 'parent' in l[0][0]]

    def get_labels(self):
        """
        list of all types/labels in the db
        :return:
        """
        return self.labels

    def validate_label(self, label):
        """
        check if a label is real
        :param label:
        :return:
        """
        return label in self.labels

    @serialize
    def get_all(self, label, with_connection_label=None):
        """
        load all nodes with a given label
        :param label:
        :param with_connection_label:
        :return:
        """
        query = 'MATCH (n:%s) ' % label
        if with_connection_label:
            query += ' -- (m:%s) ' % with_connection_label
        query += 'RETURN DISTINCT n'
        return self.query(query)

    @serialize
    def get_node(self, uid):
        """ load data for a node by uid
        :param uid: the human-readable uid string
        :return: serialized neo4j nodes
        """
        query = 'MATCH n WHERE n.uid = {uid} ' \
                'OPTIONAL MATCH (n)-[r]-() RETURN n, r'
        return self.query(query, uid=uid)

    @serialize
    def random(self):
        """ select one random node
        :return: the serialized neo4j nodelist
        """
        node = self.query('MATCH n RETURN n, rand() as random ORDER BY random LIMIT 1')
        return node

    @serialize
    def search(self, term):
        """ match a search term
        :param term: the keyword to search on
        :return: serialized neo4j results
        """
        if not term:
            return []
        data = self.query('MATCH n WHERE n.identifier =~ {term} OR '
                          'n.alternate_names =~ {term} OR '
                          'n.content =~ {term} RETURN n', term='(?i).*%s.*' % term)
        return data

    @serialize
    def related(self, uid, label, n=2, limit=5):
        """ find similar items, based on nth degree relationships
        :param uid:
        :param label:
        :param n:
        :param limit:
        :return:
        """
        query = 'MATCH (m)-[r*%d]-(n:%s) WHERE m.uid = {uid} ' \
                'RETURN DISTINCT n, count(r) ORDER BY count(r) desc ' \
                'LIMIT %d' % (n, label, limit)
        return self.query(query, uid=uid)

    @serialize
    def others_of_type(self, label, uid, exclude):
        """
        get all <blank> related to item <blank>
        :param label:
        :param uid:
        :param exclude:
        :return:
        """
        query = 'MATCH (n:%s)--(m) ' \
                'WHERE m.uid = {uid} ' \
                'AND NOT n.uid = {exclude} ' \
                'RETURN n LIMIT 5' % label
        return self.query(query, uid=uid, exclude=exclude)

    @serialize
    def get_filtered(self, label, item1, item2, operator):
        """
        items that connect to nodes
        :param label:
        :param item1:
        :param item2:
        :param operator:
        :return:
        """
        query = 'MATCH (n:%s)--m, p ' \
                'WHERE m.uid={item1} AND p.uid={item2} ' \
                'AND ' % label

        if operator == 'not':
            query += 'NOT '

        query += '(n)--(p) RETURN n'
        return self.query(query, item1=item1, item2=item2)

    @serialize
    def get_grimoire_entities(self, entity):
        """
        get a list of grimoires with a list of their demons
        :param entity:
        :return:
        """
        query = 'MATCH (n:grimoire)-[:lists]-(m:%s) ' \
                'WITH m, COUNT (n) as cn, COLLECT(n) AS ln ' \
                'WHERE cn > 1 ' \
                'RETURN m, ln ORDER BY SIZE(ln) DESC' % entity
        return self.query(query)

    @serialize
    def get_single_grimoire_entities(self, entity):
        """
        get a list of entities that only appear in one grimoire, by grimoire
        :param entity:
        :return:
        """
        query = 'MATCH (n:grimoire)-[r:lists]->(m:%s), (p:grimoire) ' \
                'WITH m, COUNT(r) AS cr, p ' \
                'WHERE cr = 1 AND (p)-[:lists]->(m) ' \
                'WITH p, collect(m) as lm ' \
                'RETURN p, lm' % entity
        return self.query(query)

    @serialize
    def get_with_param(self, param):
        """ get all nodes with a param of given name
        :param param: the field to find on nodes
        :return: serialized list of nodes
        """
        query = "MATCH (n) WHERE HAS(n.%s) RETURN n" % param
        return self.query(query)
