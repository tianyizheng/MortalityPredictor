import sys, random
import numpy as np
import _pickle as pickle
from collections import OrderedDict
import argparse

import theano
import theano.tensor as T
from theano import config
from theano.sandbox.rng_mrg import MRG_RandomStreams as RandomStreams


def unzip(zipped):
    new_params = OrderedDict()
    for key, value in zipped.items():
        new_params[key] = value.get_value()
    return new_params

def numpy_floatX(data):
    return np.asarray(data, dtype=config.floatX)

def get_random_weight(dim1, dim2, left=-0.1, right=0.1):
    return np.random.uniform(left, right, (dim1, dim2)).astype(config.floatX)

def load_embedding(infile):
    Wemb = np.array(pickle.load(open(infile, 'rb'))).astype(config.floatX)
    return Wemb

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

def init_params(options):
    params = OrderedDict()
    useTime = options['useTime']
    embFile = options['embFile']
    embDimSize = options['embDimSize']
    inputDimSize = options['inputDimSize']
    alphaHiddenDimSize= options['alphaHiddenDimSize']
    betaHiddenDimSize= options['betaHiddenDimSize']
    numClass = options['numClass']

    if len(embFile) > 0:
        print('using external code embedding')
        params['W_emb'] = load_embedding(embFile)
        embDimSize = params['W_emb'].shape[1]
    else:
        print('using randomly initialized code embedding')
        params['W_emb'] = get_random_weight(inputDimSize, embDimSize)

    gruInputDimSize = embDimSize
    if useTime: gruInputDimSize = embDimSize + 1

    params['W_gru_a'] = get_random_weight(gruInputDimSize, 3*alphaHiddenDimSize)
    params['U_gru_a'] = get_random_weight(alphaHiddenDimSize, 3*alphaHiddenDimSize)
    params['b_gru_a'] = np.zeros(3 * alphaHiddenDimSize).astype(config.floatX)

    params['W_gru_b'] = get_random_weight(gruInputDimSize, 3*betaHiddenDimSize)
    params['U_gru_b'] = get_random_weight(betaHiddenDimSize, 3*betaHiddenDimSize)
    params['b_gru_b'] = np.zeros(3 * betaHiddenDimSize).astype(config.floatX)

    params['w_alpha'] = get_random_weight(alphaHiddenDimSize, 1)
    params['b_alpha'] = np.zeros(1).astype(config.floatX)
    params['W_beta'] = get_random_weight(betaHiddenDimSize, embDimSize)
    params['b_beta'] = np.zeros(embDimSize).astype(config.floatX)
    params['w_output'] = get_random_weight(embDimSize, numClass)
    params['b_output'] = np.zeros(numClass).astype(config.floatX)
    return params

def load_params(options):
    return np.load(options['modelFile'])

def init_tparams(params, options):
    tparams = OrderedDict()
    for key, value in params.items():
        if not options['embFineTune'] and key == 'W_emb': continue
        tparams[key] = theano.shared(value, name=key)
    return tparams

def dropout_layer(state_before, use_noise, trng, keep_prob=0.5):
    proj = T.switch(
        use_noise,
        state_before * trng.binomial(state_before.shape, p=keep_prob, n=1, dtype=state_before.dtype) / keep_prob,
        state_before)
    return proj

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

