import sys
import numpy as np
import theano
import os
from theano import tensor as T
from neuralmodels.utils import permute 
from neuralmodels.loadcheckpoint import *
from neuralmodels.costs import softmax_loss
from neuralmodels.models import * #RNN, SharedRNN, SharedRNNVectors, SharedRNNOutput
from neuralmodels.predictions import OutputMaxProb, OutputSampleFromDiscrete
from neuralmodels.layers import * #softmax, simpleRNN, OneHot, LSTM, TemporalInputFeatures,ConcatenateFeatures,ConcatenateVectors
import cPickle
import pdb
import socket as soc

def DRAmodel(nodeList,edgeList,edgeFeatures,nodeFeatures,nodeToEdgeConnections,clipnorm=0.0):
	edgeRNNs = {}
	edgeNames = edgeList
	lstm_init = 'orthogonal'
	softmax_init = 'uniform'

	for em in edgeNames:
		inputJointFeatures = edgeFeatures[em]
		edgeRNNs[em] = [TemporalInputFeatures(inputJointFeatures),
				RNN('rectify','uniform',size=500,temporal_connection=False),
				RNN('rectify','uniform',size=500,temporal_connection=False),
				LSTM('tanh','sigmoid',lstm_init,100,1000),
				LSTM('tanh','sigmoid',lstm_init,100,1000)
				]

	nodeRNNs = {}
	nodeNames = nodeList.keys()
	nodeLabels = {}
	for nm in nodeNames:
		num_classes = nodeList[nm]
		nodeRNNs[nm] = [LSTM('tanh','sigmoid',lstm_init,100,1000),
				RNN('rectify','uniform',size=500,temporal_connection=False),
				RNN('rectify','uniform',size=100,temporal_connection=False),
				RNN('rectify','uniform',size=54,temporal_connection=False),
				softmax(num_classes,softmax_init)
				]
		em = nm+'_input'
		edgeRNNs[em] = [TemporalInputFeatures(nodeFeatures[nm]),
				RNN('rectify','uniform',size=500,temporal_connection=False),
				RNN('rectify','uniform',size=500,temporal_connection=False),
				]
		nodeLabels[nm] = T.lmatrix()
	learning_rate = T.fscalar()
	dra = DRA(edgeRNNs,nodeRNNs,nodeToEdgeConnections,softmax_loss,nodeLabels,learning_rate,clipnorm)
	return dra

def readCRFGraph(filename):
	lines = open(filename).readlines()
	nodeOrder = []
	nodeNames = {}
	nodeList = {}
	nodeToEdgeConnections = {}
	nodeFeatures = {}
	for node_name, node_type in zip(lines[0].strip().split(','),lines[1].strip().split(',')):
		nodeOrder.append(node_name)
		nodeNames[node_name] = node_type
		nodeList[node_type] = 0
		nodeToEdgeConnections[node_type] = {}
		nodeToEdgeConnections[node_type][node_type+'_input'] = []
		nodeFeatures[node_type] = 0
	
	edgeList = []
	edgeFeatures = {}
	nodeConnections = {}
	for i in range(2,len(lines)):
		first_nodeName = nodeOrder[i-2]
		first_nodeType = nodeNames[first_nodeName]
		nodeConnections[first_nodeName] = []
		connections = lines[i].strip().split(',')
		for j in range(len(connections)):
			if connections[j] == '1':
				second_nodeName = nodeOrder[j]
				second_nodeType = nodeNames[second_nodeName]
				nodeConnections[first_nodeName].append(second_nodeName)
		
				edgeType_1 = first_nodeType + '_' + second_nodeType
				edgeType_2 = second_nodeType + '_' + first_nodeType
				edgeType = ''
				if edgeType_1 in edgeList:
					edgeType = edgeType_1
					continue
				elif edgeType_2 in edgeList:
					edgeType = edgeType_2
					continue
				else:
					edgeType = edgeType_1
				edgeList.append(edgeType)
				edgeFeatures[edgeType] = 0
				nodeToEdgeConnections[first_nodeType][edgeType] = []
				nodeToEdgeConnections[second_nodeType][edgeType] = []

	return nodeNames,nodeList,nodeFeatures,nodeConnections,edgeList,edgeFeatures,nodeToEdgeConnections	

