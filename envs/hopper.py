import numpy as np
import gym
import pybullet_envs

from pybullet_envs import gym_locomotion_envs

class HopperMBEnv(gym_locomotion_envs.HopperBulletEnv):

    def __init__(self, render=False):
        super().__init__(render)

    def reset(self):
        s = super().reset()
        self.num_joints = len(self.robot.ordered_joints)
        return s

    def get_alive_bonus(self, z, p):
        return 1.0 if z + self.robot.initial_z > 0.8 and abs(p) < 1.0 else -1.0

    def get_reward(self, state, action):
        z = state[0]
        p = state[7]
        vx = state[3] / 0.3

        j = state[8 : 8 + self.num_joints * 2]
        joint_speeds = j[1::2]
        joints_at_limit = np.count_nonzero(np.abs(j[0::2]) > 0.99)

        alive_bonus = self.get_alive_bonus(z, p)
        progress = vx
        electricity_cost = self.electricity_cost * float(np.abs(action * joint_speeds).mean())
        electricity_cost += self.stall_torque_cost * float(np.square(action).mean())
        joints_at_limit_cost = float(self.joints_at_limit_cost * joints_at_limit)
        feet_collision_cost = 0.0

        return alive_bonus + progress + electricity_cost + joints_at_limit_cost + feet_collision_cost

    def is_done(self, state):
        z = state[0]
        p = state[7]
        return self.get_alive_bonus(z, p) < 0

    def get_alive_bonuses(self, z, p):
        return np.where(np.all([z + self.robot.initial_z > 0.8, np.abs(p) < 1.0], axis=0), 1.0, -1.0)

    def get_rewards_dones(self, states, actions):
        # states (n, 12), actions (n, 3)
        z = states[:, 0] #(n,)
        p = states[:, 7] #(n,)
        vx = states[:, 3] / 0.3 #(n,)

        j = states[:, 8:8+self.num_joints*2] #(n, 6)
        joint_speeds = j[:, 1::2] #(n, 3)
        joints_at_limit = np.count_nonzero(np.abs(j[:, 0::2]) > 0.99, axis=1) #(n,)

        alive_bonus = self.get_alive_bonuses(z, p) #(n,)
        progress = vx #(n,)
        electricity_cost = self.electricity_cost * np.mean(np.abs(actions * joint_speeds), axis=1) #(n,)
        electricity_cost += self.stall_torque_cost * np.mean(np.square(actions), axis=1) #(n,)
        joints_at_limit_cost = self.joints_at_limit_cost * joints_at_limit #(n,)
        # feet_collision_cost = 0.0

        return alive_bonus + progress + electricity_cost + joints_at_limit_cost, alive_bonus < 0
    
