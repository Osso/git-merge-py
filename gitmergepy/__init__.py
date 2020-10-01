# Monkey patch redbaron
from redbaron import nodes

nodes.NodeList.node_list = property(lambda self: self)
nodes.IfelseblockNode.node_list = property(lambda self: self.value.node_list)
