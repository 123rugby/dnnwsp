# -*- coding: utf-8 -*-

import matplotlib.pyplot as plt
import tensorflow as tf
import numpy as np
from numpy import linalg as LA
import scipy.io
import os.path

################################################# Customization part #################################################
"""
autoencoder or not
"""
autoencoder=False

"""
Select the sparsity control mode
'layer' for layer wise sparsity control
'node' for node wise sparsity control
"""
mode = 'node'

"""
Select optimizer
'G' for GradientDescentOptimizer
'Ada' for AdagradOptimizer
'M' for MomentumOptimizer
'Adam' for AdamOptimizer
'R' for RMSPropOptimizer
"""
optimizer_algorithm='Ada'

"""
Load your own data here
"""
dataset = scipy.io.loadmat('/home/hailey/01_study/prni2017_samples/lhrhadvs_sample_data2.mat')


""" 
Set the number of nodes for input, output and each hidden layer here
"""
nodes=[74484,100,100,100,4]

"""
Set learning parameters
"""
# Set total epoch
total_epoch=30
# Set mini batch size
batch_size=100
# Let anealing to begin after 5th epoch
beginAnneal=20  
# Set initial learning rate and minimum                     
lr_init = 1e-2    
min_lr = 1e-4

# Set learning rate of beta for weight sparsity control
lr_beta = 1e-3
# Set L2 parameter for L2 regularization
L2_param= 1e-5


"""
Set maximum beta value of each hidden layer (usually 0.01~0.2) 
and set target sparsness value (0:dense~1:sparse)
"""
max_beta = [0.01,0.02,0.02]
tg_hsp = [0.5,0.5,0.5]


################################################# Input data part #################################################

# Split the dataset into traning input
train_input = dataset['train_x']
# Split the dataset into test input
test_input = dataset['test_x']



if autoencoder==False:  
    # Split the dataset into traning output 
    train_output = np.zeros((np.shape(dataset['train_y'])[0],np.max(dataset['train_y'])+1))
    # trainsform classes into One-hot
    for i in np.arange(np.shape(dataset['train_y'])[0]):
        train_output[i][dataset['train_y'][i][0]]=1 
    dataset['train_y']
    
    # Split the dataset into test output
    test_output = np.zeros((np.shape(dataset['test_y'])[0],np.max(dataset['test_y'])+1))
    # trainsform classes into One-hot
    for i in np.arange(np.shape(dataset['test_y'])[0]):
        test_output[i][dataset['test_y'][i][0]]=1 




################################################# Structure part #################################################



# We need 'node_index' for split placeholder (hidden_nodes=[100, 100, 100] -> nodes_index=[0, 100, 200, 300])
nodes_index= [int(np.sum(nodes[1:i+1])) for i in np.arange(np.shape(nodes)[0]-1)]

# Make placeholders to make our model in advance, then fill the values later when training or testing
X=tf.placeholder(tf.float32,[None,nodes[0]])
Y=tf.placeholder(tf.float32,[None,nodes[-1]])

# Make weight variables which are randomly initialized
w_init=[tf.div(tf.random_normal([nodes[i],nodes[i+1]]), tf.sqrt(float(nodes[i])/2)) for i in np.arange(np.shape(nodes)[0]-1)]
w=[tf.Variable(w_init[i], dtype=tf.float32) for i in np.arange(np.shape(nodes)[0]-1)]
# Make bias variables which are randomly initialized
b=[tf.Variable(tf.random_normal([nodes[i+1]])) for i in np.arange(np.shape(nodes)[0]-1)]

# Finally build our DNN model 
layer=[0.0]*(np.shape(nodes)[0]-1)
for i in np.arange(np.shape(nodes)[0]-1):
    
    # Input layer
    if i==0:
        layer[i]=tf.add(tf.matmul(X,w[i]),b[i])
        layer[i]=tf.nn.sigmoid(layer[i])
        
    # Output layer 
    elif i==np.shape(nodes)[0]-2:
        layer[i]=tf.add(tf.matmul(layer[i-1],w[i]),b[i])
    
    # The other layers    
    else:     
        layer[i]=tf.add(tf.matmul(layer[i-1],w[i]),b[i])
        layer[i]=tf.nn.sigmoid(layer[i])


                                 



