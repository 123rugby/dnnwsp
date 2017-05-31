"""
This tutorial introduces the multilayer perceptron using Theano.

 A multilayer perceptron is a logistic regressor where
instead of feeding the input to the logistic regression you insert a
intermediate layer, called the hidden layer, that has a nonlinear
activation function (usually tanh or sigmoid) . One can use many such
hidden layers making the architecture deep. The tutorial will also tackle
the problem of MNIST digit classification.

.. math::

    f(x) = G( b^{(2)} + W^{(2)}( s( b^{(1)} + W^{(1)} x))),

References:

    - textbooks: "Pattern Recognition and Machine Learning" -
                 Christopher M. Bishop, section 5

"""
__docformat__ = 'restructedtext en'

import os
import sys
import timeit

import numpy
import numpy as np
import scipy.io as sio

import theano
import theano.tensor as T

from logistic_sgd import LogisticRegression
import StringIO 

from numpy import linalg as LA


# def hsp_fnc(betaval_L1, W, max_beta, tg_hsp, beta_lrate):
#     W = W.get_value(borrow=True)
#     Wvec = W.flatten();
#     sqrt_nsamps = pow((Wvec.shape[0]),0.5)
#     
#     n1_W = LA.norm(Wvec,1);    n2_W = LA.norm(Wvec,2);
#     hspvalue = (sqrt_nsamps-(n1_W/n2_W))/(sqrt_nsamps-1);
# 
#     betaval_L1 -= beta_lrate*np.sign(hspvalue-tg_hsp) 
# 
#     betaval_L1 = 0 if betaval_L1<0 else betaval_L1
#     betaval_L1 = max_beta if betaval_L1>max_beta else betaval_L1
# 
#     return [hspvalue, betaval_L1]

def hsp_fnc(beta_val_L1, W, max_beta, tg_hsp, beta_lrate,flag_inv_control):
    W = np.array(W.get_value(borrow=True));
    
    cnt_L1_ly = beta_val_L1;
    
    if flag_inv_control==1:
        [dim, nodes] = W.shape
        hsp_vec = np.zeros((1,nodes));  
        tg_hsp_vec = np.ones(nodes)*tg_hsp;
        sqrt_nsamps = pow(dim,0.5)
        n1_W = LA.norm(W,1,axis=0);    n2_W = LA.norm(W,2,axis=0);
        hsp_vec = (sqrt_nsamps - (n1_W/n2_W))/(sqrt_nsamps-1)
    
        cnt_L1_ly -= beta_lrate*np.sign(hsp_vec-tg_hsp_vec)

        for ii in xrange(0,nodes):
            cnt_L1_ly[ii] = 0 if cnt_L1_ly[ii] < 0 else cnt_L1_ly[ii]
            cnt_L1_ly[ii] = max_beta if cnt_L1_ly[ii]>max_beta else cnt_L1_ly[ii]
            
    else:
        Wvec = W.flatten();
        sqrt_nsamps = pow((Wvec.shape[0]),0.5)
    
        n1_W = LA.norm(Wvec,1);    n2_W = LA.norm(Wvec,2);
        hspvalue = (sqrt_nsamps-(n1_W/n2_W))/(sqrt_nsamps-1);

        cnt_L1_ly -= beta_lrate*np.sign(hspvalue-tg_hsp) 
        
        cnt_L1_ly = 0 if cnt_L1_ly<0 else cnt_L1_ly
        cnt_L1_ly = max_beta if cnt_L1_ly>max_beta else cnt_L1_ly

    return [hspvalue, cnt_L1_ly]

# def gradient_updates_momentum(cost, params, learning_rate, momentum):
def gradient_updates_momentum(cost, params, bnupdates, learning_rate, momentum):
    updates = []
    
    for bnupdate in bnupdates:
        
        updates.append(bnupdate)

    for param in params:

        param_update = theano.shared(param.get_value()*0., broadcastable=param.broadcastable)
        updates.append((param, param - learning_rate*param_update))
        updates.append((param_update, momentum*param_update + (1. - momentum)*T.grad(cost, param)))
    return updates

