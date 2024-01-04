import os
import csv
import time
import yaml
import simpy
import random
import logging
import warnings
import seaborn as sns

import cProfile
import pstats
import io

import pandas as pd
import streamlit as st
#from tqdm import tqdm
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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

global resource_monitor_data_path
resource_monitor_data_path = config['data']['resource_data']


# Initialize session state variables
if 'running' not in st.session_state:
    st.session_state['running'] = False
if 'paused' not in st.session_state:
    st.session_state['paused'] = False



def plot_resource_utilization(data):
    plt.figure(figsize=(10, 6), dpi=300)
    sns.set(style="whitegrid")

    # Plot for each resource
    sns.lineplot(x='Day', y='Daily_Use', hue='Resource', data=data, legend='full')

    # Calculate and plot the mean line grouped by Day
    mean_data = data.groupby('Day')['Daily_Use'].mean().reset_index()
    sns.lineplot(x='Day', y='Daily_Use', data=mean_data, color='black', label='Mean Daily Use', linewidth=2)

    plt.xlabel('Day')
    plt.ylabel('Average Daily Use')
    plt.title('Resource Utilization Over Time')
    plt.legend()
    st.pyplot(plt)


def plot_queue_length(data):
    plt.figure(figsize=(10, 6), dpi=300)
    sns.set(style="whitegrid")

    # Plot for each resource
    sns.lineplot(x='Day', y='Queue_Length', hue='Resource', data=data, legend='full')

    # Calculate and plot the mean line grouped by Day
    mean_data = data.groupby('Day')['Queue_Length'].mean().reset_index()
    sns.lineplot(x='Day', y='Queue_Length', data=mean_data, color='black', label='Mean Queue Length', linewidth=2)

    plt.xlabel('Day')
    plt.ylabel('Queue Length')
    plt.title('Queue Length Over Time')
    plt.legend()
    st.pyplot(plt)
        
def plot_available_capacity(data):

    available_capacity_data = data[['Day', 'Resource', 'Available_Capacity']]
    plt.figure(figsize=(10, 6))

    # Plot each unit with alpha=0.2
    for unit in available_capacity_data['Resource'].unique():
        subset = available_capacity_data[available_capacity_data['Resource'] == unit]
        plt.plot(subset['Day'], subset['Available_Capacity'], label=unit, alpha=0.2)

    # Calculate and plot mean lines with bold lines
    mean_capacity_data = available_capacity_data.groupby(['Day', 'Resource'])['Available_Capacity'].mean().reset_index()
    for unit in mean_capacity_data['Resource'].unique():
        mean_subset = mean_capacity_data[mean_capacity_data['Resource'] == unit]
        plt.plot(mean_subset['Day'], mean_subset['Available_Capacity'], label=f"{unit} Mean", linewidth=2)

    plt.xlabel('Day')
    plt.ylabel('Available Capacity')
    plt.title('Available Capacity for Neonatal Care Units Over Time (with Mean)')
    plt.legend()
    plt.grid(True)
    st.pyplot(plt)
    
def plot_admission_discharge_trends(data):
    grouped_data = data.groupby(['Day', 'Resource'])['Daily_Use'].sum().unstack()
    admissions = grouped_data.diff().clip(lower=0)  # Increase in use as admissions
    discharges = -grouped_data.diff().clip(upper=0)  # Decrease in use as discharges

    plt.figure(figsize=(12, 6))

    # Stacking admissions
    plt.stackplot(grouped_data.index, 
                  [admissions[unit] for unit in admissions.columns], 
                  labels=[f'{unit} Admissions' for unit in admissions.columns],
                  alpha=0.6)

    # Stacking discharges
    plt.stackplot(grouped_data.index, 
                  [discharges[unit] for unit in discharges.columns], 
                  labels=[f'{unit} Discharges' for unit in discharges.columns],
                  alpha=0.6)

    plt.title('Inferred Admissions and Discharges Over Time (Stacked Area Plot)')
    plt.xlabel('Day')
    plt.ylabel('Count')
    plt.legend(loc='upper left')
    plt.grid(True)
    st.pyplot(plt)