############################################# Learning part #############################################



# Make placeholders for total beta vectors (make a long one to concatenate every beta vector) 
def betavec_build():
    if mode=='layer':
        Beta_vec=tf.placeholder(tf.float32,[np.shape(nodes)[0]-2])
    elif mode=='node':
        Beta_vec=tf.placeholder(tf.float32,[np.sum(nodes[1:-1])])

    return Beta_vec


# Make L1 loss term and L2 loss term for regularisation
def build_L1loss():
    if mode=='layer':
        L1_loss=[Beta_vec[i]*tf.reduce_sum(abs(w[i])) for i in np.arange(np.shape(nodes)[0]-2)]
    elif mode=='node':
        L1_loss=[tf.reduce_sum(tf.matmul(abs(w[i]),tf.cast(tf.diag(Beta_vec[nodes_index[i]:nodes_index[i+1]]),tf.float32))) for i in np.arange(np.shape(nodes)[0]-2)]

    return L1_loss

       

# Define cost term with cross entropy and L1 and L2 tetm 
if autoencoder:
    def build_cost():
        cost=tf.reduce_mean(tf.pow(X - layer[-1], 2)) + tf.reduce_sum(L1_loss) + L2_param*tf.reduce_sum(L2_loss)
        return cost    
    
else:
    def build_cost():
        cost=tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=layer[-1], labels=Y)) \
                                         + tf.reduce_sum(L1_loss) + L2_param*tf.reduce_sum(L2_loss)
        return cost    


# Define optimizer
def build_optimizer(Lr):
    if optimizer_algorithm=='G':
        optimizer=tf.train.GradientDescentOptimizer(Lr).minimize(cost) 
    elif optimizer_algorithm=='Ada':
        optimizer=tf.train.AdagradOptimizer(Lr).minimize(cost) 
    elif optimizer_algorithm=='Adam':
        optimizer=tf.train.AdamOptimizer(Lr).minimize(cost) 
    elif optimizer_algorithm=='M':
        optimizer=tf.train.MomentumOptimizer(Lr).minimize(cost) 
    elif optimizer_algorithm=='R':
        optimizer=tf.train.RMSPropOptimizer(Lr).minimize(cost) 

    return optimizer




# Weight sparsity control with Hoyer's sparsness (Layer wise)  
if mode=='layer':
    def Hoyers_sparsity_control(w_,b,max_b,tg):
        
        # Get value of weight
        W=sess.run(w_)
        [dim,_]=W.shape    
        Wvec=W.flatten()
        
        # Calculate L1 and L2 norm     
        L1=LA.norm(Wvec,1)
        L2=LA.norm(Wvec,2)
        
        # Calculate hoyer's sparsness
        h=(np.sqrt(dim)-(L1/L2))/(np.sqrt(dim)-1)
        
        # Update beta
        b-=lr_beta*np.sign(h-tg)
        
        # Trim value
        b=0.0 if b<0.0 else b
        b=max_b if b>max_b else b
        
                   
        return [h,b]
    

# Weight sparsity control with Hoyer's sparsness (Node wise)    
elif mode=='node':   
    def Hoyers_sparsity_control(w_,b_vec,max_b,tg):
    
        # Get value of weight
        W=sess.run(w_)
        [dim,nodes]=W.shape
        
        # Calculate L1 and L2 norm 
        L1=LA.norm(W,1,axis=0)
        L2=LA.norm(W,2,axis=0)
        
        h_vec = np.zeros((1,nodes))
        tg_vec = np.ones(nodes)*tg
        
        # Calculate hoyer's sparsness
        h_vec=(np.sqrt(dim)-(L1/L2))/(np.sqrt(dim)-1)
        
        # Update beta
        b_vec-=lr_beta*np.sign(h_vec-tg_vec)
        
        # Trim value
        b_vec[b_vec<0.0]=0.0
        b_vec[b_vec>max_b]=max_b
        
               
        return [h_vec,b_vec]
    

lr = lr_init

Beta_vec=betavec_build()

L1_loss=build_L1loss()
L2_loss = [tf.reduce_sum(tf.square(w[i])) for i in np.arange(np.shape(nodes)[0]-2)]   

cost=build_cost()


