import gym
import numpy as np 
import sys
import time
import tensorflow as tf 
from tensorflow.keras.layers import Dense, Input
from tensorflow.keras.models import Model 
from tensorflow.keras.optimizers import Adam, RMSprop, SGD
from tensorflow.keras import regularizers
from tensorflow.keras import utils

class Agent:
    def __init__(self, input_dim, output_dim, hidden_layers=[32, 32], policy_lr=1e-3, v_lr=1e-3, v_update_steps=80):
        self.input_dim = input_dim
        self.output_dim = output_dim 

        self.v_update_steps = v_update_steps

        self._build_policy_model(input_dim, output_dim, hidden_layers, policy_lr)
        self._build_value_model(input_dim, hidden_layers, v_lr)

    def _build_policy_model(self, input_dim, output_dim, hidden_layers, lr):
        policy_input = Input(shape=(input_dim,))
        X = policy_input
        for size in hidden_layers:
            X = Dense(size, activation="relu", kernel_initializer="glorot_normal", kernel_regularizer=regularizers.l2(0.01))(X)
        mu = Dense(output_dim, activation="tanh", kernel_initializer="glorot_normal", kernel_regularizer=regularizers.l2(0.01))(X)
        sigma = Dense(output_dim, activation="softplus", kernel_initializer="glorot_normal", kernel_regularizer=regularizers.l2(0.01))(X)
        self.policy = Model(inputs=policy_input, outputs=[mu, sigma])
        # self.policy = Model(inputs=policy_input, outputs=mu)
        # self.log_stds = tf.Variable(-0.75 * np.ones((output_dim,)), dtype="float32", name="log_stds", trainable=True)
        self.policy_opt = Adam(lr)

    def _build_value_model(self, input_dim, hidden_layers, lr):
        v_input = Input(shape=(input_dim,))
        X = v_input
        for size in hidden_layers:
            X = Dense(size, activation="relu", kernel_initializer="glorot_normal", kernel_regularizer=regularizers.l2(0.01))(X)
        X = Dense(1, activation="linear", kernel_initializer="glorot_normal", kernel_regularizer=regularizers.l2(0.01))(X)
        self.v = Model(inputs=v_input, outputs=X)
        self.v_opt = Adam(lr)

    def _gaussian_log_likelihood(self, actions, means, stds, log_stds, eps=1e-8):
        pre_sum = -0.5 * (((actions-means)/(stds+eps))**2 + 2*log_stds + np.log(2*np.pi))
        return tf.reduce_sum(pre_sum, axis=1)
        # return -0.5 * (tf.reduce_sum(((actions - means) / (stds + eps)) ** 2 + 2 * log_stds, axis=1) + self.output_dim * np.log(2 * np.pi))

    i = 0

    def update(self, state, action, G):
        """Does one step of policy gradient update
        
        Args:
            states: np.array of sample states. dim = (n_samples, self.input_dim)
            action: np.array of sample actions. dim = (n_samples,)
            weights: np.array of sample weights e.g. rewards-to-go. dim = (n_samples,)
        """
        state = np.expand_dims(state, axis=0)
        action = np.expand_dims(action, axis=0)
        G = np.expand_dims(G, axis=0)

        # Update the policy
        def policy_loss():
            mean, std = self.policy(state)
            log_std = tf.math.log(std)
            log_prob = self._gaussian_log_likelihood(action, mean, std, log_std)
            adv = G - self.v(state)
            loss = -tf.reduce_mean(log_prob * adv)

            # if (Agent.i % 200 == 0):
            #     print("States:", states)
            #     print("Meanss:", means)
            #     print("Log Stds:", log_stds)
            #     print("Stds:", stds)
            #     print("Log Probs:", log_probs)
            #     print("Values:", values)
            #     print("Rewards:", rtg)
            #     print("Advs:", advs)
            #     print("Loss:", loss)

            # Agent.i += 1

            return loss

        self.policy_opt.minimize(policy_loss, lambda: self.policy.trainable_weights)
        # self.policy_opt.minimize(policy_loss, lambda: self.policy.trainable_weights + [self.log_stds])

        # Update the Value function
        def v_loss():
            value = self.v(state)
            return tf.reduce_mean((value - G) ** 2)

        for _ in range(self.v_update_steps):
            self.v_opt.minimize(v_loss, lambda: self.v.trainable_weights)

    def sample_action(self, s):
        """"""
        state = np.expand_dims(s, axis=0)
        # means = self.policy.predict(state)[0]
        # stds = tf.exp(self.log_stds)
        means, stds = self.policy.predict(state)
        noises = tf.random.normal((self.output_dim,))
        sample = means[0] + stds[0] * noises
        return tf.clip_by_value(sample, -1.0, 1.0).numpy()

    def get_value(self, s):
        state = np.expand_dims(s, axis=0)
        value = self.v.predict(state)[0]
        return value

    def save(self, path, extension="h5"):
        self.policy.save(f"{path}_pi.{extension}")
        self.v.save(f"{path}_v.{extension}")
        # np.save(f"{path}_log_stds", self.log_stds.numpy())

    def load(self, path, extension="h5"):
        del self.policy
        self.policy = tf.keras.models.load_model(f"{path}_pi.{extension}")
        del self.v 
        self.v = tf.keras.models.load_model(f"{path}_v.{extension}")
        # self.log_stds.assign(np.load(f"{path}_log_stds.npy"))

