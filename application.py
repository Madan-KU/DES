import os
import io
import csv
import json
import time
import yaml
import simpy
import numpy as np
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
import plotly.express as px
import plotly.graph_objects as go
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

if 'plot_initialized' not in st.session_state:
    st.session_state.plot_initialized = False

USER_CREDENTIALS = {
    "necs": "necs",
}

def check_login(username, password):
    return username in USER_CREDENTIALS and USER_CREDENTIALS[username] == password

def show_login_page():
    st.title("Access Authentication")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if check_login(username, password):
            st.session_state['logged_in'] = True
            st.experimental_rerun()
        else:
            st.error("Invalid username or password.")

   
# ==================================================
# ===================== Plots ======================
# ==================================================
           
def plot_resource_utilization(data):

    mean_NICU = data[data['Resource'] == 'NICU']['Daily_Use'].mean()
    mean_HDCU = data[data['Resource'] == 'HDCU']['Daily_Use'].mean()
    mean_SCBU = data[data['Resource'] == 'SCBU']['Daily_Use'].mean()

    # Display the metrics
    with st.container(border=True):
        st.info(" Average Utilization by Resource")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Average NICU", value=f"{mean_NICU:.2f}")
        with col2:
            st.metric(label="Average HDCU", value=f"{mean_HDCU:.2f}")
        with col3:
            st.metric(label="Average SCBU", value=f"{mean_SCBU:.2f}")

        col1, col2, col3 = st.columns(3)

    fig = go.Figure()

    resources = data['Resource'].unique()
    for resource in resources:
        resource_data = data[data['Resource'] == resource]

        mean_line = resource_data.groupby('Day')['Daily_Use'].mean().reset_index()
        fig.add_trace(go.Scatter(x=mean_line['Day'], y=mean_line['Daily_Use'], 
                                 mode='lines', name=f'{resource} Mean', line=dict(width=3)))

    fig.update_layout(title='Resource Utilization Over Time', xaxis_title='Day', yaxis_title='Average Daily Use')
    st.plotly_chart(fig)   




def plot_queue_length(data):
    queue_len_NICU = data[data['Resource'] == 'NICU']['Queue_Length'].mean()
    queue_len_HDCU = data[data['Resource'] == 'HDCU']['Queue_Length'].mean()
    queue_len_SCBU = data[data['Resource'] == 'SCBU']['Queue_Length'].mean()

    # Display the metrics
    with st.container(border=True):
        st.info("Average Queue Length by Resource")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Average NICU", value=f"{queue_len_NICU:.2f}")
        with col2:
            st.metric(label="Average HDCU", value=f"{queue_len_HDCU:.2f}")
        with col3:
            st.metric(label="Average SCBU", value=f"{queue_len_SCBU:.2f}")

    fig = go.Figure()

    resources = data['Resource'].unique()
    for resource in resources:
        resource_data = data[data['Resource'] == resource]

        mean_line = resource_data.groupby('Day')['Queue_Length'].mean().reset_index()
        fig.add_trace(go.Scatter(x=mean_line['Day'], y=mean_line['Queue_Length'], 
                                 mode='lines', name=f'{resource} Mean', line=dict(width=3)))

    fig.update_layout(title='Queue Length Over Time', xaxis_title='Day', yaxis_title='Average Queue Length')
    st.plotly_chart(fig)
        