def relu1(x):
    return T.switch(x<0, 0, x)

def RMSprop(cost, params, learning_rate, rho=0.9, epsilon=1e-6):
    all_grads = [T.grad(cost, param) for param in params]

    updates = []
    for p, g in zip(params, all_grads):
        acc = theano.shared(p.get_value() * 0.)
        acc_new = rho * acc + (1 - rho) * g ** 2
        gradient_scaling = T.sqrt(acc_new + epsilon)
        g = g / gradient_scaling
        updates.append((acc, acc_new))
        updates.append((p, p - learning_rate * g))
    return updates

def adam(cost, params, learning_rate, b1=0.9, b2=0.999, e=1e-8,
         gamma=1-1e-8):
    
    updates = []
    all_grads = [T.grad(cost, param) for param in params]

#     all_grads = T.grad(cost, params)
    alpha = learning_rate
    t = theano.shared(np.float32(1))
    b1_t = b1*gamma**(t-1)   #(Decay the first moment running average coefficient)

    for theta_previous, g in zip(params, all_grads):
        m_previous = theano.shared(np.zeros(theta_previous.get_value().shape,
                                            dtype=theano.config.floatX))
        v_previous = theano.shared(np.zeros(theta_previous.get_value().shape,
                                            dtype=theano.config.floatX))
        m = b1_t*m_previous + (1 - b1_t)*g                             # (Update biased first moment estimate)
        v = b2*v_previous + (1 - b2)*g**2                              # (Update biased second raw moment estimate)
        m_hat = m / (1-b1**t)                                          # (Compute bias-corrected first moment estimate)
        v_hat = v / (1-b2**t)                                          # (Compute bias-corrected second raw moment estimate)
        theta = theta_previous - (alpha * m_hat) / (T.sqrt(v_hat) + e) #(Update parameters)

        updates.append((m_previous, m))
        updates.append((v_previous, v))
        updates.append((theta_previous, theta) )
    updates.append((t, t + 1.))
    return updates

# start-snippet-1
class HiddenLayer(object):
    def __init__(self, rng, input, n_in, n_out, W=None, b=None,
                 activation=T.nnet.sigmoid):

        self.input = input
        # end-snippet-1

        if W is None:
            W_values = numpy.asarray(
                rng.uniform(
                    low=-4*numpy.sqrt(6. / (n_in + n_out)),
                    high=4*numpy.sqrt(6. / (n_in + n_out)),
                    size=(n_in, n_out)
                ),
                dtype=theano.config.floatX
            )
#             if activation == theano.tensor.nnet.sigmoid:
#                 W_values *= 4
            W = theano.shared(value=W_values, name='W', borrow=True)
            
        if b is None:
            b_values = numpy.zeros((n_out,), dtype=theano.config.floatX)
            b = theano.shared(value=b_values, name='b', borrow=True)

        self.W = W
        self.b = b

        lin_output = T.dot(input, self.W) + self.b
        self.output = (
            lin_output if activation is None
            else activation(lin_output)
        )
        # parameters of the model
        self.params = [self.W, self.b]
        
        self.chk_pre_output = theano.shared(numpy.zeros((60,n_out), dtype=theano.config.floatX), name='chk_pre_output', borrow=True)
        self.updates = [(self.chk_pre_output, lin_output)]

