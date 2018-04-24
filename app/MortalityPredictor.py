import sys, random
import numpy as np
import _pickle as pickle
from collections import OrderedDict
import argparse

import theano
import theano.tensor as T
from theano import config
from theano.sandbox.rng_mrg import MRG_RandomStreams as RandomStreams


def sigmoid(x):
  return 1. / (1. + np.exp(-x))

def numpy_floatX(data):
	return np.asarray(data, dtype=config.floatX)

def load_embedding(infile):
	Wemb = np.array(pickle.load(open(infile, 'rb'))).astype(config.floatX)
	return Wemb

def load_params(options):
	params = OrderedDict()
	weights = np.load(options['modelFile'])
	for k,v in weights.items():
		params[k] = v
	if len(options['embFile']) > 0: params['W_emb'] = np.array(pickle.load(open(options['embFile'], 'rb'))).astype(config.floatX)
	return params

def init_tparams(params, options):
	tparams = OrderedDict()
	for key, value in params.items():
		tparams[key] = theano.shared(value, name=key)
	return tparams

def _slice(_x, n, dim):
	if _x.ndim == 3:
		return _x[:, :, n*dim:(n+1)*dim]
	return _x[:, n*dim:(n+1)*dim]

def gru_layer(tparams, emb, name, hiddenDimSize):
	timesteps = emb.shape[0]
	if emb.ndim == 3: n_samples = emb.shape[1]
	else: n_samples = 1

	def stepFn(wx, h, U_gru):
		uh = T.dot(h, U_gru)
		r = T.nnet.sigmoid(_slice(wx, 0, hiddenDimSize) + _slice(uh, 0, hiddenDimSize))
		z = T.nnet.sigmoid(_slice(wx, 1, hiddenDimSize) + _slice(uh, 1, hiddenDimSize))
		h_tilde = T.tanh(_slice(wx, 2, hiddenDimSize) + r * _slice(uh, 2, hiddenDimSize))
		h_new = z * h + ((1. - z) * h_tilde)
		return h_new

	Wx = T.dot(emb, tparams['W_gru_'+name]) + tparams['b_gru_'+name]
	results, updates = theano.scan(fn=stepFn, sequences=[Wx], outputs_info=T.alloc(numpy_floatX(0.0), n_samples, hiddenDimSize), non_sequences=[tparams['U_gru_'+name]], name='gru_layer', n_steps=timesteps)

	return results
	
def build_model(tparams, options):
	alphaHiddenDimSize = options['alphaHiddenDimSize']
	betaHiddenDimSize = options['betaHiddenDimSize']

	x = T.tensor3('x', dtype=config.floatX)

	reverse_emb_t = x[::-1]
	reverse_h_a = gru_layer(tparams, reverse_emb_t, 'a', alphaHiddenDimSize)[::-1] * 0.5
	reverse_h_b = gru_layer(tparams, reverse_emb_t, 'b', betaHiddenDimSize)[::-1] * 0.5

	preAlpha = T.dot(reverse_h_a, tparams['w_alpha']) + tparams['b_alpha']
	preAlpha = preAlpha.reshape((preAlpha.shape[0], preAlpha.shape[1]))
	alpha = (T.nnet.softmax(preAlpha.T)).T

	beta = T.tanh(T.dot(reverse_h_b, tparams['W_beta']) + tparams['b_beta'])
	
	return x, alpha, beta

def padMatrixWithTime(seqs, times, options):
	lengths = np.array([len(seq) for seq in seqs]).astype('int32')
	n_samples = len(seqs)
	maxlen = np.max(lengths)

	x = np.zeros((maxlen, n_samples, options['inputDimSize'])).astype(config.floatX)
	t = np.zeros((maxlen, n_samples)).astype(config.floatX)
	for idx, (seq,time) in enumerate(zip(seqs,times)):
		for xvec, subseq in zip(x[:,idx,:], seq):
			xvec[subseq] = 1.
		t[:lengths[idx], idx] = time

	if options['useLogTime']: t = np.log(t + 1.)

	return x, t, lengths

def padMatrixWithoutTime(seqs, options):
	lengths = np.array([len(seq) for seq in seqs]).astype('int32')
	n_samples = len(seqs)
	maxlen = np.max(lengths)

	x = np.zeros((maxlen, n_samples, options['inputDimSize'])).astype(config.floatX)
	for idx, seq in enumerate(seqs):
		for xvec, subseq in zip(x[:,idx,:], seq):
			xvec[subseq] = 1.

	return x, lengths


