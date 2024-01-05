import os
import simpy
import random
import pandas as pd
import logging

from modules.logger_configurator import configure_logger
from modules.read_config import read_config

configure_logger()
config = read_config('parameters.yaml')

logger = logging.getLogger(__name__)

def Simulate(sim_params): #Working**
    print("Accessing simulation parameters in simulation.py:")
    
    for attr_name in dir(sim_params):
        if not callable(getattr(sim_params, attr_name)) and not attr_name.startswith("__"):
            # print(f"{attr_name}: {getattr(sim_params, attr_name)}") 
            globals()[attr_name] = getattr(sim_params, attr_name)



# Class representing our births requiring additional care.
class Birth_Patient:
    def __init__(self, p_id, prob_NICU, prob_HDCU, prob_SCBU):
        self.id = p_id
        self.q_time_NICU = 0
        self.q_time_HDCU = 0
        self.q_time_SCBU = 0
        self.NICU_Pat = False
        self.HDCU_Pat = False
        self.SCBU_Pat = False
        self.prob_NICU = prob_NICU
        self.prob_HDCU = prob_HDCU
        self.prob_SCBU = prob_SCBU
        self.nicu_chance = 0
        self.hdcu_chance = 0
        self.scbu_chance = 0
        self.pat_monitor_df = pd.DataFrame()

            
    def determine_destiny(self, prob_var, var_pat, var_chance):
        sc = random.uniform(0, 1)
        if sc < prob_var:
            setattr(self, var_pat, True)
            setattr(self, var_chance, sc)

    # NOT NORMALL IN USE DUE TO SEVERE PERFORMANCE ISSUES, ONLY HERE TO MONITOR WHEN NECESSARY        
    def pat_monitor(self,run_number, day_number):
        id = self.id 
        nicu_pat = self.NICU_Pat
        nicu_prob = self.nicu_chance
        hdcu_pat = self.HDCU_Pat
        hdcu_prob = self.hdcu_chance
        scbu_pat = self.SCBU_Pat
        scbu_prob = self.scbu_chance
        rn = run_number
        dn = day_number
    
        # append data to the dataframe
        
        self.pat_monitor_df = self.pat_monitor_df.append({"Run_Number": rn,
                                                        "Day_Number": dn,
                                                        "Pat_ID": id,
                                                        "nicu_pat": nicu_pat,
                                                        "nicu_prob": nicu_prob,
                                                        "hdcu_pat": hdcu_pat,
                                                        "hdcu_prob": hdcu_prob,
                                                        "scbu_pat": scbu_pat,
                                                        "scbu_prob": scbu_prob},
                                                        ignore_index=True)

    def write_pat_details(self):
        with open("./patient_monitor_data.csv", "a", newline='') as f:
            writer = csv.writer(f, delimiter=",")    
            for index, row in self.pat_monitor_df.iterrows():
                writer.writerow(row)


# Class representing our model of Neonatal Unit.

