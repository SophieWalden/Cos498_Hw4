import numpy as np
import random
import time

class Model:
    def __init__(self, parents=[]):
        self.layer_size = [11, 32, 16, 8, 5]
        self.activation_functions = [None, "ReLU", "ReLU", "ReLU", "Softmax"]
        self.saved = False

        self.weights = {}
        self.biases = {}
        self.nodes = []
        self.chosen_percentage = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        self.chosen_count = 0
        self.id = random.randint(0, 100000000)
        self.parents = parents

        self.setup_architecture()
        

    def setup_architecture(self):
        nodeIndex = 0
        self.weights = []
        self.biases = []

        for i, size in enumerate(self.layer_size[:-1]):
            self.nodes.append([])
            self.weights.append(np.random.uniform(-1, 1, (self.layer_size[i], self.layer_size[i + 1])))
            self.biases.append(np.zeros(self.layer_size[i + 1]))

            for _ in range(size):
                self.nodes[-1].append(nodeIndex)
                nodeIndex += 1

    def feedForward(self, inputParams):
        inputParams = np.array(inputParams)
        activations = [inputParams]
        
        for layerIndex in range(1, len(self.layer_size)):
            z = np.dot(activations[-1], self.weights[layerIndex - 1]) + self.biases[layerIndex - 1]
            
            if self.activation_functions[layerIndex] == "ReLU":
                activation = np.maximum(0, z) 
            elif self.activation_functions[layerIndex] == "Softmax":
                exp_values = np.exp(z - np.max(z))  
                activation = exp_values / np.sum(exp_values)
            else:
                activation = z 
            
            activations.append(activation)

        return activations[-1]
    
    def mutate(self):
        for j, layer in enumerate(self.weights):
            for i, node in enumerate(layer):
                for k, connection in enumerate(node):
                    if random.random() < 0.1:
                        self.weights[j][i][k] += (random.random() * 2 - 1) * 0.1
                    
        for j, layer in enumerate(self.biases):
            for i, node in enumerate(layer):
                if random.random() < 0.1:
                    self.biases[j][i] += (random.random() * 2 - 1) * 0.1

    def crossover(self, parent2):
        baby = Model(parents=[self.id, parent2.id])

        for i in range(len(self.weights)):
            if random.random() < 0.5:
                baby.weights[i] = self.weights[i].copy()
                baby.biases[i] = self.biases[i].copy()
            else:
                baby.weights[i] = parent2.weights[i].copy()
                baby.biases[i] = parent2.biases[i].copy()

        return baby
    
    def save(self, filename="model_weights_and_biases.npz"):
        np.savez(filename, weights=self.weights, biases=self.biases)
        self.saved = True

    def load(self, filename="model_weights_and_biases.npz"):
        data = np.load(filename, allow_pickle=True)
        self.weights = data["weights"]
        self.biases = data["biases"]