if __name__ == '__main__':
	
	crf_problem = sys.argv[1]

	crf_file = './CRFProblems/{0}/crf'.format(crf_problem)

	readCRFGraph(crf_file)

	'''
	index = sys.argv[1]	
	fold = sys.argv[2]
	
	main_path = ''
	if soc.gethostname() == "napoli110.stanford.edu":
		main_path = '/scr/ashesh/activity-anticipation'
	elif soc.gethostname() == "ashesh":
		main_path = '.'
			
	path_to_dataset = '{1}/dataset/{0}'.format(fold,main_path)
	path_to_checkpoints = '{1}/checkpoints/{0}'.format(fold,main_path)

	if not os.path.exists(path_to_checkpoints):
		os.mkdir(path_to_checkpoints)

	test_data = cPickle.load(open('{1}/test_data_{0}.pik'.format(index,path_to_dataset)))	
	Y_te_human = test_data['labels_human']
	Y_te_human_anticipation = test_data['labels_human_anticipation']
	X_te_human_disjoint = test_data['features_human_disjoint']
	X_te_human_shared = test_data['features_human_shared']

	print "Loading training data...."
	train_data = cPickle.load(open('{1}/train_data_{0}.pik'.format(index,path_to_dataset)))	
	print "Data Loaded"
	Y_tr_human = train_data['labels_human']
	Y_tr_human_anticipation = train_data['labels_human_anticipation']
	X_tr_human_disjoint = train_data['features_human_disjoint']
	X_tr_human_shared = train_data['features_human_shared']

	Y_tr_objects = train_data['labels_objects']
	Y_tr_objects_anticipation = train_data['labels_objects_anticipation']
	X_tr_objects_disjoint = train_data['features_objects_disjoint']
	X_tr_objects_shared = train_data['features_objects_shared']

	num_sub_activities = int(np.max(Y_tr_human) - np.min(Y_tr_human) + 1)
	num_affordances = int(np.max(Y_tr_objects) - np.min(Y_tr_objects) + 1)
	num_sub_activities_anticipation = int(np.max(Y_tr_human_anticipation) - np.min(Y_tr_human_anticipation) + 1)
	num_affordances_anticipation = int(np.max(Y_tr_objects_anticipation) - np.min(Y_tr_objects_anticipation) + 1)
	inputJointFeatures = X_tr_human_shared.shape[2]
	inputHumanFeatures = X_tr_human_disjoint.shape[2]
	inputObjectFeatures = X_tr_objects_disjoint.shape[2]
	assert(inputJointFeatures == X_tr_objects_shared.shape[2])

	assert(X_tr_human_shared.shape[0] == X_tr_human_disjoint.shape[0])
	assert(X_tr_human_shared.shape[1] == X_tr_human_disjoint.shape[1])
	assert(X_tr_objects_shared.shape[0] == X_tr_objects_disjoint.shape[0])
	assert(X_tr_objects_shared.shape[1] == X_tr_objects_disjoint.shape[1])


	nodeList = {}
	nodeList['H'] = num_sub_activities
	nodeList['O'] = num_affordances
	edgeList = ['HO']
	edgeFeatures = {}
	edgeFeatures['HO'] = inputJointFeatures
	nodeFeatures = {}
	nodeFeatures['H'] = inputHumanFeatures
	nodeFeatures['O'] = inputObjectFeatures
	nodeToEdgeConnections = {}
	nodeToEdgeConnections['H'] = {}
	nodeToEdgeConnections['H']['HO'] = [0,inputJointFeatures]
	nodeToEdgeConnections['H']['H_input'] = [inputJointFeatures,inputJointFeatures+inputHumanFeatures]
	nodeToEdgeConnections['O'] = {}
	nodeToEdgeConnections['O']['HO'] = [0,inputJointFeatures]
	nodeToEdgeConnections['O']['O_input'] = [inputJointFeatures,inputJointFeatures+inputObjectFeatures]
	dra = DRAmodel(nodeList,edgeList,edgeFeatures,nodeFeatures,nodeToEdgeConnections)

	trX = {}
	trY = {}
	trX['H'] = np.concatenate((X_tr_human_shared,X_tr_human_disjoint),axis=2)	
	trY['H'] = Y_tr_human
	trX['O'] = np.concatenate((X_tr_objects_shared,X_tr_objects_disjoint),axis=2)	
	trY['O'] = Y_tr_objects
	dra.fitModel(trX,trY,1,'{1}/{0}/'.format(index,path_to_checkpoints),10)
	'''
