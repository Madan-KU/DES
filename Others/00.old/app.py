import os
import csv
import time
import yaml
import simpy
import random
import logging
import warnings
import seaborn as sns

import pandas as pd
import streamlit as st
#from tqdm import tqdm
import matplotlib.pyplot as plt
from functools import partial, wraps

from src.simulation import NCCU_Model, Simulate
from modules.data_loader import read_data
from modules.read_config import read_config
from modules.logger_configurator import configure_logger

# Function to load YAML file
def load_yaml(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

# Function to save YAML file
def save_yaml(file_path, data):
    with open(file_path, 'w') as file:
        yaml.dump(data, file, default_flow_style=False)


configure_logger()
config = read_config('parameters.yaml')

logger = logging.getLogger(__name__)


# Initialize session state variables
if 'running' not in st.session_state:
    st.session_state['running'] = False
if 'paused' not in st.session_state:
    st.session_state['paused'] = False


def plot_resource_utilization(data):
    plt.figure(figsize=(10, 6))
    for resource in data['Resource'].unique():
        resource_data = data[data['Resource'] == resource]
        plt.plot(resource_data['Day'], resource_data['Daily_Use'], label=resource)
    plt.xlabel('Day')
    plt.ylabel('Average Daily Use')
    plt.title('Resource Utilization Over Time')
    plt.legend()
    st.pyplot(plt)

def plot_queue_length(data):
    plt.figure(figsize=(10, 6))
    for resource in data['Resource'].unique():
        resource_data = data[data['Resource'] == resource]
        plt.plot(resource_data['Day'], resource_data['Queue_Length'], label=resource)
    plt.xlabel('Day')
    plt.ylabel('Queue Length')
    plt.title('Queue Length Over Time')
    plt.legend()
    st.pyplot(plt)



# def plot_histograms(stay_duration_data):
#     plt.figure(figsize=(10, 6))
#     for unit in stay_duration_data['Unit_Type'].unique():
#         unit_data = stay_duration_data[stay_duration_data['Unit_Type'] == unit]['Stay_Duration']
#         sns.histplot(unit_data, kde=True, label=unit)
#     plt.xlabel('Stay Duration (days)')
#     plt.ylabel('Frequency')
#     plt.title('Histogram of Stay Durations')
#     plt.legend()
#     st.pyplot(plt)





        
# try:
    # Here we add callbacks to a resource that get called just before or after a get / request or a put / release event:

st.set_page_config(page_title="Simulation Demo", page_icon="📈")





st.title("Neonatal Critical Care Bed Use Modelling")

st.write("")

st.markdown("""This is a stochastic discrete event simulation of each of the 3 levels of care provided in a neonatal critical care unit.""")
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
    
    # Add an 'Admin' button in the sidebar
    if st.sidebar.button("Modify Parameters"):
        st.sidebar.markdown("### Parameters/Configuration")
        yaml_file_path = 'parameters.yaml'

        # Load and display the current YAML data
        if os.path.exists(yaml_file_path):
            data = load_yaml(yaml_file_path)
            updated_data = {}
            for key, value in data.items():
                updated_data[key] = st.sidebar.text_input(f"{key}", value)

            if st.sidebar.button('Save Changes'):
                save_yaml(yaml_file_path, updated_data)
                st.sidebar.success("Configuration updated successfully!")
        else:
            st.sidebar.error("YAML file not found.")

    # This part should be aligned with the 'if' above, not nested inside it
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
    stop_button = st.form_submit_button(label='Stop Simulation')

if submit_button:
    start_time = time.time()
    progress_bar=st.progress(0)
    with st.spinner('Running simulations...'):

        Simulate(sim_params_instance)
        total_runs = sim_params_instance.number_of_runs
    
        

        all_runs_data = pd.DataFrame()  # Initialize all_runs_data
        for run in range(total_runs):
            # logger.info("#######>main run loop in app.py") ########### Main Loop Runs Properly**

            # Update the progress bar
            progress_percentage = int((run / total_runs) * 100)
            progress_bar.progress(progress_percentage)
            
            try:
                NCCU_model_instance = NCCU_Model(sim_params_instance)
                NCCU_model_instance.run()
                all_runs_data = pd.concat([all_runs_data, NCCU_model_instance.resource_monitor_df])
            except Exception as e:
                logger.error(f"Error in simulation run {run + 1}: {e}")

            progress_bar.progress(100)

        end_time = time.time()  # End time
        total_duration = end_time - start_time  # Total duration

        st.info(f"Total simulation time: {total_duration:.2f} seconds")

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

        st.header("Simulation Results Visualization")

        st.subheader("Resource Utilization Over Time")
        plot_resource_utilization(all_runs_data)

        st.subheader("Queue Length Over Time")
        plot_queue_length(all_runs_data)

        # # Assuming you have stay duration data
        # st.subheader("Histograms of Stay Duration")
        # plot_histograms(stay_duration_data)


        ax.legend()

        st.pyplot(fig)
    st.success('Done!')

if stop_button:
    st.session_state['running'] = False


# except Exception as global_exception:
    # logger.error(f"Global exception: {global_exception}")