function [nn, L]  = nntrain(nn, train_x, train_y, opts, val_x, val_y)

% assert(X, A) == if(~X) error(A)
assert(isfloat(train_x), 'train_x must be a float');                           
assert(nargin == 4 || nargin == 6,'number ofinput arguments must be 4 or 6')   

loss.train.e               = [];    % training loss function
loss.train.e_frac          = [];    % training error rate
loss.val.e                 = [];    % validation loss function
loss.val.e_frac            = [];    % validation error rate
opts.validation = 0;

if nargin == 6
    opts.validation = 1;
end

% plot figure handle
fhandle = [];
if isfield(opts,'plot') && opts.plot == 1
    fhandle = figure();
end

m = size(train_x, 1);   % m = # of training samples

batchsize = opts.batchsize; % batch size
numepochs = opts.numepochs; % # of epochs
numbatches = m / batchsize; % # of batches

% weight sparsity parameters
epsilon = 0.001;         
betarate = 0.01;         

assert(rem(numbatches, 1) == 0, 'numbatches must be a integer');

L = zeros(numepochs*numbatches,1);
n = 1;                             

for i = 1 : numepochs
    tic;       
    kk = randperm(m);   	
    for l = 1 : numbatches
        batch_x = train_x(kk((l - 1) * batchsize + 1 : l * batchsize), :);  % train_x to batch_x
        batch_y = train_y(kk((l - 1) * batchsize + 1 : l * batchsize), :);	% train_y to batch_y
        
        if(nn.inputZeroMaskedFraction ~= 0)
            batch_x = batch_x.*(rand(size(batch_x))>nn.inputZeroMaskedFraction);
        end
        
        nn = nnff(nn, batch_x, batch_y);    % Feed-forward
        nn = nnbp(nn);                      % Back-propagation
        nn = nnapplygrads(nn);              % Gradient-descent update
     
       % weight sparsity 
       for j = 1 : (nn.n-1)               
            if length(nn.weightPenaltyL1) == 1
                pl1 = nn.weightPenaltyL1(1);
            else
                pl1 = nn.weightPenaltyL1(j);
            end                        
            if nn.nzr(j) ~= 0                 
                mNZR = length( find( abs(nn.W{j}(:)) > epsilon ) ) / numel(nn.W{j});
                pl1 = pl1 + betarate*sign(mNZR - nn.nzr(j)); % sign function was added to facilitate the weight saprsity control.
                if pl1 > nn.max_beta(j) % maximum beta values are largely dependent on data & models.
                        pl1 = nn.max_beta(j);
                elseif pl1 < 0
                    pl1 = 0;
                end
                nn.weightPenaltyL1(j) = pl1;
        	end    
        end
          L(n) =  gather(nn.L);    
%         L(n) = nn.L;        % loss function with all batches     
        n = n + 1;          % all batches for all samples
    end    
    t = toc;
    
    if opts.validation == 1
        loss = nneval(nn, loss, train_x, train_y, val_x, val_y);
        str_perf = sprintf('; Full-batch train mse = %f, val mse = %f', loss.train.e(end), loss.val.e(end));
    else
        loss = nneval(nn, loss, train_x, train_y);
        str_perf = sprintf('; Full-batch train err = %f', loss.train.e(end));
    end
    if ishandle(fhandle)
        nnupdatefigures(nn, fhandle, loss, opts, i);
    end
    
    nn.loss = loss;
    for j = 1 : (nn.n-1) % to check current weight sparsity level
        mNZR = length( find( abs(nn.W{j}(:)) > epsilon ) ) / numel(nn.W{j});
        nn.mNZR{j} = [nn.mNZR{j} mNZR];
    end
    nn.beta =[nn.beta; nn.weightPenaltyL1(1)];
	nn.lr = [nn.lr nn.learningRate];
    nn.rho = [nn.rho mean(nn.p{2}(:))];
	nn.er = [nn.er loss.train.e(end)];
    
	disp(['epoch ' num2str(i) '/' num2str(opts.numepochs) '. Took ' num2str(t) ' seconds' '. Mini-batch mean squared error on training set is ' num2str(mean(L((n-numbatches):(n-1)))) str_perf]);
  
    % Annealing
    if nn.beginAnneal == 0
        nn.learningRate = nn.learningRate * nn.scaling_learningRate;
    elseif i > nn.beginAnneal
        decayrate = -0.0001;    
        nn.learningRate = max( 1e-6, ( decayrate*i+(1-decayrate*nn.beginAnneal) ) * nn.learningRate ); 
    end
  
end

end