# Make learning rate as placeholder to update learning rate every iterarion 
Lr=tf.placeholder(tf.float32)
optimizer=build_optimizer(Lr)
  

if autoencoder:
    pred=tf.nn.sigmoid(layer[-1])
    correct_prediction = tf.equal(pred,X)   
else:
    pred=layer[-1]
    correct_prediction=tf.equal(tf.argmax(pred,1),tf.argmax(Y,1))  
    
# calculate mean accuracy depending on the frequency it predicts correctly
accuracy=tf.reduce_mean(tf.cast(correct_prediction,tf.float32))      








############################################# Condition check part #############################################

condition=False

print()

if np.shape(nodes)[0] <3:
    print("Error : Not enough hidden layer number.")
elif np.shape(train_input)[0] != np.shape(train_output)[0]:
    print("Error : The sizes of input train dataset and output train dataset don't match. ")  
elif np.shape(test_input)[0] != np.shape(test_output)[0]:
    print("Error : The sizes of input test dataset and output test dataset don't match. ")     
elif not ((mode=='layer') | (mode=='node')):
    print("Error : Select a valid mode. ") 
elif (np.any(np.array(tg_hsp)<0)) | (np.any(np.array(tg_hsp)>1)):  
    print("Error : Please set the target sparsities appropriately.")
elif autoencoder!=True & autoencoder!=False:
    print("Error : Please set the autoencoder mode appropriately.")
else:
    condition=True




################################################ Training & test part ################################################