def plot_available_capacity(data):
    Available_Capacity_NICU = data[data['Resource'] == 'NICU']['Available_Capacity'].mean()
    Available_Capacity_HDCU = data[data['Resource'] == 'HDCU']['Available_Capacity'].mean()
    Available_Capacity_SCBU = data[data['Resource'] == 'SCBU']['Available_Capacity'].mean()

    # Display the metrics
    with st.container(border=True):
        st.info("Average Available Capacity by Resource")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Average NICU", value=f"{Available_Capacity_NICU:.2f}")
        with col2:
            st.metric(label="Average HDCU", value=f"{Available_Capacity_HDCU:.2f}")
        with col3:
            st.metric(label="Average SCBU", value=f"{Available_Capacity_SCBU:.2f}")

    fig = go.Figure()

    resources = data['Resource'].unique()
    for resource in resources:
        resource_data = data[data['Resource'] == resource]

        mean_line = resource_data.groupby('Day')['Available_Capacity'].mean().reset_index()
        fig.add_trace(go.Scatter(x=mean_line['Day'], y=mean_line['Available_Capacity'], 
                                 mode='lines', name=f'{resource} Mean', line=dict(width=3)))

    fig.update_layout(title='Available Capacity for Neonatal Care Units Over Time', 
                      xaxis_title='Day', yaxis_title='Available Capacity')
    st.plotly_chart(fig)
    
def plot_admission_discharge_trends_moving_avg(data):
    colors = {'NICU': 'blue', 'HDCU': 'red', 'SCBU': 'green'}
    daily_use = data.groupby(['Day', 'Resource'])['Daily_Use'].sum().unstack()
    admissions = daily_use.diff().clip(lower=0)
    discharges = -daily_use.diff().clip(upper=0)

    admissions_avg = admissions.rolling(window=7).mean().melt(ignore_index=False, var_name='Resource', value_name='Admissions').reset_index()
    discharges_avg = discharges.rolling(window=7).mean().melt(ignore_index=False, var_name='Resource', value_name='Discharges').reset_index()

    Avg_Admission_NICU = admissions_avg[admissions_avg['Resource'] == 'NICU']['Admissions'].mean()
    Avg_Admission_HDCU = admissions_avg[admissions_avg['Resource'] == 'HDCU']['Admissions'].mean()
    Avg_Admission_SCBU = admissions_avg[admissions_avg['Resource'] == 'SCBU']['Admissions'].mean()

    Avg_Discharge_NICU = discharges_avg[discharges_avg['Resource'] == 'NICU']['Discharges'].mean()
    Avg_Discharge_HDCU = discharges_avg[discharges_avg['Resource'] == 'HDCU']['Discharges'].mean()
    Avg_Discharge_SCBU = discharges_avg[discharges_avg['Resource'] == 'SCBU']['Discharges'].mean()

    fig = go.Figure()

    with st.container(border=True):
        st.info("Average Admissions and Discharges by Resource")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="NICU Admissions", value=f"{Avg_Admission_NICU:.2f}")
        with col2:
            st.metric(label="HDCU Admissions", value=f"{Avg_Admission_HDCU:.2f}")
        with col3:
            st.metric(label="SCBU Admissions", value=f"{Avg_Admission_SCBU:.2f}")

        col4, col5, col6 = st.columns(3)
        with col4:
            st.metric(label="NICU Discharges", value=f"{Avg_Discharge_NICU:.2f}")
        with col5:
            st.metric(label="HDCU Discharges", value=f"{Avg_Discharge_HDCU:.2f}")
        with col6:
            st.metric(label="SCBU Discharges", value=f"{Avg_Discharge_SCBU:.2f}")

    # Plot for admissions and discharges
    for resource in admissions_avg['Resource'].unique():
        admissions_data = admissions_avg[admissions_avg['Resource'] == resource]
        discharges_data = discharges_avg[discharges_avg['Resource'] == resource]

        # Admissions
        fig.add_trace(go.Scatter(x=admissions_data['Day'], y=admissions_data['Admissions'], mode='lines+markers', 
                                 name=f'{resource} Admissions', #line=dict(color=colors[resource], width=2), 
                                 marker=dict(symbol='circle')))
        
        # Discharges
        fig.add_trace(go.Scatter(x=discharges_data['Day'], y=discharges_data['Discharges'], mode='lines+markers', 
                                 name=f'{resource} Discharges', #line=dict(color=colors[resource], width=2), 
                                 marker=dict(symbol='x')))

    fig.update_layout(title='7-Day Moving Average of Admissions and Discharges by Resource', 
                      xaxis_title='Day', yaxis_title='7-Day Moving Average', 
                      legend_title='Category')
    st.plotly_chart(fig)