class MortalityPredictor(object):
    def __init__(self, modelFile, codeFile, embFile='', useTime=False):

        # The filepath of the saved numpy model to load
        modelFile = modelFile
        codeFile = codeFile

        self.codes = pickle.load(open(codeFile, 'rb'))

        # The path to the Pickled file containing the representation vectors of medical codes.
        # If you are not using medical code representations, do not use this option
        # embFile='embFile.txt'
        # Note: NO EMB FILE HERE
        embFile=embFile

        useTime=useTime

        # type=int
        # The number of unique input medical codes
        inputDimSize=20000

        # type=int
        # The number of unique label medical codes
        numClass=1

        # Use logarithm of time duration to dampen the impact of the outliers
        useLogTime=True

        # The size of the visit embedding.
        # If you are not providing your own medical code vectors, you can specify this value
        embDimSize=128

        # If you are using randomly initialized code representations, always use this option.
        # If you are using an external medical code representations,
        # and you want to fine-tune them as you train RETAIN, use this option
        embFineTune=True

        # The size of the hidden layers of the GRU responsible for generating alpha weights
        alphaHiddenDimSize=128

        # The size of the hidden layers of the GRU responsible for generating beta weights
        betaHiddenDimSize=128

        # type=float
        # L2 regularization for the final classifier weight w
        L2_output=0.001

        # type=float
        # L2 regularization for the input embedding weight W_emb
        L2_emb=0.001

        # type=float
        # L2 regularization for the alpha generating weight w_alpha
        L2_alpha=0.001

        # type=float
        # L2 regularization for the input embedding weight W_beta
        L2_beta=0.001

        # type=float
        # A small value to prevent log(0)
        logEps=1e-8

        options = locals().copy()

        print('Loading the parameters ... ')
        params = load_params(options)
        tparams = init_tparams(params, options)

        options['alphaHiddenDimSize'] = params['w_alpha'].shape[0]
        options['betaHiddenDimSize'] = params['W_beta'].shape[0]
        options['inputDimSize'] = params['W_emb'].shape[0]

        print('Building the model ... ')
        x, alpha, beta =  build_model(tparams, options)
        get_result = theano.function(inputs=[x], outputs=[alpha, beta], name='get_result')
        
        self.params = params
        self.tparams = tparams
        self.get_result = get_result

        self.options = options

    # And calculate contribution score for each input
    def predict(self, x, t=None):
        if self.options['useTime']:
            raise NotImplementedError('Using time as an input is not supported yet.')
        else:
            xs, lengths = padMatrixWithoutTime([x], self.options)
            
            emb = np.dot(xs, self.params['W_emb'])
            
            alpha, beta = self.get_result(emb)
            
            alpha = alpha[:,0]
            beta = beta[:,0,:]
            
            ct = (alpha[:,None] * beta * emb[:,0,:]).sum(axis=0)
            y_t = sigmoid(np.dot(ct, self.params['w_output']) + self.params['b_output'])[0]
            
            patient = x
            contributions = []
            for i in range(len(patient)):
                visit = patient[i]
                c_per_visit = []
                for j in range(len(visit)):
                    code = visit[j]
                    contribution = np.dot(self.params['w_output'].flatten(), alpha[i] * beta[i] * self.params['W_emb'][code])
                    c_per_visit.append(contribution)
                contributions.append(c_per_visit)
                    
            
            return y_t, contributions

    @staticmethod
    def parseIcd9(code):
        code_str = ''
        if code.startswith('E'):
            code_str = code_str + 'E'
            code = code[1:]
        if len(code) > 3:
            code = code[0:3] + '.' + code[3:]
        code_str = code_str + code

        return code_str

    def icd9_to_sparse(self, code):
        code_str = 'D_' + code

        if code_str in self.codes:
            return self.codes[code_str]
        else:
            return None

    def predict_icd9(self, data):
        # Given a list of list of icd9 codes
        # convert into the vector representation needed by the model
        inputs = []

        for encounter in data:
            encounter_input = [diagnosis for diagnosis in map(lambda x: self.icd9_to_sparse(x), encounter) if diagnosis is not None]
            if len(encounter_input) > 0:
                inputs.append(encounter_input)

        if len(inputs) > 0:
            return self.predict(inputs)
        else:
            return None, None

    def incremental_predict_icd9(self, data):
        preds = []
        contribs = []
        for i in range(len(data)):
            inputs = data[:i+1]
            p, c = self.predict_icd9(inputs)
            if p is not None and c is not None:
                preds.append(p)
                contribs.append(c)

        return preds, contribs


if __name__ == '__main__':

    sample_item = [[76, 507, 160, 30], [664, 1665, 1206, 61, 193, 141, 7, 2186, 123]]
    small_test_set = [sample_item]

    model = MortalityPredictor('models/mimic3.model.npz', 'models/mimic3.types')

    # Should output 0.13253019598600665
    print(model.predict(sample_item[:1]))
    print(model.predict(sample_item))
    
    # Should output 0.5791347762818906
    print(model.predict([[1, 2, 3], [4, 5, 6]]))
    
