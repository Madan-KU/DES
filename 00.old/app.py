import os
import csv
import yaml
import simpy
import random
import logging
import warnings

import pandas as pd
import streamlit as st
#from tqdm import tqdm
import matplotlib.pyplot as plt
from functools import partial, wraps

from src.simulation import NCCU_Model
from modules.data_loader import read_data
from modules.read_config import read_config
from modules.logger_configurator import configure_logger

configure_logger()
config = read_config('parameters.yaml')

logger = logging.getLogger(__name__)


        
# try:
    # Here we add callbacks to a resource that get called just before or after a get / request or a put / release event:

st.set_page_config(page_title="Simulation Demo", page_icon="📈")

st.title("Neonatal Critical Care Bed Use Modelling")

st.write("")

st.markdown(
    """
This is a stochastic discreet event simulation of each of the 3 levels of care provided in a neonatal critical care unit.
"""
)
st.write("")



class simulation_parameters:
    def __init__(self, config):
        self.config = config

    
        self.chance_need_NICU = config['simulation_parameters']['chance_need_NICU']
        self.chance_need_HDCU = config['simulation_parameters']['chance_need_HDCU']
        self.chance_need_SCBU = config['simulation_parameters']['chance_need_SCBU']

        self.chance_need_HDCU_after_NICU = config['simulation_parameters']['chance_need_HDCU_after_NICU']
        self.chance_need_SCBU_after_NICU = config['simulation_parameters']['chance_need_SCBU_after_NICU']

        self.chance_need_NICU_after_HDCU = config['simulation_parameters']['chance_need_NICU_after_HDCU']
        self.chance_need_SCBU_after_HDCU = config['simulation_parameters']['chance_need_SCBU_after_HDCU']

        self.chance_need_NICU_after_SCBU = config['simulation_parameters']['chance_need_NICU_after_SCBU']
        self.chance_need_HDCU_after_SCBU = config['simulation_parameters']['chance_need_HDCU_after_SCBU']

        self.number_of_runs = None  # Updated later in the script
        self.sim_duration = None
        self.warm_up_duration = None
        self.number_of_NICU_cots = None
        self.number_of_HDCU_cots = None
        self.number_of_SCBU_cots = None
        self.annual_birth_rate = None
        self.day_births_inter = None
        self.daily_births = None
        self.avg_NICU_stay = None
        self.avg_HDCU_stay = None
        self.avg_SCBU_stay = None

sim_params_instance = simulation_parameters(config)

with st.sidebar:
    st.image('./NECS_Cropped_Dots.png', caption=None, width=300, use_column_width=None, clamp=False, channels="RGB", output_format="auto")
    tab1, tab2, tab3 = st.tabs(["Simulation Run Settings", "Unit Parameters", "Dev"])
    with tab1:
        # simulation run metrics
        st.markdown("""Set your preferred settings for the simulation run times.""")
        # number of cycles before starting data collection
        sim_params_instance.warm_up_duration = st.number_input("""Simulation warm up - recommended in this scenario we don't open 
                                            doors with an empty unit a large number of days will help us 
                                            account for existing patients of varying 
                                            lengths of stay duration""", 0, 1000, 100, step=1) #None, None, 100, step=1
        sim_params_instance.sim_duration = st.number_input("Simulation duration - days", 0, 1000, 300, step=1)  # None, None, 300, step=1
        sim_params_instance.number_of_runs = st.number_input("""Number of times to run the simulation. We run the simulation many 
                                            times and then average out the results to account for busy periods 
                                            and slow periods that can occur in stochastic modelling)""", 1, 100, 50, step=1) #  1, None, 50, step=1

    with tab2:
        st.markdown("""Here we can set our unit parameters""")
        sim_params_instance.number_of_NICU_cots = st.slider("Number of NICU cots", 1, 10, 3)
        sim_params_instance.number_of_HDCU_cots = st.slider("Number of LCU cots", 1, 10, 3)
        sim_params_instance.number_of_SCBU_cots = st.slider("Number of SCBU cots", 1, 20, 12)
        sim_params_instance.annual_birth_rate = st.slider("Annual Birth Rate", 1, 6000, 3000)
        sim_params_instance.day_births_inter = round(sim_params_instance.annual_birth_rate / 365, 2)
        daily_births = f"This is the equivalent of an average {sim_params_instance.day_births_inter} per day"
        st.sidebar.markdown(daily_births)

        st.markdown("""These are the average lengths of time spent in each setting, 
                        it is not advised to alter these as they are derived from badgernet data, 
                        but they could be altered if you wanted to look at certain 'what if' scenarios""")
        sim_params_instance.avg_NICU_stay = st.number_input("Average length of stay in a NICU cot", 12.67, None, 12.67)
        sim_params_instance.avg_HDCU_stay = st.number_input("Average length of stay in a LCU cot", 12.69, None, 12.69)
        sim_params_instance.avg_SCBU_stay = st.number_input("Average length of stay in a SCBU cot", 8.75, None, 8.75)

# For the number of runs specified in the g class, create an instance of the
# NCCU_Model class, and call its run method
with st.form(key='my_form'):
    submit_button = st.form_submit_button(label='Run simulations')



if submit_button:
    print(sim_params_instance.sim_duration)
    with st.spinner('Running simulations...'):
        all_runs_data = pd.DataFrame()  # Initialize all_runs_data
        for run in range(sim_params_instance.number_of_runs):
            try:
                NCCU_model_instance = NCCU_Model(sim_params_instance)
                NCCU_model_instance.run(sim_params_instance)
                all_runs_data = pd.concat([all_runs_data, NCCU_model_instance.resource_monitor_df])
            except Exception as e:
                logger.error(f"Error in simulation run {run + 1}: {e}")

        data = all_runs_data

        data_avg = data.groupby(['Day', 'Resource'])['Daily_Use'].mean().reset_index()

        resources = data_avg['Resource'].unique()

        fig, ax = plt.subplots()

        for resource in resources:
            resource_data = data_avg[data_avg['Resource'] == resource]
            ax.plot(resource_data['Day'], resource_data['Daily_Use'], label=resource)

        ax.set_xlabel('Day')
        ax.set_ylabel('Average Daily Use')
        ax.set_title('Average Daily Use of Resources Over Time')

        ax.legend()

        st.pyplot(fig)
    st.success('Done!')


# except Exception as global_exception:
#     logger.error(f"Global exception: {global_exception}")