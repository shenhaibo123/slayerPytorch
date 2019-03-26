import sys, os

CURRENT_TEST_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.append(CURRENT_TEST_DIR + "/../src")

import numpy as np
import matplotlib.pyplot as plt
from slayer import spikeLayer
from spikeLoss import spikeLoss
from data_reader import SlayerParams
import torch

###############################################################################
# testing the gradinets #######################################################
net_params = SlayerParams(CURRENT_TEST_DIR + "/test_files/snnData/network.yaml")

Ns   = int(net_params['simulation']['tSample'] / net_params['simulation']['Ts'])
Nin  = int(net_params['layer'][0]['dim'])
Nhid = int(net_params['layer'][1]['dim'])
Nout = int(net_params['layer'][2]['dim'])

class Network(torch.nn.Module):
	def __init__(self, net_params, device=torch.device('cuda')):
		super(Network, self).__init__()
		# initialize slayer
		slayer = spikeLayer(net_params['neuron'], net_params['simulation'], fullRefKernel = True)
		# define network functions
		self.spike = slayer.spike()
		self.psp   = slayer.psp()
		self.fc1   = slayer.dense(Nin, Nhid)
		self.fc2   = slayer.dense(Nhid, Nout)
		W1 = np.loadtxt('test_files/snnData/w1Initial.txt')
		W2 = np.loadtxt('test_files/snnData/w2Initial.txt')
		self.fc1.weight = torch.nn.Parameter(torch.FloatTensor(W1.reshape((Nhid, Nin , 1, 1, 1))).to(self.fc1.weight.device), requires_grad = True)
		self.fc2.weight = torch.nn.Parameter(torch.FloatTensor(W2.reshape((Nout, Nhid, 1, 1, 1))).to(self.fc2.weight.device), requires_grad = True)
	
	def forward(self, spikeInput):
		spikeLayer1 = self.spike(self.fc1(self.psp(spikeInput)))
		spikeLayer2 = self.spike(self.fc2(self.psp(spikeLayer1)))
		return spikeLayer2
		
snn = Network(net_params)

# load input spikes
spikeAER = np.loadtxt('test_files/snnData/spikeIn.txt')
spikeAER[:,0] /= net_params['simulation']['Ts']
spikeAER[:,1] -= 1

spikeData = np.zeros((Nin, Ns))
for (tID, nID) in np.rint(spikeAER).astype(int):
	if tID < Ns : spikeData[nID, tID] = 1/net_params['simulation']['Ts']
spikeIn = torch.FloatTensor(spikeData.reshape((1, Nin, 1, 1, Ns))).to(torch.device('cuda'))

spikeOut = snn.forward(spikeIn)

# load desired spikes
spikeAER = np.loadtxt('test_files/snnData/spikeOut.txt')
spikeAER[:,0] /= net_params['simulation']['Ts']
spikeAER[:,1] -= 1
spikeData = np.zeros((Nout, Ns))
for (tID, nID) in np.rint(spikeAER).astype(int):
	if tID < Ns : spikeData[nID, tID] = 1/net_params['simulation']['Ts']
spikeDes = torch.FloatTensor(spikeData.reshape((1, Nout, 1, 1, Ns))).to(torch.device('cuda'))

# calculate loss
# error = snn.psp(spikeOut - spikeDes) 
# loss  = 1/2 * torch.sum(error**2) * net_params['simulation']['Ts']
error = spikeLoss(net_params['neuron'], net_params['simulation'])
loss = error.spikeTime(spikeOut, spikeDes)
print('loss :', loss)

loss.backward()

gradW1 = np.loadtxt('test_files/snnData/gradW1Initial.txt')
gradW2 = np.loadtxt('test_files/snnData/gradW2Initial.txt')

print('Layer2 gradient error :', np.linalg.norm(gradW2 - snn.fc2.weight.grad.reshape((Nout, Nhid)).cpu().numpy()) / gradW2.size)
print('Layer1 gradient error :', np.linalg.norm(gradW1 - snn.fc1.weight.grad.reshape((Nhid, Nin )).cpu().numpy()) / gradW1.size)

# print(snn.fc2.weight.grad.reshape((Nout, Nhid)).cpu().numpy())
# print(snn.fc1.weight.grad.reshape((Nhid, Nin)).cpu().numpy()[0, :])

# plotting
plt.figure(1)
plt.subplot(2, 1, 1)
plt.plot(gradW2 - snn.fc2.weight.grad.reshape((Nout, Nhid)).cpu().numpy(), '.')
plt.xlabel('Output neuron #')
plt.ylabel('Gradient Error')

plt.subplot(2, 1, 2)
plt.plot(gradW1 - snn.fc1.weight.grad.reshape((Nhid, Nin )).cpu().numpy(), '.')
plt.xlabel('Hidden neuron #')
plt.ylabel('Gradient Error')

plt.show()

