''' process neo4j results '''

def serialize(func):
    ''' serialize neo4j data '''
    def serialize_wrapper(self, *args, **kwargs):
        ''' serialize dis '''
        data = func(self, *args, **kwargs)
        nodes = []
        rels = []
        try:
            data.records
        except AttributeError:
            return {'nodes': []}

        for item in data.records:
            try:
                item_rels = item['r']
            except AttributeError:
                pass
            else:
                for rel in item_rels:
                    rels.append({
                        'id': rel._id,
                        'start': {
                            'id': rel.start_node._id,
                            'label':  [l for l in rel.start_node.labels][0],
                            'properties': rel.start_node.properties
                        },
                        'end': {
                            'id': rel.end_node._id,
                            'label':  [l for l in rel.end_node.labels][0],
                            'properties': rel.end_node.properties
                        },
                        'type': rel.type,
                        'properties': rel.properties
                    })
            try:
                node = item['n']
            except AttributeError:
                pass
            else:
                try:
                    link = '/%s/%s' % (node.labels.copy().pop(), node.properties['uid'])
                except KeyError:
                    link = ''

                nodes.append({
                    'id': node._id,
                    'label': [l for l in node.labels][0],
                    'link': link,
                    'properties': node.properties,
                })

        return {'nodes': nodes, 'relationships': rels}
    return serialize_wrapper

