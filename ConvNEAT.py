import functools
import itertools
import operator
import random
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

import torch
import torchvision


# genetic components
def weighted_choice(choices, weights):
    return random.choices(choices, weights=weights)[0]

def random_choices(choices, chances):
    return list(np.array(choices)[np.random.rand(len(chances)) < chances])


class Gene:
    """
    Symbolizes a Edge in the Graph
    Is also used in itialization.
    Specify what can be created after this in the split_edge mutation
    (or to what it will be changed if its a initialized edge)
    """

    def __init__(self, id, id_in, id_out, mutate_to=None):
        self.id = id
        self.id_in = id_in
        self.id_out = id_out
        self.enabled = True

        self.mutate_to = mutate_to or self.init_mutate_to()

    def __repr__(self):
        r = super().__repr__()
        return r[:-1] + ' |%s| ID = %d (%d->%d) ' % (self.enabled, self.id, self.id_in, self.id_out) + r[-1:]

    def short_repr(self):
        return ''

    def init_mutate_to(self):
        return [[KernelGene, DenseGene], [1, 1]]

    # A mutation is decided to happen. Returns itself.
    def mutate_random(self):
        return weighted_choice(*self.mutate_to)(self.id, self.id_in, self.id_out)

    def output_size(self, input_size):
        pass

    # A Edge is decided to be added after. Returns what it should be.
    def add_after(self, id, id_in, id_out):
        return weighted_choice(*self.mutate_to)(id, id_in, id_out)

    def copy(self, id, id_in, id_out):
        pass

    def dissimilarity(self, other):
        return self != other