def plot_daywise_resource_utilization(data):
    data['Utilization_Rate'] = data['Daily_Use'] / data['Total_Capacity']
    
    plt.figure(figsize=(12, 6))
    sns.set(style="whitegrid")  # Cleaner style

    # Apply a 7-day moving average to smooth the data
    data['Utilization_MA'] = data.groupby('Resource')['Utilization_Rate'].transform(lambda x: x.rolling(window=7, min_periods=1).mean())

    sns.lineplot(x='Day', y='Utilization_MA', hue='Resource', data=data, marker="o")

    plt.title('Day-wise Resource Utilization (7-day Moving Average)')
    plt.xlabel('Day')
    plt.ylabel('Utilization Rate')
    plt.legend(title='Neonatal Unit', loc='upper left')
    plt.tight_layout()

    st.pyplot(plt)
st.set_page_config(page_title="Simulation Demo", page_icon="📈")


####################
def calculate_bed_occupancy_rate(data, unit_type):
    total_capacity = sim_params_instance['number_of_' + unit_type + '_cots']
    avg_daily_use = data[data['Resource'] == unit_type]['Daily_Use'].mean()
    return (avg_daily_use / total_capacity) * 100

def calculate_average_length_of_stay(data, unit_type):
    total_stays = data[data['Resource'] == unit_type]['Daily_Use'].sum()
    total_admissions = data[data['Resource'] == unit_type]['Admissions'].sum()
    return total_stays / total_admissions if total_admissions != 0 else 0

def calculate_readmission_rate(data, unit_type):
    readmissions = data[(data['Resource'] == unit_type) & (data['Readmission'] == True)].shape[0]
    total_discharges = data[data['Resource'] == unit_type]['Discharges'].sum()
    return (readmissions / total_discharges) * 100 if total_discharges != 0 else 0

####################
markdown_content = """
# Welcome to the Neonatal Critical Care Bed Use Modelling Application

## Overview
Delve into the intricate workings of a neonatal critical care unit with our advanced simulation tool. This application is meticulously crafted to model the utilization of critical care beds in neonatal units, using real-world data and probabilities. It's an essential tool for healthcare administrators, planners, and researchers aiming to optimize neonatal care efficiency and effectiveness.

## Key Features
1. **Realistic Simulation**: Experience the dynamics of neonatal care with our stochastic discrete event simulation, reflecting actual patient flow and bed utilization.
2. **Customizable Parameters**: Tailor your simulation with parameters like the chances of requiring different types of neonatal care (NICU, HDCU, SCBU) and the probabilities of needing subsequent care levels post-discharge.
3. **Data-Driven Insights**: Analyze detailed metrics through integrated visualizations, understanding resource utilization and identifying potential improvements in care delivery.
4. **User-Friendly Experience**: Enjoy a streamlined interface designed for easy navigation and interaction, making complex simulations accessible to all user levels.

## Getting Started
To begin exploring the potential of your neonatal care unit:
1. **Set Simulation Parameters**: Start by configuring the simulation to mirror your specific scenario. Adjust parameters like the probability of requiring different levels of neonatal care, based on real data.
2. **Run the Simulation**: Launch the simulation with your set parameters. Monitor the process in real-time and witness the unfolding of care dynamics in a virtual neonatal unit.
3. **Analyze and Interpret**: Post-simulation, explore the generated data to gain insights into bed utilization, patient flow, and care efficiency.

## Modify Parameters - Personalize Your Simulation
Under the "Modify Parameters" option, you have the flexibility to alter key variables:
- **Initial Care Needs**: Set probabilities for initial care requirements in NICU, HDCU, and SCBU.
- **Subsequent Care Probabilities**: Adjust the chances of needing different care levels after initial discharge (e.g., HDCU after NICU).
- **Predefined Defaults**: For ease of use, the application comes with predefined values based on historical data, which you can modify as needed.

These parameters are crucial for tailoring the simulation to specific research questions or operational scenarios. They allow for a diverse range of simulations, from typical operational days to stress-testing the system under extreme conditions.


## Terms and Conditions
[Place Holder]
"""

