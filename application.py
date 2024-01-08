import os
import io
import csv
import json
import time
import yaml
import simpy
import pandas as pd
import random
import logging
import warnings
import seaborn as sns

import cProfile
import pstats
import io
import re

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

# ==================================================
# ===================== Plots ======================
# ==================================================

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
    plt.legend( loc='upper left') #title='Neonatal Unit',
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

# ==================================================
# ============== Submit feedback page ==============
# ==================================================

def submit_feedback_page():
    # Helper function for email validation
    def validate_email(email):
        email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.fullmatch(email_regex, email)

    # Helper function to save feedback to a JSON file
    def save_feedback(feedback_file, feedback_data):
        try:
            # Attempt to read existing data
            try:
                with open(feedback_file, 'r') as file:
                    data = json.load(file)
            except FileNotFoundError:
                data = []

            # Append new feedback and save
            data.append(feedback_data)
            with open(feedback_file, 'w') as file:
                json.dump(data, file, indent=4)

        except Exception as e:
            raise Exception(f"Error saving feedback: {e}")

    # Streamlit UI elements for feedback form
    st.header("Submit your Feedback")
    feedback_type = st.selectbox("Type of Feedback", ["Issue", "Suggestion", "General Comment"], key='feedback_type')
    comment = st.text_area("Your Feedback", help="Please share your thoughts or issues.", key='feedback_comment')
    email = st.text_input("Email (Optional)", help="Enter your email if you wish to be contacted.", key='feedback_email')
    submit_feedback = st.button("Submit Feedback", key='submit_feedback')

    if submit_feedback:
        # Validate email if provided
        if email and not validate_email(email):
            st.error("Please enter a valid email address.")
            return

        feedback_data = {
            "type": feedback_type,
            "comment": comment,
            "email": email
        }

        # Attempt to save feedback
        try:
            save_feedback('feedback.json', feedback_data)
            st.success("Thank you for your feedback!")
        except Exception as e:
            st.error(str(e))

# ==================================================
# ================ Markdown Content ================
# ==================================================
            
markdown_content = """
# Welcome to the Neonatal Critical Care Bed Use Modelling Application

## Overview
Delve into the intricate workings of a neonatal critical care unit with our advanced simulation tool. This application is meticulously crafted to model the utilization of critical care beds in neonatal units, using real-world data and probabilities. It's an essential tool for healthcare administrators, planners, and researchers aiming to optimize neonatal care efficiency and effectiveness.

## Key Features
1. **Realistic Simulation**: Experience the dynamics of neonatal care with our stochastic discrete event simulation, reflecting actual patient flow and bed utilization.
2. **Customizable Parameters**: Tailor your simulation with parameters like the chances of requiring different types of neonatal care (NICU, HDCU, SCBU) and the probabilities of needing subsequent care levels post-discharge.
3. **Data-Driven Insights**: Analyze detailed metrics through integrated visualizations, understanding resource utilization and identifying potential improvements in care delivery.

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

# ==================================================
# =============== Modify Parameters ================
# ==================================================

def modify_parameters_page():
    def authenticate_user(username, password):
        # Placeholder for authentication logic
        # In production, use secure password handling
        return username == "Admin" and password == "admin"

    def handle_yaml(file_path, data=None, operation='load'):
        try:
            if operation == 'load':
                with open(file_path, 'r') as file:
                    return yaml.safe_load(file)
            elif operation == 'save' and data is not None:
                with open(file_path, 'w') as file:
                    yaml.dump(data, file, default_flow_style=False)
                    return True
        except Exception as e:
            st.error(f"Error handling YAML file: {e}")
            return None

    st.markdown("### Admin Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type='password')

    if st.button('Verify'):
        if authenticate_user(username, password):
            st.markdown("### Parameters/Configuration")
            yaml_file_path = 'parameters.yaml'

            if os.path.exists(yaml_file_path):
                data = handle_yaml(yaml_file_path)
                if data is not None:
                    updated_data = {key: st.text_input(f"{key}", value) for key, value in data.items()}

                    if st.button('Save Changes'):
                        if handle_yaml(yaml_file_path, updated_data, 'save'):
                            st.success("Configuration updated successfully!")
            else:
                st.error("YAML file not found.")
        else:
            st.error("Invalid username or password.")

def main_app():

    with st.sidebar:
        st.header("Simulation Settings", divider='rainbow')      

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
        
        # if st.sidebar.button("Submit Feedback"):
    
        # feedback_form('sidebar')
        # feedback_form('main')    

    with st.form(key='my_form'):
    
        st.header("Neonatal Critical Care Bed Use Modelling", divider='rainbow')

        st.markdown("""This is a stochastic discrete event simulation of each of the 3 levels of care provided in a neonatal critical care unit.""")

        st.write("")  
    
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

            # if st.checkbox('Show simulation Statistics'):
            st.subheader("Summary Statistics of Data")
            data_desc = data.describe()
            st.dataframe(data_desc)

            ###KPIs
            average_utilization = data['Utilization_Rate'].mean()
            max_queue_length = data['Queue_Length'].max()
            # Display KPIs using Markdown
            
            metric1,metric2,=st.columns(2,gap='small')
            with metric1:
                st.info('Average Utilization') #,icon="💰"
                st.metric(label="Average Utilization",value=f"{average_utilization:,.0f}")

            with metric2:
                st.info('Max Queue Length')
                st.metric(label="Max Queue Length",value=f"{max_queue_length:,.0f}")


            @st.cache_data
            def convert_df(df):
                # IMPORTANT: Cache the conversion to prevent computation on every rerun
                return df.to_csv().encode('utf-8')

            csv = convert_df(data)

            st.download_button(
                label="Download data as CSV",
                data=csv,
                file_name='Simulation_data.csv',
                mime='text/csv',
            )
            # ax.legend()

            # st.pyplot(fig)
        st.success('Done!')

        data.to_csv(resource_monitor_data_path)

    if stop_button:
        st.session_state['running'] = False


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

# ==================================================
# =================== Main Block ===================
# ==================================================

def main():
    st.sidebar.image('./NECS_Cropped_Dots.png', caption=None, width=200, use_column_width=None, clamp=False, channels="RGB", output_format="auto")
    # st.sidebar.divider()
    st.sidebar.header("Navigation", divider='rainbow')
    page = st.sidebar.radio("Select a Page", ["Main App", "Modify Parameters", "Submit Your Feedback"])
    # st.sidebar.divider()

    if page == "Main App":
        main_app()
    elif page == "Modify Parameters":
        modify_parameters_page()
    elif page == "Submit Your Feedback":
        submit_feedback_page()


if 'agreed' not in st.session_state:
    st.session_state['agreed'] = False

if st.session_state['agreed']:
    main()
else:
    display_agreement()


#### Add View run logs via Admin Panel
# border = "=" * 50
# text = " Plots ".center(50, '=')
# print(border)
# print(text)
# print(border)