"""Visualization of pipelines using graphviz"""

import functools

import flask
import graphviz

from data_integration import pipelines
from data_integration.ui import views
from mara_page import acl, html, bootstrap, _


def card(node: pipelines.Pipeline):
    return bootstrap.card(
        body=[_.p[_.em[node.description]],
              (_.p[views.format_labels(node)] if node.labels else ''),
              html.asynchronous_content(
                  flask.url_for('data_integration.dependency_graph', path=node.url_path()))])


@views.blueprint.route('/<path:path>/dependency-graph')
@views.blueprint.route('/dependency-graph', defaults={'path': ''})
@acl.require_permission(views.acl_resource, do_abort=False)
@functools.lru_cache(maxsize=None)
def dependency_graph(path: str):
    node, found = pipelines.find_node(path.split('/'))
    if not found:
        flask.abort(404, f'Node "{path}" not found')

    return dependency_graph(node)


@functools.singledispatch
def dependency_graph(nodes: {str: pipelines.Node},
                     current_node: pipelines.Node = None) -> str:
    """
    Draws a list of pipeline nodes and the dependencies between them using graphviz

    Args:
        nodes: The nodes to render
        current_node: If not null, then this node is highlighted

    Returns:
        An svg representation of the graph
    """
    graph = graphviz.Digraph(graph_attr={'rankdir': 'TD', 'ranksep': '0.25', 'nodesep': '0.1'})
    for node in nodes.values():

        node_attributes = {'fontname': ' ',  # use website default
                           'fontsize': '10.5px'  # fontsize unfortunately must be set
                           }

        if node != current_node:
            node_attributes.update(
                {'href': views.node_url(node), 'fontcolor': '#0275d8',
                 'tooltip': node.description, 'color': 'transparent'})
        else:
            node_attributes.update({'color': '#888888', 'style': 'dotted'})

        if isinstance(node, pipelines.Pipeline):
            node_attributes.update({'shape': 'rectangle', 'style': 'dotted', 'color': '#888888'})
        elif isinstance(node, pipelines.ParallelTask):
            node_attributes.update({'shape': 'ellipse', 'style': 'dotted', 'color': '#888888'})
        else:
            node_attributes['shape'] = 'rectangle'

        graph.node(name=node.id, label=node.id.replace('_', '\n'), _attributes=node_attributes)

        for upstream in node.upstreams:
            if upstream.id in nodes:
                graph.edge(upstream.id, node.id, _attributes={'color': '#888888', 'arrowsize': '0.7'})
            elif (not current_node) or node in current_node.upstreams:
                graph.node(name=f'{upstream.id}_{node.id}',
                           _attributes={'style': 'invis', 'label': '', 'height': '0.1', 'fixedsize': 'true'})
                graph.edge(f'{upstream.id}_{node.id}', node.id,
                           _attributes={'color': '#888888', 'arrowsize': '0.7',
                                        'edgetooltip': upstream.id, 'style': 'dotted'})

        for downstream in node.downstreams:
            if downstream.id not in nodes and (not current_node or node in current_node.downstreams):
                graph.node(name=f'{downstream.id}_{node.id}',
                           _attributes={'style': 'invis', 'label': '', 'height': '0.1', 'fixedsize': 'true'})
                graph.edge(node.id, f'{downstream.id}_{node.id}',
                           _attributes={'color': '#888888', 'arrowsize': '0.7',
                                        'edgetooltip': downstream.id, 'style': 'dotted'})

    return graph.pipe('svg').decode('utf-8')


@dependency_graph.register(pipelines.Pipeline)
def __(pipeline: pipelines.Pipeline):
    """Draw all nodes of a pipeline excluding initial and final node"""
    return dependency_graph({id: node for id, node in pipeline.nodes.items()
                             if node != pipeline.initial_node and node != pipeline.final_node})


@dependency_graph.register(pipelines.Node)
def __(node: pipelines.Pipeline):
    """For all other pipeline nodes, draw only direct upstreams and downstreams of node"""
    return dependency_graph({node.id: node for node in list(node.upstreams) + [node] + list(node.downstreams)},
                            node)