class KernelGene(Gene):
    """
    Kernels are the edges of the graph
    """

    def __init__(self, id, id_in, id_out, size=[None, None, None], stride=None, padding=None):
        super().__init__(id, id_in, id_out, mutate_to=self.init_mutate_to())

        [depth, width, height] = size
        self.depth = depth or self.init_depth()
        self.width = width or self.init_width()
        self.height = height or self.init_height()
        self.stride = stride or self.init_stride()
        self.padding = padding if padding is not None else self.init_padding()

    def __repr__(self):
        r = super().__repr__()
        return (r[:-1] + 'size=%d*%d*%d, str=%d, pad=%d' %
                (self.depth, self.width, self.height, self.stride, self.padding) + r[-1:])

    def short_repr(self):
        return '%dx%dx%d' % (self.depth, self.width, self.height)

    def init_depth(self):
        return 1

    def init_width(self):
        return random.randrange(3, 6)

    def init_height(self):
        return random.randrange(3, 6)

    def init_stride(self):
        return 1

    def init_padding(self):
        return 0

    def init_mutate_to(self):
        return [[KernelGene, PoolGene, DenseGene], [1, 2, 0]]

    def mutate_depth(self):
        self.depth = max(1, self.depth + random.choice([-2, -1, 1, 2]))

    def mutate_width(self):
        self.width = max(1, self.width + random.choice([-2, -1, 1, 2]))

    def mutate_height(self):
        self.height = max(1, self.height + random.choice([-2, -1, 1, 2]))

    def mutate_size(self):
        r = random.choice([-2, -1, 1, 2])
        [self.width, self.height] = map(lambda x: max(1, x + r), [self.width, self.height])

    def mutate_stride(self):
        self.depth = max(1, self.depth + random.choice([-2, -1, 1, 2]))

    def mutate_padding(self):
        self.depth = max(1, self.depth + random.choice([-2, -1, 1, 2]))

    def mutate_random(self):
        mutations = random_choices((self.mutate_depth, self.mutate_width, self.mutate_height, self.mutate_size,
                                    self.mutate_stride, self.mutate_padding),
                                   (0.1, 0.1, 0.1, 0.2, 0.3, 0.2))
        for mutate in mutations:
            mutate()
        return self

    def output_size(self, in_size):
        [in_depth, in_width, in_height] = in_size
        out_depth = self.depth
        out_width = ((in_width - self.width + 2 * self.padding - 1) // self.stride) + 1
        out_height = ((in_height - self.height + 2 * self.padding - 1) // self.stride) + 1
        return [out_depth, out_width, out_height]

    def copy(self, id, id_in, id_out):
        return KernelGene(id, id_in, id_out, size=[self.depth, self.width, self.height],
                          stride=self.stride, padding=self.padding)


class PoolGene(Gene):
    """
    Pooling Layers are edges of the graph
    """
    def __init__(self, id, id_in, id_out, pooling=None, size=[None, None], padding=None):
        super().__init__(id, id_in, id_out, mutate_to=self.init_mutate_to())

        self.possible_pooling = ['max', 'avg']

        self.pooling = pooling or self.init_pooling()
        [width, height] = size
        self.width = width or self.init_width()
        self.height = height or self.init_height()
        self.padding = padding if padding is not None else self.init_padding()

    def __repr__(self):
        r = super().__repr__()
        return (r[:-1] + 'pool=%s, size=%d*%d, pad=%d' %
                (self.pooling, self.width, self.height, self.padding) + r[-1:])

    def short_repr(self):
        return self.pooling

    def init_pooling(self):
        return random.choice(self.possible_pooling)

    def init_width(self):
        return random.randrange(3, 6)

    def init_height(self):
        return random.randrange(3, 6)

    def init_padding(self):
        return 0

    def init_mutate_to(self):
        return [[KernelGene, PoolGene, DenseGene], [4, 1, 0]]

    def mutate_pooling(self):
        self.pooling = random.choice([x for x in self.possible_pooling if x != self.pooling])

    def mutate_width(self):
        self.width = max(1, self.width + random.choice([-2, -1, 1, 2]))

    def mutate_height(self):
        self.height = max(1, self.height + random.choice([-2, -1, 1, 2]))

    def mutate_size(self):
        r = random.choice([-2, -1, 1, 2])
        [self.width, self.height] = map(lambda x: max(1, x + r), [self.width, self.height])

    def mutate_padding(self):
        self.padding = max(1, self.padding + random.choice([-2, -1, 1, 2]))

    def mutate_random(self):
        mutations = random_choices((self.mutate_pooling, self.mutate_width, self.mutate_height, self.mutate_size,
                                    self.mutate_padding),
                                   (0.4, 0.2, 0.2, 0.5, 0.2))
        for mutate in mutations:
            mutate()
        return self

    def output_size(self, in_size):
        [in_depth, in_width, in_height] = in_size
        out_depth = in_depth
        out_width = (in_width - self.width + 2 * self.padding)
        out_height = (in_height - self.height + 2 * self.padding)
        return [out_depth, out_width, out_height]

    def copy(self, id, id_in, id_out):
        return PoolGene(id, id_in, id_out, size=[self.width, self.height],
                        pooling=self.pooling, padding=self.padding)


class DenseGene(Gene):
    """
    Fully Conected Layers are the Edges of the rest of the graph
    We don't know the size of the flattened first layer,
    so the number of hidden neurons per layer it determined by the distance to the layer before
    """

    def __init__(self, id, id_in, id_out, size_change=None, activation=None):
        super().__init__(id, id_in, id_out, mutate_to=self.init_mutate_to())

        self.possible_activations = ['relu', 'tanh']

        self.size_change = size_change or self.init_size_change()
        self.activation = activation or self.init_activation()

    def __repr__(self):
        r = super().__repr__()
        return (r[:-1] + 'size_change=%+d, activation=%s' %
                (self.size_change, self.activation) + r[-1:])

    def init_size_change(self):
        return random.choice(list(range(-10, -4)) + list(range(5, 11)))

    def init_activation(self):
        return random.choice(self.possible_activations)

    def init_mutate_to(self):
        return [[KernelGene, PoolGene, DenseGene], [0, 0, 1]]

    def mutate_size_change(self):
        self.size_change = self.size_change + random.choice(list(range(-10, -4)) + list(range(5, 11)))

    def mutate_activation(self):
        self.activation = random.choice([x for x in self.possible_activations if x != self.activation])

    def mutate_random(self):
        mutations = random_choices((self.mutate_size_change, self.mutate_activation),
                                   (1, 0.2))
        for mutate in mutations:
            mutate()
        return self

    def output_size(self, in_size):
        return [in_size[0], in_size[1], in_size[2] + self.size_change]

    def copy(self, id, id_in, id_out):
        return DenseGene(id, id_in, id_out, size_change=self.size_change, activation=self.activation)


class Node:

    def __init__(self, id, depth, merge=None, role=None):
        self.id = id
        self.depth = depth
        self.role = role

        self.possible_merges = ['upscale', 'downscale', 'padding', 'avgscale']

        self.merge = merge or self.init_merge()
        self.size = None

    def __repr__(self):
        return '<Node | ID = %d, depth=%.2f, merge=%s>' % (self.id, self.depth, self.merge)

    def short_repr(self):
        return '' if self.size is None else '%dx%dx%d' % (self.size[0], self.size[1], self.size[2])

    def init_merge(self):
        return random.choice(self.possible_merges)

    def mutate_merge(self):
        self.merge = random.choice([x for x in self.possible_merges if x != self.merge])

    def mutate_random(self):
        self.mutate_merge()
        return self

    def output_size(self, in_sizes):
        # how to combine the input sizes of a node
        mergesize = {'downscale': lambda x: list(np.min(np.array(x), axis=0)),
                     'upscale': lambda x: list(np.max(np.array(x), axis=0)),
                     'padding': lambda x: list(np.max(np.array(x), axis=0)),
                     'avgscale': lambda x: list(np.sum(np.array(x), axis=0) / len(x))}
        out_size = mergesize[self.merge](in_sizes)
        return [1, 1, np.prod(out_size)] if self.role == 'flatten' else out_size


class Genome:
    """
    Indirect representation of a feedforward convolutional net.
    This includes hyperparameters.
    The Minimal net is:
    Node 0 'Input' - Edge 3 - Node 1 'Flatten' - Edge 4 - Node 2 'Out'

    Coded as a graph where the edges are the neurons and the edges describe
    - the convolution operation (kernel)
    - the sizes of fully connected layers
    Shape and Number of neurons in a node are only decoded indirectly
    """

    def __init__(self, population, log_learning_rate=None, genes_and_nodes=None):
        self.population = population
        self.log_learning_rate = log_learning_rate or self.init_log_learning_rate()

        [self.nodes, self.genes] = genes_and_nodes or self.init_genome()
        self.genes_by_id, self.nodes_by_id = self.dicts_by_id()

    def __repr__(self):
        r = super().__repr__()
        return (r[:-1] + ' | learning_rate=%.4f, nodes=%s, genes=%s' %
                (self.log_learning_rate, self.nodes, self.genes) + r[-1:])

    def init_genome(self):
        return [[Node(0, 0), Node(1, 1, role='flatten'), Node(2, 2)],
                [Gene(3, 0, 1, mutate_to=[[KernelGene, DenseGene], [1, 0]]),
                 Gene(4, 1, 2, mutate_to=[[KernelGene, DenseGene], [0, 1]])]]

    def next_id(self):
        return self.population.next_id()

    def dicts_by_id(self):
        genes_by_id = dict()
        for gene in self.genes:
            genes_by_id = {**genes_by_id, **{gene.id: gene}}
        nodes_by_id = dict()
        for node in self.nodes:
            nodes_by_id = {**nodes_by_id, **{node.id: node}}
        return [genes_by_id, nodes_by_id]


    def init_log_learning_rate(self):
        return random.normalvariate(-6, 2)

    def mutate_log_learning_rate(self):
        self.log_learning_rate += random.normalvariate(0, 1)

    def mutate_genes(self, p):
        mutate = np.random.rand(len(self.genes)) < p
        for i, gene in enumerate(self.genes):
            if mutate[i]:
                self.genes[i] = gene.mutate_random()

    def mutate_nodes(self, p):
        mutate = np.random.rand(len(self.nodes)) < p
        for i, node in enumerate(self.nodes):
            if mutate[i]:
                node.mutate_random()

    def disable_edge(self):
        # TODO Erreichbar
        enabled = [gene for gene in self.genes if gene.enabled]
        if len(enabled) > 0:
            random.choice(enabled).enabled = False

    def enable_edge(self):
        disabled = [gene for gene in self.genes if not gene.enabled]
        if len(disabled) > 0:
            random.choice(disabled).enabled = True

    def split_edge(self):
        enabled = [gene for gene in self.genes if gene.enabled]
        if len(enabled) > 0:
            edge = random.choice(enabled)
            [d1, d2] = [self.nodes_by_id[edge.id_in].depth, self.nodes_by_id[edge.id_out].depth]
            [id1, id2, id3] = [f() for f in [self.next_id]*3]
            edge.enabled = False
            # Guarantee d1<dn<d2 and no duplicates with cut-off normalvariate
            new_node = Node(id1, min(d2+(d1+d2)/10, max(d1-(d1+d2)/10, random.normalvariate((d1 + d2) / 2, 0.0001))))
            new_edge_1 = edge.copy(id2, edge.id_in, new_node.id)
            new_edge_2 = edge.add_after(id3, new_node.id, edge.id_out)
            self.nodes += [new_node]
            self.genes += [new_edge_1, new_edge_2]
            self.nodes_by_id[id1] = new_node
            self.genes_by_id[id2] = new_edge_1
            self.genes_by_id[id3] = new_edge_2

    def add_edge(self):
        if len(self.nodes) >= 2:
            tries = 5
            while tries > 0:
                [n1, n2] = random.sample(self.nodes, 2)
                if n1.depth > n2.depth:
                    n1, n2 = n2, n1
                # only if edge doesn't exist
                if [n1.id, n2.id] in [[e.id_in, e.id_out] for e in self.genes]:
                    tries -= 1
                    continue
                id = self.next_id()
                new_edge = weighted_choice([KernelGene, PoolGene, DenseGene], [1, 1, 1])(id, n1.id, n2.id)
                self.genes += [new_edge]
                self.genes_by_id[id] = new_edge
                break

    def mutate_random(self):
        mutations = random_choices((lambda: self.mutate_genes(0.5), lambda: self.mutate_nodes(0.2),
                                    self.mutate_log_learning_rate,
                                    self.disable_edge, self.enable_edge, self.split_edge, self.add_edge),
                                   (1, 1, 0.5, 0.1, 0.1, 0.7, 0.3))
        for mutate in mutations:
            mutate()
        return self

    def visualize(self, input_size=None):
        self.set_sizes(input_size)
        edgelist = ['%d %d {\'class\':\'%s\'}' % (e.id_in, e.id_out, str(type(e)).split('.')[-1][:-2])
                    for e in self.genes if e.enabled]
        G = nx.parse_edgelist(edgelist)
        color_dict = {'DenseGene': 'green', 'KernelGene': 'darkorange', 'PoolGene': 'darkblue'}
        edge_colors = [color_dict[G[u][v]['class']] for u, v in G.edges()]
        edge_labels = {(str(e.id_in), str(e.id_out)): e.short_repr() for e in self.genes if e.enabled}
        node_labels = {str(n.id): n.short_repr() for n in self.nodes}
        pos = self.graph_positioning()
        fig, ax = plt.subplots()
        nx.draw(G, pos=pos, node_size=300, node_color="skyblue", node_shape="s", linewidths=4, ax=ax, with_labels=True,
                font_size=10, font_color="grey", font_weight="bold", width=2,
                edge_color=edge_colors, labels=node_labels)
        nx.draw_networkx_edge_labels(G, pos=pos, edge_labels=edge_labels, ax=ax, font_size=8, alpha=0.5)
        plt.show()

    # Groups nodes by feed-forward layers
    def group_by(self):
        nodes = sorted(self.nodes, key=lambda x: x.depth)
        grouped = []
        group = []
        c = []
        for n in nodes:
            if n.id in c:
                grouped.append(group)
                group = [n]
                c = []
            else:
                group += [n]
            c += [edge.id_out for edge in self.genes if edge.id_in == n.id]
        if len(group) > 0:
            grouped.append(group)
        return grouped

    def graph_positioning(self):
        grouped_nodes = self.group_by()
        x_steps = 1 / (len(grouped_nodes) - 1)
        shift_list = [-0.03, 0, 0.03]
        pos = dict()
        for i, group in enumerate(grouped_nodes):
            shift = shift_list[i % len(shift_list)]
            x = i * x_steps
            y_list = list(np.linspace(0, 1, len(group) + 2) + shift)[1:-1]
            pos = dict(**pos, **{str(n.id): (x, y_list[j]) for j, n in enumerate(group)})
        return pos

    def set_sizes(self, input_size):
        """
        calculate the sizes of all convolutional,etc... nodes and set them for
        plotting and building the net, if no input_size is given reset every node size
        """
        for node in self.nodes:
            node.size = None
        if input_size is None:
            return
        nodes = sorted(self.nodes, key=lambda x: x.depth)
        self.nodes_by_id[0].size = input_size
        outputs_by_id = {0: input_size}
        for node in nodes:
            # All reachable incoming edges that are enabled
            in_edges = [edge for edge in self.genes if edge.enabled and edge.id_in in outputs_by_id.keys()
                        and edge.id_out == node.id]
            if len(in_edges) > 0:
                in_sizes = [edge.output_size(outputs_by_id[edge.id_in]) for edge in in_edges]
                node.size = node.output_size(in_sizes)
                outputs_by_id[node.id] = node.size


class Population:

    def __init__(self, n, evaluate_genome):
        self.evaluate_genome = evaluate_genome
        self.id_generator = itertools.count()
        # 0-5 is reserved
        [f() for f in [self.next_id]*5]
        self.genomes = [Genome(self) for _ in range(n)]

    def next_id(self):
        return next(self.id_generator)

    def evolve(self, generation):
        scores = [(self.evaluate_genome(g), g) for g in self.genomes]
        scores.sort(key=operator.itemgetter(0))
        print()
        print()
        print('GENERATION', generation)
        print()
        for s, g in scores:
            r = repr(g)
            if len(r) > 64:
                r = r[:60] + '...' + r[-1:]
            print('{:64}:'.format(r), s)
        print()
        print()
        self.genomes = [g for s, g in scores]
        for i in range(len(self.genomes) // 4):
            self.genomes[i] = Genome(self)
        for i in range(len(self.genomes) // 4, len(self.genomes) * 3 // 4):
            self.genomes[i].mutate_random()


class Net(torch.nn.Module):

    def __init__(self, genome, input_size, output_size):
        super().__init__()

        genome.set_sizes()

        possible_activations = {'relu': torch.nn.functional.relu,
                                'tanh': torch.tanh}

        width = 28
        height = 28
        self.convs = []
        for i, gconv in enumerate(genome.convs):
            conv = torch.nn.Conv2d(
                        in_channels=1,
                        out_channels=gconv.out_channels,
                        kernel_size=gconv.half_kernel_size*2+1,
                        padding=gconv.half_kernel_size,
                    )
            activation = possible_activations[gconv.activation]
            pool = gconv.pool
            self.convs.append((conv, activation, pool))
            self.add_module('convs[{}][0]'.format(i), conv)
        self.pool = torch.nn.MaxPool2d(kernel_size=2)
        self.linears = []
        for i, glinear in enumerate(genome.linears):
            linear = torch.nn.Linear(
                        in_features=1,
                        out_features=glinear.out_channels,
                    )
            activation = possible_activations[glinear.activation]
            self.linears.append((linear, activation))
            self.add_module('linears[{}][0]'.format(i), linear)
            num_channels = glinear.out_channels
        self.final_linear = linear = torch.nn.Linear(
                    in_features=num_channels,
                    out_features=10,
                )

    def forward(self, x):
        batch_size, num_channels, height, width = x.shape
        for conv, activation, pool in self.convs:
            x = conv(x)
            x = activation(x)
            if pool:
                x = self.pool(x)
        x = torch.reshape(x, (batch_size, -1))
        for linear, activation in self.linears:
            x = linear(x)
            x = activation(x)
        x = self.final_linear(x)
        return x


def main():
    p = Population(1, 1)
    g = Genome(p)
    for i, gene in enumerate(g.genes):
        g.genes[i] = gene.mutate_random()
    while True:
        g.visualize(input_size=[3, 50, 50])
        g.mutate_random()


if __name__ == '__main__':
    main()