def train_one_epoch(agent, env, batch_size, discount=0.99, max_ep_len=1000):
    ep_returns = []
    ep_lens = []

    s = env.reset()

    ep_len = 0
    ep_return = 0

    for i in range(batch_size):
        a = agent.sample_action(s)
        new_s, r, done, _ = env.step(a)
        G = r
        if not done:
            G += discount * agent.get_value(new_s)
        agent.update(s, a, G)
        s = new_s

        ep_len += 1
        ep_return += r

        if done or ep_len == max_ep_len:
            ep_returns.append(ep_return)
            ep_lens.append(ep_len)
            ep_return = 0
            ep_len = 0
            s = env.reset()
        
    return ep_returns, ep_lens
            
def train(agent, env, epochs, batch_size, save_path, save_freq=100, init_epoch=0, discount=0.99, max_ep_len=1000):
    for i in range(init_epoch, epochs):
        returns, lens = train_one_epoch(agent, env, batch_size, discount=discount, max_ep_len=max_ep_len)
        print(f"epoch: {i}, \t return: {np.mean(returns)}, \t episode length: {np.mean(lens)}")
        if i % save_freq == 0: 
            agent.save(f"{save_path}_{i}")
    agent.save(f"{save_path}_{epochs - 1}")

def test_agent(agent, env, n_tests, delay=1):
    for test in range(n_tests):
        print(f"Test #{test}")
        s = env.reset()
        done = False
        total_reward = 0
        while True:
            time.sleep(delay)
            env.render()
            a = agent.sample_action(s)
            print(f"Chose action {a} for state {s}")
            s, reward, done, _ = env.step(a)
            total_reward += reward
            if done:
                print(f"Done. Total Reward = {total_reward}")
                time.sleep(2)
                break

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=str, default="models/lunarlander_model")
    parser.add_argument("--load_epoch", type=int, default=-1)
    parser.add_argument("--tests", type=int, default=0)
    parser.add_argument("--init_epoch", type=int, default=0)
    parser.add_argument("--save_freq", type=int, default=20)
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--bs", type=int, default=2000)
    parser.add_argument("--pi_lr", type=float, default=1e-3)
    parser.add_argument("--v_lr", type=float, default=1e-3)
    parser.add_argument("--v_update_steps", type=int, default=80)
    parser.add_argument("--test_only", action="store_true")
    parser.add_argument("--discount", type=float, default=0.99)
    parser.add_argument("--max_ep_len", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--hidden_layers", type=str, default="[64, 32]")
    args = parser.parse_args()

    np.random.seed(args.seed)
    tf.random.set_seed(args.seed)

    env = gym.make('LunarLanderContinuous-v2')

    hidden_layers = [int(x) for x in args.hidden_layers[1:-1].split(",")]
    agent = Agent(env.observation_space.shape[0], env.action_space.shape[0], hidden_layers=hidden_layers, 
                    policy_lr=args.pi_lr, v_lr=args.v_lr, v_update_steps=args.v_update_steps)

    if args.load_epoch >= 0:
        agent.load(f"{args.path}_{args.load_epoch}")
    
    if args.verbose:
        # agent.policy.summary()
        # agent.v.summary()
        # state = np.expand_dims(env.reset(), axis=0)
        # means = agent.policy.predict(state)[0]
        # stds = tf.exp(agent.log_stds)
        # print(state[0], means, agent.log_stds, stds)
        print(args)
        # print(tf.exp(agent.log_stds))
        # input()

    if args.epochs > 0 and not args.test_only:
        train(agent, env, args.epochs, args.bs, args.path, save_freq=args.save_freq, 
                init_epoch=args.init_epoch, discount=args.discount, max_ep_len=args.max_ep_len)

    if args.tests > 0:
        test_agent(agent, env, args.tests, 0.025)

    env.close()