def plot_daywise_resource_utilization(data):
    data['Utilization_Rate'] = data['Daily_Use'] / data['Total_Capacity']

    avg_utilization_NICU = data[data['Resource'] == 'NICU']['Utilization_Rate'].mean()
    avg_utilization_HDCU = data[data['Resource'] == 'HDCU']['Utilization_Rate'].mean()
    avg_utilization_SCBU = data[data['Resource'] == 'SCBU']['Utilization_Rate'].mean()

    with st.container(border=True):
        st.info("Average Utilization Rate by Resource")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="NICU", value=f"{avg_utilization_NICU:.2f}")
        with col2:
            st.metric(label="HDCU", value=f"{avg_utilization_HDCU:.2f}")
        with col3:
            st.metric(label="SCBU", value=f"{avg_utilization_SCBU:.2f}")

    fig = go.Figure()
    colors = {'NICU': 'blue', 'HDCU': 'red', 'SCBU': 'green'}

    # Calculate and plot the daily average for each resource
    resources = data['Resource'].unique()
    for resource in resources:
        resource_data = data[data['Resource'] == resource]
        daily_avg = resource_data.groupby('Day')['Utilization_Rate'].mean().reset_index()
        fig.add_trace(go.Scatter(x=daily_avg['Day'], y=daily_avg['Utilization_Rate'], mode='lines', name=f'{resource} Average'))

    # Update the layout
    fig.update_layout(title='Average Daily Resource Utilization Rate',
                      xaxis_title='Day',
                      yaxis_title='Utilization Rate',
                      legend_title='Resource')
    st.plotly_chart(fig)

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

    with st.container(border=True):
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
[Placeholder]
## Key Features
[Placeholder]

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

    with st.container(border=True):
        st.info("### Admin Login")
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
            plot_admission_discharge_trends_moving_avg(data)

            st.subheader("Day-wise Resource Utilization")
            plot_daywise_resource_utilization(data)

            with st.container(border=True):
                st.info("*//Experimental//*")
                st.subheader("Summary Statistics of Data")

                # Filter options for displaying fields
                all_columns = data.columns.tolist()
                selected_columns = st.multiselect("Select fields to display", all_columns, default=all_columns)

                # Display only selected fields in the summary statistics
                data_desc = data[selected_columns].describe()
                st.dataframe(data_desc)

                # # Check if plots are initialized
                # if not st.session_state.plot_initialized:
                #     # Plotting code (this will run only once or when explicitly updated)
                #     plot_data()
                #     st.session_state.plot_initialized = True

                ### KPIs
                if 'Utilization_Rate' in selected_columns:
                    average_utilization = data['Utilization_Rate'].mean()
                    metric1, metric2 = st.columns(2, gap='small')
                    with metric1:
                        st.info('Average Utilization')
                        st.metric(label="Average Utilization", value=f"{average_utilization:,.4f}")
                
                if 'Queue_Length' in selected_columns:
                    max_queue_length = data['Queue_Length'].max()
                    with metric2:
                        st.info('Max Queue Length')
                        st.metric(label="Max Queue Length", value=f"{max_queue_length:,.0f}")

                



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
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if True: # st.session_state['logged_in']:
    def main():
        st.sidebar.image('./NECS_Cropped_Dots.png', caption=None, width=200, use_column_width=None, clamp=False, channels="RGB", output_format="auto")
        # st.sidebar.divider()
        st.sidebar.header("Navigation", divider='rainbow')
        page = st.sidebar.radio("Select a Page", ["Main App", "Modify Parameters", "Submit Your Feedback"])
        # st.sidebar.divider()

        if  page == "Main App":
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
else:
    show_login_page()

#### Add View run logs via Admin Panel
# border = "=" * 50
# text = " Plots ".center(50, '=')
# print(border)
# print(text)
# print(border)