class NamedResource(simpy.PriorityResource):
    def __init__(self, *args, name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name


class NCCU_Model:


    def __init__(self, sim_params_instance):

        self.env = simpy.Environment()
        self.patient_counter = 0

        self.NICU = NamedResource(self.env, capacity=number_of_NICU_cots, name='NICU')
        self.HDCU = NamedResource(self.env, capacity=number_of_HDCU_cots, name='HDCU')
        self.SCBU = NamedResource(self.env, capacity=number_of_SCBU_cots, name='SCBU')
        
        self.run_number = number_of_runs#####

        self.mean_q_time_cot = 0



        #"""2"""
        self.results_df = pd.DataFrame()
        self.results_df["P_ID"] = []
        self.results_df["Start_Q_Cot"] = []
        self.results_df["Q_Time_NICU"] = []
        self.results_df["Q_Time_HDCU"] = []
        self.results_df["Q_Time_SCBU"] = []
        self.results_df.set_index("P_ID", inplace=True)

        self.resource_monitor_df = pd.DataFrame()
        self.results_df["Run_Number"] = []
        self.results_df["Day"] = []
        self.results_df["Resource"] = []
        self.results_df["Daily_Use"] = []
        self.results_df["Total_Capacity"] = []
        self.results_df["Available_Capacity"] = []
        self.results_df["Queue_Length"] = []

        self.NICU_usage = {}
        self.HDCU_usage = {}
        self.SCBU_usage = {}
        

    def generate_birth_arrivals(self):
        # logger.info("#>Enter generate_birth_arrivals")   
        # Keep generating until the simulation duration is reached
        for _ in range(sim_duration):
            # With day as our currency for timestamps here we need to generate multiple agents per day
            sampled_num = round(random.expovariate(1.0 / day_births_inter), 0)
            sampled_num = int(sampled_num)
            for i in range(sampled_num):
                # Increment the patient counter by 1
                self.patient_counter += 1

                # Create a new patient instance of the Birth_Patient class,
                # and give the patient an ID determined by the patient counter
                birth = Birth_Patient(self.patient_counter, chance_need_NICU, chance_need_HDCU, chance_need_SCBU)

                birth.determine_destiny(chance_need_NICU, 'NICU_Pat', 'nicu_chance')
                birth.determine_destiny(chance_need_HDCU, 'HDCU_Pat', 'hdcu_chance')
                birth.determine_destiny(chance_need_SCBU, 'SCBU_Pat', 'scbu_chance')

                # THIS MONITORING SIGNIFICANTLY DEGRADES PERFORMANCE ONLY UN_COMMENT
                # TEMPORARILY TO CHECK VARIABLE ASSIGNMENTS
                # birth.pat_monitor(self.run_number, self.env.now)
                # birth.write_pat_details()

                # Get the SimPy environment to run the manage_birth_resource method
                # with this patient
                self.env.process(self.manage_birth_resource(birth))

                # Freeze this function until that time has elapsed
            yield self.env.timeout(1)
            # logger.info("#>Exit generate_birth_arrivals")   




            
    def process_cot_request(self, cot_request, birth, start_cot_wait, avg_stay, next_chances, cot_pat):
        with cot_request:
            # Record the time the patient finished queuing
            end_wait = self.env.now

            # Calculate the time this patient spent queuing for a cot and
            # store in the patient's attribute
            birth.q_time_cot = end_wait - start_cot_wait

            # Randomly sample the time the patient will spend in cot
            sampled_cot_duration = round(random.expovariate(1.0 / avg_stay), 0)
            sampled_cot_duration = int(sampled_cot_duration)

            # Freeze this function until that time has elapsed
            yield self.env.timeout(sampled_cot_duration)

            # reset cot flagv
            setattr(birth, cot_pat, False)

            #calculate the new chances to need the other types of resource having exited one
            for chance, pat, chance_name in next_chances:
                birth.determine_destiny(chance, pat, chance_name)
                if not getattr(birth, pat):
                    break


    # A method that models the processes for births and assigning resources.
    # The method needs to be passed a patient who may require resources
    def manage_birth_resource(self, birth):
        # Record the time the patient started queuing for a cot
        start_cot_wait = self.env.now
        # logger.info("#>enter manage_birth_resource block")  

        # Release immediately any agents that dont require any resource
        if not (birth.NICU_Pat or birth.HDCU_Pat or birth.SCBU_Pat): 
            return

        # Open a while so that any required cot can be processed while needed
        while birth.NICU_Pat or birth.HDCU_Pat or birth.SCBU_Pat:

            #"""Process NICU Requirement"""
            if birth.NICU_Pat == True:
                # Request a NICU cot only
                req = self.NICU.request()
                yield req
                yield from self.process_cot_request(
                    req, # self.NICU.request(), ####> day_births_inter** will raise issues
                    birth,
                    start_cot_wait,
                    avg_NICU_stay,
                    [
                        (chance_need_HDCU_after_NICU, 'HDCU_Pat', 'hdcu_chance'),
                        (chance_need_SCBU_after_NICU, 'SCBU_Pat', 'scbu_chance')
                    ],
                    'NICU_Pat'
                )
                self.NICU.release(req)
                # logger.info("#>exiting manage_birth_resource")  
                break  
            

            # Reinitialise the cot wait on exiting the previous Cot
            start_cot_wait = self.env.now

            #"""Process HDU Requirement"""
            
            
            if birth.HDCU_Pat:

                hdu_req = self.HDCU.request(priority=0)
                nicu_req = self.NICU.request(priority=1)

                requests = {self.HDCU: hdu_req, self.NICU: nicu_req}

                # Make a request for each type of cot
                results = yield simpy.AnyOf(self.env, requests.values())

                # Check which request was successful and cancel the other
                used_req = next(iter(results))  # The request that succeeded
                used_res = next(res for res, req in requests.items() if req == used_req)  # The resource for that request

                for res, req in requests.items():
                    if req != used_req:
                        req.cancel()  # Cancel the unused request
                        res.release(req)

                # Now process the used request
                yield from self.process_cot_request(
                    used_req,
                    birth,
                    start_cot_wait,
                    avg_HDCU_stay if used_res == self.HDCU else avg_NICU_stay,
                    [
                        (chance_need_NICU_after_HDCU, 'NICU_Pat', 'nicu_chance'),
                        (chance_need_SCBU_after_HDCU, 'SCBU_Pat', 'scbu_chance')
                    ],
                    'HDCU_Pat'
                )
                used_res.release(used_req)

                break

            # Reinitialise the cot wait on exiting the previous Cot
            start_cot_wait = self.env.now
        
            #"""Process SCBU Requirement"""
            if birth.SCBU_Pat:
                
                scbu_req = self.SCBU.request(priority=0)
                hdu_req = self.HDCU.request(priority=1)
                nicu_req = self.NICU.request(priority=2)

                requests = {self.SCBU: scbu_req, self.HDCU: hdu_req, self.NICU: nicu_req}

                # Make a request for each type of cot
                results = yield simpy.AnyOf(self.env, requests.values())

                # Check which request was successful and cancel the other
                used_req = next(iter(results))  # The request that succeeded
                used_res = next(res for res, req in requests.items() if req == used_req)  # The resource for that request

                for res, req in requests.items():
                    if req != used_req:
                        req.cancel()  # Cancel the unused request
                        res.release(req)

                # Now process the used request
                yield from self.process_cot_request(
                    used_req,
                    birth,
                    start_cot_wait,
                    avg_HDCU_stay if used_res == self.HDCU else avg_NICU_stay,
                    [
                        (chance_need_NICU_after_SCBU, 'NICU_Pat', 'nicu_chance'),
                        (chance_need_HDCU_after_SCBU, 'HDCU_Pat', 'hdcu_chance')
                    ],
                    'SCBU_Pat'
                )
                used_res.release(used_req)

                break
            
            # Reinitialise the cot wait on exiting the previous Cot
            start_cot_wait = self.env.now
            
    def monitor(self, resource):
        # logger.info("#>Enter Monitor")   
        
        if self.env.now > warm_up_duration:
            day = resource._env.now  # current simulation time
            usage = resource.count # resource count
            total_capacity = resource.capacity # resource capacity
            available_capacity = total_capacity - usage # available resource capacity
            resource_name = resource.name # What resource type?
            queue_length = len(resource.queue) # number of waiting

            # append data to the dataframe
            new_row = pd.DataFrame({
                "Run_Number": [self.run_number],
                "Day": [day],
                "Resource": [resource_name],
                "Daily_Use": [usage],
                "Total_Capacity": [total_capacity],
                "Available_Capacity": [available_capacity],
                "Queue_Length": [queue_length]
                })

            self.resource_monitor_df = pd.concat([self.resource_monitor_df, new_row], ignore_index=True)
            # logger.info(self.resource_monitor_df)
            # logger.info("Exit Monitor")

        
    def monitor_resource(self, resource):
        # logger.info("Enter Monitor Resource")
        while True:
            self.monitor(resource)  
            yield self.env.timeout(1)  # Check resource usage every 1 time unit  
        # logger.info("Exit Monitor Resource")


    
    def daily_scheduler(self):
        # logger.info("#>Enter Daily Scheduler")
        while True:
            # Wait for 1 day
            yield self.env.timeout(1)
            # Call monitor for each resource

            

            self.monitor(self.NICU)
            self.monitor(self.HDCU)
            self.monitor(self.SCBU)
        # logger.info("#>Exit Daily Scheduler")       
 

    # The run method starts up the entity generators, and tells SimPy to start
    # running the environment for the duration specified in the g class. After
    # the simulation has run, it calls the methods that calculate run
    # results, and the method that writes these results to file
    def run(self):
        # logger.info("#> Enter Run Block")   
        
        # Start entity generators
        self.env.process(self.generate_birth_arrivals())

        # logger.info("#>#> generate birth arrivals in Run Block{}")  

        self.env.process(self.daily_scheduler())
        
        # logger.info("#> daily scheduler complete") 
        # Run simulation
        self.env.run(until=sim_duration)

        
        
        # Write run results to file
        #self.write_run_results()
        
        
if __name__ == '__main__':
    configure_logger()
    config = read_config('parameters.yaml')