####################

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



def main_app():

    with st.sidebar:

        st.title("Neonatal Critical Care Bed Use Modelling")

        st.write("")

        st.markdown("""This is a stochastic discrete event simulation of each of the 3 levels of care provided in a neonatal critical care unit.""")

        st.write("")


        
        
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

        tab1, tab2 = st.tabs(["Simulation Run Settings", "Unit Parameters"])
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

    st.image('./NECS_Cropped_Dots.png', caption=None, width=300, use_column_width=None, clamp=False, channels="RGB", output_format="auto")
    
    with st.form(key='my_form'):
        submit_button = st.form_submit_button(label='Run simulations')
        stop_button = st.form_submit_button(label='Stop Simulation')

    if submit_button:
        start_time = time.time()
        progress_bar=st.progress(0)
        with st.spinner('Running simulations...'):

            # pr = cProfile.Profile()
            # pr.enable()

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

            # pr.disable()
            # s = io.StringIO()
            # sortby = 'cumulative'
            # ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
            # ps.print_stats()
            # print(s.getvalue())  

            # with open("cprofile.txt", "w") as file:
            #     file.write(s.getvalue())

            end_time = time.time()  # End time
            total_duration = end_time - start_time  # Total duration

            st.info(f"Total simulation time: {total_duration:.2f} seconds")

            data = all_runs_data
            data['Utilization_Rate'] = data['Daily_Use'] / data['Total_Capacity']

            # data_avg = data.groupby(['Day', 'Resource'])['Daily_Use'].mean().reset_index()

            # resources = data_avg['Resource'].unique()

            # fig, ax = plt.subplots()

            # for resource in resources:
            #     resource_data = data_avg[data_avg['Resource'] == resource]
            #     ax.plot(resource_data['Day'], resource_data['Daily_Use'], label=resource)

            # ax.set_xlabel('Day')
            # ax.set_ylabel('Average Daily Use')
            # ax.set_title('Average Daily Use of Resources Over Time')

            st.header("Simulation Results Visualization")

            st.subheader("Resource Utilization Over Time")
            plot_resource_utilization(all_runs_data)

            st.subheader("Queue Length Over Time")
            plot_queue_length(all_runs_data)

            st.subheader("Available Capacity Over Time")
            plot_available_capacity(all_runs_data)

            st.subheader("Inferred Admission and Discharge Trends")
            plot_admission_discharge_trends(data)

            st.subheader("Day-wise Resource Utilization")
            plot_daywise_resource_utilization(data)

            st.subheader(" All Runs df head")
            st.dataframe(all_runs_data.head(10))

            # ax.legend()

            # st.pyplot(fig)
        st.success('Done!')

        data.to_csv(resource_monitor_data_path)

    if stop_button:
        st.session_state['running'] = False

    # except Exception as global_exception:
    #     logger.error(f"Global exception: {global_exception}")

def display_agreement():
    st.title("Neonatal Critical Care Simulation")
    # st.markdown("### Please read the following agreement before proceeding:")
    st.markdown(markdown_content, unsafe_allow_html=True)

    agree = st.button("I Agree")
    disagree = st.button("I Disagree")

    if agree:
        st.session_state['agreed'] = True
        st.rerun()
    elif disagree:
        st.warning("You have disagreed with the terms. Exiting the application.")
        st.stop()

if 'agreed' not in st.session_state:
    st.session_state['agreed'] = False

if st.session_state['agreed']:
    main_app()
else:
    display_agreement()