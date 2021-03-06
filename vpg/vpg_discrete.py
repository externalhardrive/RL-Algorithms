import gym
import numpy as np 
import sys
import time
import tensorflow as tf 
from tensorflow.keras.layers import Dense, Input
from tensorflow.keras.models import Model 
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import utils

class DiscreteAgent:
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
            X = Dense(size, activation="tanh", kernel_initializer="glorot_normal")(X)
        X = Dense(output_dim, activation="softmax", kernel_initializer="glorot_normal")(X)
        self.policy = Model(inputs=policy_input, outputs=X)
        self.policy_opt = Adam(lr)

    def _build_value_model(self, input_dim, hidden_layers, lr):
        v_input = Input(shape=(input_dim,))
        X = v_input
        for size in hidden_layers:
            X = Dense(size, activation="tanh", kernel_initializer="glorot_normal")(X)
        X = Dense(1, activation=None, kernel_initializer="glorot_normal")(X)
        self.v = Model(inputs=v_input, outputs=X)
        self.v_opt = Adam(lr)

    def _gaussian_log_likelihood(self, actions, means, stds, log_stds, eps=1e-8):
        return -0.5 * (tf.reduce_sum(((actions - means) / (stds + eps)) ** 2 + 2 * log_stds + np.log(2 * np.pi), axis=1))

    def update(self, states, actions, rewards_to_go):
        """Does one step of policy gradient update
        
        Args:
            states: np.array of sample states. dim = (n_samples, self.input_dim)
            action: np.array of sample actions. dim = (n_samples,)
            weights: np.array of sample weights e.g. rewards-to-go. dim = (n_samples,)
        """
        # Update the policy
        def policy_loss():
            action_prob = self.policy(states)
            action_mask = utils.to_categorical(actions, num_classes=self.output_dim)
            probs = tf.reduce_sum(action_prob * action_mask, axis=1)
            log_probs = tf.math.log(probs)
            advs = rewards_to_go - self.v(states)
            return -tf.reduce_mean(log_probs * advs)

        self.policy_opt.minimize(policy_loss, lambda: self.policy.trainable_weights)

        # Update the Value function
        def v_loss():
            values = self.v(states)
            return tf.reduce_mean(tf.math.squared_difference(values, rewards_to_go))

        for _ in range(self.v_update_steps):
            self.v_opt.minimize(v_loss, lambda: self.v.trainable_weights)

    def sample_action(self, s):
        state = np.expand_dims(s, axis=0)
        action_prob = self.policy.predict(state)[0]
        return np.random.choice(range(self.output_dim), p=action_prob)

    def get_value(self, s):
        state = np.expand_dims(s, axis=0)
        value = self.v.predict(state)[0]
        return value

    def save(self, path, extension="h5"):
        self.policy.save(f"{path}_pi.{extension}")
        self.v.save(f"{path}_v.{extension}")

    def load(self, path, extension="h5"):
        del self.policy
        self.policy = tf.keras.models.load_model(f"{path}_pi.{extension}")
        del self.v 
        self.v = tf.keras.models.load_model(f"{path}_v.{extension}")