if condition==True:
    
    # make initializer        
    init = tf.global_variables_initializer()              

    
    
    with tf.Session(config=tf.ConfigProto(allow_soft_placement=True, log_device_placement=True)) as sess:
        
        # run tensorflow variable initialization
        sess.run(init)
    
        # initialization    
        def initialization(mode):           
            if mode=='layer': 
                beta=np.zeros(np.shape(nodes)[0]-2)
                beta_vec = np.zeros(np.shape(nodes)[0]-2)
                hsp = np.zeros(np.shape(nodes)[0]-2)            
                plot_beta = np.zeros(np.shape(nodes)[0]-2)
                plot_hsp = np.zeros(np.shape(nodes)[0]-2)
                           
            elif mode=='node':                       
                beta = [np.zeros(nodes[i+1]) for i in np.arange(np.shape(nodes)[0]-2)]  
                beta_vec=np.zeros(np.sum(nodes[1:-1]))
                hsp = [np.zeros(nodes[i+1]) for i in np.arange(np.shape(nodes)[0]-2)]            
                plot_beta = [np.zeros(nodes[i+1]) for i in np.arange(np.shape(nodes)[0]-2)]
                plot_hsp = [np.zeros(nodes[i+1]) for i in np.arange(np.shape(nodes)[0]-2)]
                
            # make arrays to plot results
            plot_lr=np.zeros(1)
            plot_cost=np.zeros(1)
            
            return beta, beta_vec, hsp, plot_beta, plot_hsp, plot_lr, plot_cost
                
        beta, beta_vec, hsp, plot_beta, plot_hsp, plot_lr, plot_cost = initialization(mode)
        
        
        

        
           
        # Calculate how many mini-batch iterations
        total_batch=int(np.shape(train_output)[0]/batch_size) 
        
        
        # train and get cost
        cost_avg=0.0
        for epoch in np.arange(total_epoch):            
            cost_epoch=0.0
            
            # Begin Annealing
            if beginAnneal == 0:
                lr = lr * 1.0
            elif epoch+1 > beginAnneal:
                lr = max( min_lr, (-0.01*(epoch+1) + (1+0.0001*beginAnneal)) * lr )        
            
            
            # Train at each mini batch    
            for batch in np.arange(total_batch):
                batch_x = train_input[batch*batch_size:(batch+1)*batch_size]
                batch_y = train_output[batch*batch_size:(batch+1)*batch_size]
                
                # Get cost and optimize the model
                # auto encoder
                if autoencoder:
                    cost_batch,_=sess.run([cost,optimizer],feed_dict={Lr:lr, X:batch_x, Beta_vec:beta_vec })
                else:                   
                    cost_batch,_=sess.run([cost,optimizer],feed_dict={Lr:lr, X:batch_x, Y:batch_y, Beta_vec:beta_vec })
                    
                cost_epoch+=cost_batch/total_batch 
                    
        
                # make space to plot beta, sparsity level
                plot_lr=np.hstack([plot_lr,[lr]])
                plot_cost=np.hstack([plot_cost,[cost_batch]])
                
                # save footprint for plot
                if mode=='layer':
                    plot_hsp=[np.vstack([plot_hsp[i],[hsp[i]]]) for i in np.arange(np.shape(nodes)[0]-2)]
                    plot_beta=[np.vstack([plot_beta[i],[beta_vec[i]]]) for i in np.arange(np.shape(nodes)[0]-2)]
                    
                elif mode=='node':
                    plot_hsp=[np.vstack([plot_hsp[i],[np.transpose(hsp[i])]]) for i in np.arange(np.shape(nodes)[0]-2)]
                    plot_beta=[np.vstack([plot_beta[i],[np.transpose(beta[i])]]) for i in np.arange(np.shape(nodes)[0]-2)]

                
        
                # run weight sparsity control function
                for i in np.arange(np.shape(nodes)[0]-2):
                    [hsp[i],beta[i]]=Hoyers_sparsity_control(w[i], beta[i], max_beta[i], tg_hsp[i])   
                    
                if mode=='layer':               
                    beta_vec=beta
                        
                elif mode=='node':                              
                    beta_vec=[item for sublist in beta for item in sublist]
                    
                    
            # Print cost at each epoch        
            print("< Epoch", "{:02d}".format(epoch+1),"> Cost : ", "{:.4f}".format(cost_epoch))
    #        print("beta_(mean) :",beta_N)
    #        print("hsp_h1_vec(mean) : ","{:.3f}".format(hsp_h1_vec.mean()), "/ hsp_h2_vec(mean) :","{:.3f}".format(hsp_h2_vec.mean()), "/ hsp_h3_vec(mean) :","{:.3f}".format(hsp_h3_vec.mean()))
    #        print("")
        
        # Print final accuracy of test set
        if autoencoder:
            # Applying encode and decode over test set
            print("Accuracy :",sess.run(accuracy,feed_dict={X:test_input}))
                        
        else:
            print("Accuracy :",sess.run(accuracy,feed_dict={X:test_input, Y:test_output}))
        
       
        # Plot the change of learning rate
        plt.title("Learning rate plot",fontsize=16)
        plot_lr=plot_lr[1:]
        plt.ylim(0.0, lr_init*1.2)
        plt.plot(plot_lr)
        plt.show()
        
        # Plot the change of cost
        plt.title("Cost plot",fontsize=16)
        plot_cost=plot_cost[1:]
        plt.plot(plot_cost)
        plt.show()      
        
        
        # Plot the change of beta value
        print("")       
        for i in np.arange(np.shape(nodes)[0]-2):
            print("")
            print("                      < ",i+1,"th, layer >")
            plt.title("Beta plot",fontsize=16)
            plot_beta[i]=plot_beta[i][1:]
            plt.plot(plot_beta[i])
            plt.ylim(0.0, 0.15)
            plt.show()
        
        # Plot the change of Hoyer's sparsness
        print("")            
        for i in np.arange(np.shape(nodes)[0]-2):
            print("")
            print("                      < ",i+1,"th, layer >")
            plt.title("Hoyer's sparsness plot",fontsize=16)
            plot_hsp[i]=plot_hsp[i][1:]
            plt.plot(plot_hsp[i])
            plt.ylim(0.0, 1.0)
            plt.show()
        
        current_directory = os.getcwd()
        final_directory = os.path.join(current_directory, r'results')
        if not os.path.exists(final_directory):
            os.makedirs(final_directory)  
        scipy.io.savemat("results/result_learningrate.mat", mdict={'lr': plot_lr})
        scipy.io.savemat("results/result_cost.mat", mdict={'cost': plot_cost})
        scipy.io.savemat("results/result_beta.mat", mdict={'beta': plot_beta})
        scipy.io.savemat("results/result_hsp.mat", mdict={'hsp': plot_hsp})


else:
    # Don't run the sesstion but print 'failed' if any condition is unmet
    print("Failed!")    
     