def build_model(tparams, options, W_emb=None):
    keep_prob_emb = options['keepProbEmb']
    keep_prob_context = options['keepProbContext']
    alphaHiddenDimSize = options['alphaHiddenDimSize']
    betaHiddenDimSize = options['betaHiddenDimSize']

    trng = RandomStreams(1234)
    use_noise = theano.shared(numpy_floatX(0.))
    useTime = options['useTime']

    x = T.tensor3('x', dtype=config.floatX)
    t = T.matrix('t', dtype=config.floatX)
    y = T.vector('y', dtype=config.floatX)
    lengths = T.ivector('lengths')

    n_timesteps = x.shape[0]
    n_samples = x.shape[1]

    if options['embFineTune']: emb = T.dot(x, tparams['W_emb'])
    else: emb = T.dot(x, W_emb)

    if keep_prob_emb < 1.0: emb = dropout_layer(emb, use_noise, trng, keep_prob_emb)

    if useTime: temb = T.concatenate([emb, t.reshape([n_timesteps,n_samples,1])], axis=2) #Adding the time element to the embedding
    else: temb = emb

    def attentionStep(att_timesteps):
        reverse_emb_t = temb[:att_timesteps][::-1]
        reverse_h_a = gru_layer(tparams, reverse_emb_t, 'a', alphaHiddenDimSize)[::-1] * 0.5
        reverse_h_b = gru_layer(tparams, reverse_emb_t, 'b', betaHiddenDimSize)[::-1] * 0.5

        preAlpha = T.dot(reverse_h_a, tparams['w_alpha']) + tparams['b_alpha']
        preAlpha = preAlpha.reshape((preAlpha.shape[0], preAlpha.shape[1]))
        alpha = (T.nnet.softmax(preAlpha.T)).T

        beta = T.tanh(T.dot(reverse_h_b, tparams['W_beta']) + tparams['b_beta'])
        c_t = (alpha[:,:,None] * beta * emb[:att_timesteps]).sum(axis=0)
        return c_t

    counts = T.arange(n_timesteps)+ 1
    c_t, updates = theano.scan(fn=attentionStep, sequences=[counts], outputs_info=None, name='attention_layer', n_steps=n_timesteps)
    if keep_prob_context < 1.0: c_t = dropout_layer(c_t, use_noise, trng, keep_prob_context)

    preY = T.nnet.sigmoid(T.dot(c_t, tparams['w_output']) + tparams['b_output'])
    preY = preY.reshape((preY.shape[0], preY.shape[1]))
    indexRow = T.arange(n_samples)
    y_hat = preY.T[indexRow, lengths - 1]

    logEps = options['logEps']
    cross_entropy = -(y * T.log(y_hat + logEps) + (1. - y) * T.log(1. - y_hat + logEps))
    cost_noreg = T.mean(cross_entropy)

    cost = cost_noreg + options['L2_output'] * (tparams['w_output']**2).sum() + options['L2_alpha'] * (tparams['w_alpha']**2).sum() + options['L2_beta'] * (tparams['W_beta']**2).sum()

    if options['embFineTune']: cost += options['L2_emb'] * (tparams['W_emb']**2).sum()

    if useTime: return use_noise, x, y, t, lengths, cost_noreg, cost, y_hat
    else: return use_noise, x, y, lengths, cost_noreg, cost, y_hat


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
        # Decides how much you want to keep during the dropout between the embedded input and
        # the alpha & beta generation process
        keepProbEmb=0.5

        # type=float
        # Decides how much you want to keep during the dropout between
        # the context vector c_i and the final classifier
        keepProbContext=0.5

        # type=float
        # A small value to prevent log(0)
        logEps=1e-8

        options = locals().copy()

        print('Initializing the parameters ... ')
        params = init_params(options)
        if len(modelFile) > 0: params = load_params(options)
        tparams = init_tparams(params, options)

        print('Building the model ... ')
        if useTime and embFineTune:
            print('using time information, fine-tuning code representations')
            use_noise, x, y, t, lengths, cost_noreg, cost, y_hat =  build_model(tparams, options)
            get_prediction = theano.function(inputs=[x, t, lengths], outputs=y_hat, name='get_prediction')
        elif useTime and not embFineTune:
            print('using time information, not fine-tuning code representations')
            W_emb = theano.shared(params['W_emb'], name='W_emb')
            use_noise, x, y, t, lengths, cost_noreg, cost, y_hat =  build_model(tparams, options, W_emb)
            get_prediction = theano.function(inputs=[x, t, lengths], outputs=y_hat, name='get_prediction')
        elif not useTime and embFineTune:
            print('not using time information, fine-tuning code representations')
            use_noise, x, y, lengths, cost_noreg, cost, y_hat =  build_model(tparams, options)
            get_prediction = theano.function(inputs=[x, lengths], outputs=y_hat, name='get_prediction')
        elif not useTime and not embFineTune:
            print('not using time information, not fine-tuning code representations')
            W_emb = theano.shared(params['W_emb'], name='W_emb')
            use_noise, x, y, lengths, cost_noreg, cost, y_hat =  build_model(tparams, options, W_emb)
            get_prediction = theano.function(inputs=[x, lengths], outputs=y_hat, name='get_prediction')

        use_noise.set_value(0.)

        self.pred = get_prediction
        self.options = options

    def predict(self, x, t=None):
        if self.options['useTime']:
            xs, ts, lengths = padMatrixWithTime(batchX, batchT, options)
            return self.preed(xs, ts, lengths)[0]
        else:
            xs, lengths = padMatrixWithoutTime([x], self.options)
            return self.pred(xs, lengths)[0]

    def icd9_to_sparse(self, code):
        code_str = 'D_'
        if code.startswith('E'):
            code_str = code_str + 'E'
            code = code[1:]
        if len(code) > 3:
            code = code[0:3] + '.' + code[3:]
        code_str = code_str + code

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
            return None


if __name__ == '__main__':

    sample_item = [[76, 507, 160, 30], [664, 1665, 1206, 61, 193, 141, 7, 2186, 123]]
    small_test_set = [sample_item]

    model = MortalityPredictor('models/mimic3.model.npz')

    # Should output 0.13253019598600665
    p = model.predict(sample_item)
    print(p)

    # Should output 0.5791347762818906
    print(model.predict([[1, 2, 3], [4, 5, 6]]))