# start-snippet-2
class MLP(object):
    
    def __init__(self, rng, input, n_nodes, pretrained=None, activation=T.nnet.sigmoid):

        if len(n_nodes) > 2:
            self.hiddenLayer = []
            
            for i in xrange(len(n_nodes)-2):
                
                if i == 0:
                    hidden_input = input
                else:
                    hidden_input = self.hiddenLayer[i-1].output
                    
                self.hiddenLayer.append(
                    HiddenLayer(
                        rng=rng,
                        input=hidden_input,
                        n_in=n_nodes[i],
                        n_out=n_nodes[i+1],
                        W=None,
                        b=None,
                        activation=activation
                    )
                )
        # The logistic regression layer gets as input the hidden units
        # of the hidden layer
        if len(n_nodes) == 2:
            logistic_input = input
        else:
            logistic_input = self.hiddenLayer[len(n_nodes)-3].output
                    
        self.logRegressionLayer = LogisticRegression(
            input=logistic_input,
            n_in=n_nodes[len(n_nodes)-2],
            n_out=n_nodes[len(n_nodes)-1]
        )
        # end-snippet-2 start-snippet-3
        
        self.L1 = []
        for i in xrange(len(n_nodes)-2):
            self.L1.append(abs(self.hiddenLayer[i].W).sum() )
        self.L1.append(abs(self.logRegressionLayer.W).sum() )    
        
        self.L2_sqr = 0
        for i in xrange(len(n_nodes)-2):
            self.L2_sqr += (self.hiddenLayer[i].W ** 2).sum()
        self.L2_sqr += ((self.logRegressionLayer.W ** 2).sum())

        # negative log likelihood of the MLP is given by the negative
        # log likelihood of the output of the model, computed in the
        # logistic regression layer
        self.negative_log_likelihood = (
            self.logRegressionLayer.negative_log_likelihood
        )
        # same holds for the function computing the number of errors
        self.errors = self.logRegressionLayer.errors
        self.mse = self.logRegressionLayer.mse
        
        self.params = []
        if len(n_nodes) > 2:
            for i in xrange(len(n_nodes)-2):
                self.params.extend(self.hiddenLayer[i].params)
        self.params.extend(self.logRegressionLayer.params)
        
        self.oldparams = [theano.shared(numpy.zeros(p.get_value(borrow=True).shape, dtype=theano.config.floatX)) for p in self.params]

        # keep track of model input
        self.input = input
        
        self.bnUpdates = []
        for i in xrange(len(n_nodes)-2):
            self.bnUpdates.extend(self.hiddenLayer[i].updates)
        
def test_mlp(n_nodes=[74484,100,100,100,4],  # input-hidden-nodees
             datasets='lhrhadvs_sample_data.mat',  # load data
             # activation:  # sigmoid function: T.nnet.sigmoid, hyperbolic tangent function: T.tanh, Rectified Linear Unit: relu1
             batch_size = 100, n_epochs = 500, learning_rate=0.001,activation = T.tanh,
             beginAnneal=200, min_annel_lrate = 1e-4, decay_rate = 1e-4, momentum_val=0.00,
             
             # Select optimizer 'Grad' for GradientDescentOptimizer, 'Adam' for AdamOptimizer, 'Rmsp' for RMSPropOptimizer
             optimizer_algorithm='Grad',
                       
             # Parameters for the node-wise control of weight sparsity
             # if you have three hidden layer, the number of target Hoyer's sparseness should be same 
             tg_hspset=[0.7, 0.5, 0.5], # Target sparsity
             max_beta=[0.05, 0.9, 0.9], # Maximum beta changes
             
            # Parameters for the layer-wise control of weight sparsity 
             # tg_hspset=[0.7, 0.5, 0.5], # Target sparsity 
             # max_beta=[0.05, 0.8, 0.8], # Maximum beta changes
             beta_lrates = 1e-2,        L2_reg = 1e-5,
             
            # flag_inv_control =1 is the node-wise control of weight sparsity 
            # flag_inv_control =0 is the layer-wise control of weight sparsity
            
             flag_inv_control = 0,
             # Save path  
             sav_path = '/home/khc/workspace/prni2017',  
              ):
                                
    datasets=sio.loadmat(datasets) # load datasets
    
    ############# lhrhadvs_sample_data.mat #############
    # train_x  = 240 volumes x 74484 voxels  
    # train_x  = 240 volumes x 1 [0:left-hand clenching task, 1:right-hand clenching task, 2:auditory task, 3:visual task]
    # test_x  = 120 volumes x 74484 voxels
    # test_y  = 120 volumes x 1 [0:left-hand clenching task, 1:right-hand clenching task, 2:auditory task, 3:visual task]
    ############################################################

    train_x = datasets['train_x']; 
    train_y = datasets['train_y'];
    test_x  = datasets['test_x'];
    test_y  = datasets['test_y'];
    
    train_set_x = theano.shared(numpy.asarray(train_x, dtype=theano.config.floatX))
    train_set_y = T.cast(theano.shared(train_y.flatten(),borrow=True),'int32')
    
    test_set_x = theano.shared(numpy.asarray(test_x, dtype=theano.config.floatX))
    test_set_y = T.cast(theano.shared(test_y.flatten(),borrow=True),'int32')

    # compute number of minibatches for training, validation and testing
    n_train_batches = train_set_x.get_value(borrow=True).shape[0] / batch_size
    n_test_batches = test_set_x.get_value(borrow=True).shape[0] / batch_size

    #####################
    # BUILD ACTUAL MODEL #
    ######################
    print '... building the model'

    # allocate symbolic variables for the data
    index = T.lscalar()  # index to a [mini]batch
    x = T.matrix('x')  
    y = T.ivector('y')  # the labels are presented as 1D vector of [int] labels

    l1_penalty_layer = T.fvector() #  L1-norm regularization parameter
    ln_rate = T.scalar(name='learning_rate') # learning rate
    momentum = T.scalar(name='momentum')
                 
    rng = numpy.random.RandomState(1234)

    # construct the MLP class
    classifier = MLP(
        rng=rng,
        input=x,
        n_nodes = n_nodes,
        activation = activation,
        pretrained = None
    )

    # cost function
    cost = (classifier.negative_log_likelihood(y))
    
    if flag_inv_control==1:
        for i in xrange(len(n_nodes)-2):
            node_size = n_nodes[i+1]; tg_index = np.arange((i * node_size),((i + 1) * node_size));
            cost += (T.dot(abs(classifier.hiddenLayer[i].W),l1_penalty_layer[tg_index])).sum();
    else:
        for i in xrange(len(n_nodes)-2):
            cost += l1_penalty_layer[i] * classifier.L1[i]

    cost += L2_reg * classifier.L2_sqr    

    
    updates_test = []
    for hiddenlayer in classifier.hiddenLayer:
        for i in xrange(1):
            updates_test.append( hiddenlayer.updates[i] )
           
    test_model = theano.function(
        inputs=[index],
        outputs=[classifier.errors(y),classifier.mse(batch_size,n_nodes[-1],y)],
        updates=updates_test,
        givens={
            x: test_set_x[index * batch_size:(index + 1) * batch_size],
            y: test_set_y[index * batch_size:(index + 1) * batch_size]
        }
    )
    
    updates =[];
    # Select optimizer 'Grad' for GradientDescentOptimizer, 'Adam' for AdamOptimizer, 'Rmsp' for RMSPropOptimizer
    if optimizer_algorithm=='Grad':
        gparams = [T.grad(cost, param) for param in classifier.params]
        
        for param, gparam, oldparam in zip(classifier.params, gparams, classifier.oldparams):
            delta = ln_rate * gparam + momentum * oldparam
            updates.append((param, param - delta))
            updates.append((oldparam, delta))

    elif optimizer_algorithm=='Adam':
        updates = adam(cost, classifier.params, learning_rate)
        
    elif optimizer_algorithm=='Rmsp' :
        updates = RMSprop(cost, classifier.params, learning_rate)
    
    # compiling a Theano function `train_model` that returns the cost, but
    # in the same time updates the parameter of the model based on the rules
    # defined in `updates`
    train_model = theano.function(
        inputs=[index, l1_penalty_layer,ln_rate,momentum],
        outputs=[cost,classifier.errors(y),classifier.mse(batch_size,n_nodes[-1],y)],
        updates=updates,
        givens={
            x: train_set_x[index * batch_size: (index + 1) * batch_size],
            y: train_set_y[index * batch_size: (index + 1) * batch_size]
        },
        allow_input_downcast = True,
        on_unused_input = 'ignore'
    )

    ###############
    # TRAIN MODEL #
    ###############
    print '... training'

    # early-stopping parameters
    test_score = 0. 
    start_time = timeit.default_timer()

    epoch = 0;    done_looping = False
    
    # To check training
    train_errors = np.zeros(n_epochs);    test_errors = np.zeros(n_epochs);
    train_mse = np.zeros(n_epochs);    test_mse = np.zeros(n_epochs);
    lrs = np.zeros(n_epochs); lrate_list = np.zeros(n_epochs);
    
    # define variables
    if flag_inv_control==1:
        hsp_avg_vals =[]; L1_beta_avg_vals=[];  all_hsp_vals =[]; all_L1_beta_vals=[];
        L1_beta_vals = np.zeros(np.sum(n_nodes[1:(len(n_nodes)-1)]));
        cnt_hsp_val = np.zeros(len(n_nodes)-2); 
        cnt_beta_val = np.zeros(len(n_nodes)-2);
        
        for i in xrange(len(n_nodes)-2):
            hsp_avg_vals.append(np.zeros((n_epochs,n_nodes[i+1])));
            L1_beta_avg_vals.append(np.zeros((n_epochs,n_nodes[i+1])));
    
            all_hsp_vals.append(np.zeros((n_epochs,n_nodes[i+1])));
            all_L1_beta_vals.append(np.zeros((n_epochs,n_nodes[i+1])));
        
    else:
        all_hsp_vals = np.zeros((n_epochs,len(n_nodes)-2));  
        all_L1_beta_vals = np.zeros((n_epochs,len(n_nodes)-2));
        
        L1_beta_vals= np.zeros(len(n_nodes)-2)
        cnt_hsp_val = np.zeros(len(n_nodes)-2);    

     # training 
    while (epoch < n_epochs) and (not done_looping):
        epoch = epoch + 1
        minibatch_all_avg_error = []; minibatch_all_avg_mse = []

        for minibatch_index in xrange(n_train_batches):
            disply_text = StringIO.StringIO();
            minibatch_avg_cost, minibatch_avg_error, minibatch_avg_mse = train_model(minibatch_index, L1_beta_vals,learning_rate,momentum_val)
            minibatch_all_avg_error.append(minibatch_avg_error)
            minibatch_all_avg_mse.append(minibatch_avg_mse)
             
            if flag_inv_control==1:
                for i in xrange(len(n_nodes)-2):
                    node_size = n_nodes[i+1]; tg_index = np.arange((i * node_size),((i + 1) * node_size));
                    tmp_L1_beta_vals = L1_beta_vals[tg_index]
                    [all_hsp_vals[i][epoch-1], L1_beta_vals[tg_index]] = hsp_fnc(tmp_L1_beta_vals,classifier.hiddenLayer[i].W,max_beta[i],tg_hspset[i],beta_lrates,flag_inv_control);
                    all_L1_beta_vals[i][epoch-1]= L1_beta_vals[tg_index];
            else:
                for i in xrange(len(n_nodes)-2):
                    [cnt_hsp_val[i], L1_beta_vals[i]] = hsp_fnc(L1_beta_vals[i],classifier.hiddenLayer[i].W,max_beta[i],tg_hspset[i],beta_lrates,flag_inv_control);
                
            # iteration number
            iter = (epoch - 1) * n_train_batches + minibatch_index
            # test it on the test set
            test_losses = []; test_mses = []
            for i in xrange(n_test_batches):
                test_losses.append(test_model(i)[0])
                test_mses.append(test_model(i)[1])
            test_score = numpy.mean(test_losses);
             
        # Begin Annealing
        if beginAnneal == 0:
            learning_rate = learning_rate * 1.0
        elif epoch > beginAnneal:
            learning_rate = max(min_annel_lrate, (-decay_rate*epoch + (1+decay_rate*beginAnneal)) * learning_rate )
            
        # Save variables to check training
        train_errors[epoch-1] = np.mean(minibatch_all_avg_error)*100
        test_errors[epoch-1] = test_score*100
        train_mse[epoch-1] = np.mean(minibatch_all_avg_mse)
        test_mse[epoch-1] = np.mean(test_mses)
        
        if flag_inv_control ==1:
            disply_text.write("Node-wise control, epoch %i/%d, Tr.err= %.2f, Ts.err= %.2f, lr = %.6f, " % (epoch,n_epochs,train_errors[epoch-1],test_errors[epoch-1],learning_rate))

            for layer_idx in xrange(len(n_nodes)-2):
                cnt_hsp_val[layer_idx] = np.mean(all_hsp_vals[layer_idx][epoch-1])
                cnt_beta_val[layer_idx] = np.mean(all_L1_beta_vals[layer_idx][epoch-1])
                
        else:  
            disply_text.write("Layer-wise control, epoch %i/%d, Tr.err= %.2f, Ts.err= %.2f, lr = %.6f, " % (epoch,n_epochs,train_errors[epoch-1],test_errors[epoch-1],learning_rate))
            
            all_hsp_vals[epoch-1,:] = cnt_hsp_val;
            all_L1_beta_vals[epoch-1,:] = L1_beta_vals;
            
        for layer_idx in xrange(len(n_nodes)-2):
            if (layer_idx==len(n_nodes)-3):
                disply_text.write("hsp_l%d = %.2f/%.2f, beta_l%d = %.2f" % (layer_idx+1,cnt_hsp_val[layer_idx],tg_hspset[layer_idx],layer_idx+1,L1_beta_vals[layer_idx]))
            else:
                disply_text.write("hsp_l%d = %.2f/%.2f, beta_l%d = %.2f, " % (layer_idx+1,cnt_hsp_val[layer_idx],tg_hspset[layer_idx],layer_idx+1,L1_beta_vals[layer_idx]))
                    
        # Display saved variables                 
        print disply_text.getvalue()
        disply_text.close()
        
        lrs[epoch-1] = learning_rate
                    
    if not os.path.exists(sav_path):
        os.makedirs(sav_path)
        
    end_time = timeit.default_timer()
    cst_time = (end_time - start_time) / 60.
    print >> sys.stderr, ('\n The code for file ' + os.path.split(__file__)[1] +
                          ' ran for %.2fm' % ((end_time - start_time) / 60.))
     
    sav_text = StringIO.StringIO();
    for layer_idx in xrange(len(n_nodes)-2):
        if layer_idx==len(n_nodes)-3:
            sav_text.write("%d" % (n_nodes[layer_idx+1]))
        else:
            sav_text.write("%d-" % (n_nodes[layer_idx+1]))

    sav_name = '%s/mlp_rst_inv_%s.mat' % (sav_path,sav_text.getvalue())
    sav_text.close()
        
    data_variable = {}; 

    for i in xrange(len(n_nodes)-1):
        if (i==len(n_nodes)-2): 
            W_name = "w%d" %(i+1); b_name = "b%d" % (i+1); 
            data_variable[W_name] = classifier.logRegressionLayer.W.get_value(borrow=True)
            data_variable[b_name] = classifier.logRegressionLayer.b.get_value(borrow=True)
        else:
            W_name = "w%d" %(i+1); b_name = "b%d" % (i+1)
            data_variable[W_name] = classifier.hiddenLayer[i].W.get_value(borrow=True)
            data_variable[b_name] = classifier.hiddenLayer[i].b.get_value(borrow=True)
            
    data_variable['hsp_vals'] = all_hsp_vals;  
    data_variable['L1_vals'] =  all_L1_beta_vals;
    data_variable['train_errors'] = train_errors;    data_variable['test_errors'] = test_errors;
    data_variable['l_rate'] = lrs;
    
    data_variable['momtentum'] = momentum_val;    data_variable['beginAnneal'] = beginAnneal;    data_variable['decay_lr'] = decay_rate;
    data_variable['beta_lrates'] = beta_lrates;    data_variable['max_beta'] = max_beta;    data_variable['tg_hspset'] = tg_hspset;
    data_variable['batch_size'] = batch_size;    data_variable['n_epochs'] = n_epochs;    data_variable['min_annel_lrate'] = min_annel_lrate;
    data_variable['n_nodes'] = n_nodes; data_variable['lrate_list'] = lrate_list;
    
    sio.savemat(sav_name,data_variable)

    print '...done!'

if __name__ == '__main__':
    test_mlp()
        