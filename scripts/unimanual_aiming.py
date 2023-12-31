# Imports
from psychopy import visual, core
import numpy as np
import pandas as pd
import src.lib as lib
from datetime import datetime
import copy
import os
import nidaqmx

# To Do:
# 1. add in visual perturbations (clamp and offset)
# 2. add code to test vibrations before experiment

# ------------------Blocks to run ------------------
# Use this to run whole protocol
# make sure the strings match the names of the sheets in the excel
# ExpBlocks = [
#     "Practice",
#     "Baseline", 
#     "Exposure",
#     "Post"
#     ]

# For testing a few trials
ExpBlocks = ["Baseline"]

# ----------- Participant info ----------------

# For clamp and rotation direction
rot_direction = 1  # 1 for forwrad, -1 for backward
participant = 99


study_id = "Wrist Visuomotor Rotation"
experimenter = "Gregg"
current_date = datetime.now()
date_time_str = current_date.strftime("%Y-%m-%d %H:%M:%S")


study_info = {
    "Participant ID": participant,
    "Date_Time": date_time_str,
    "Study ID": study_id,
    "Experimenter": experimenter,
}
# experiment_info = pd.DataFrame.from_dict(study_info)

if not participant == 99:
    print(study_info)
    input(
        """
        Make sure changed the participant info is correct before continuing.
        Press enter to continue.
        """
    )

# # Check if directory exists and if it is empty
dir_path = f"data/p{str(participant)}"

if not participant == 99:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(
            """
        Directory didn't exist so one was created. Continuing with program.
        """
        )
    elif len(os.listdir(dir_path)) == 0:
        print(
            """
        Directory already exists and is empty. Continuing with program."""
        )
    elif os.path.exists(dir_path) and not len(dir_path) == 0:
        print(
            """
        This directory exists and isn't empty, exiting program.
        Please check the contents of the directory before continuing.
        """
        )
        exit()

# set up file path
file_path = f"data/p{str(participant)}/p{str(participant)}"
# pd.DataFrame.from_dict(study_info).to_csv(f"{file_path}_study_information.csv")
print("Setting everything up...")

# ------------------------ Set up --------------------------------

# Variables set up
cursor_size = 0.075
target_size = 0.3
home_size = 0.15
home_range_size = home_size * 5
fs = 500
timeLimit = 2

# Create NI channels
# Inputs
input_task = nidaqmx.Task()
input_task.ai_channels.add_ai_voltage_chan("Dev1/ai0", min_val=0, max_val=5)
input_task.ai_channels.add_ai_voltage_chan("Dev1/ai2", min_val=0, max_val=5)
input_task.timing.cfg_samp_clk_timing(
    fs, sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS
)

# Outputs - have to create separate tasks for input/output
output_task = nidaqmx.Task()
output_task.do_channels.add_do_chan("Dev1/port0/line0")
output_task.do_channels.add_do_chan("Dev1/port0/line1")


# Create data structs
# For single trial

## Psychopy set up
# Create window
win = visual.Window(
    fullscr=True,
    monitor="testMonitor",
    units="pix",
    color="black",
    waitBlanking=False,
    screen=1,
    size=[1920, 1080],
)


# set up clocks
move_clock = core.Clock()
home_clock = core.Clock()
trial_delay_clock = core.Clock()

int_cursor = visual.Rect(
    win,
    width=lib.cm_to_pixel(cursor_size),
    height=lib.cm_to_pixel(20),
    fillColor="Black",
)

target = visual.Rect(
    win,
    width=lib.cm_to_pixel(target_size),
    height=lib.cm_to_pixel(20),
    lineColor="red",
    fillColor=None,
)

# Data dicts for storing data
trial_summary_data_template = {
    "trial_num": [],
    "move_times": [],
    "elbow_end": [],
    "curs_end": [],
    "error": [],
    "block": [],
    "trial_delay": [],
    "target": [],
}

# For online position data
position_data_template = {
    "elbow_pos": [],
    "time": [],
}

print("Done set up")

# -------------- start main experiment loop ------------------------------------
input("Press enter to continue to first block ... ")
for block in range(len(ExpBlocks)):
    condition = lib.read_trial_data("Trials.xlsx", ExpBlocks[block])
    file_ext = ExpBlocks[block]

    # Summary data dictionaries for this block
    block_data = copy.deepcopy(trial_summary_data_template)

    # starts NI DAQ task for data collection and output
    input_task.start()
    output_task.start()

    for i in range(len(condition.trial_num)):
        # Creates dictionary for single trial
        current_trial = copy.deepcopy(trial_summary_data_template)
        position_data = copy.deepcopy(position_data_template)

        # Set up vibration output
        if condition.vibration[i] == 0:
            vib_output = [False, False]
        elif condition.vibration[i] == 1:
            vib_output = [True, True]
        elif condition.vibration[i] == 2:
            vib_output = [True, False] # BICEPS
        elif condition.vibration[i] == 3:
            vib_output = [False, True] # TRICEPS

        int_cursor.color = None
        int_cursor.draw()
        win.flip()

        # Sets up target position
        target_jitter = np.random.uniform(-0.25, 0.25)  # jitter target position
        target_amplitude = condition.target_amp[i] + target_jitter
        current_target_pos = lib.calc_target_pos(0, target_amplitude)

        # Run trial
        input(f"Press enter to start trial # {i+1} ... ")
        rand_wait = np.random.randint(300, 701)
        current_trial["trial_delay"].append(rand_wait / 1000)
        block_data["trial_delay"].append(rand_wait / 1000)
        trial_delay_clock.reset()
        while trial_delay_clock.getTime() < rand_wait / 1000:
            current_time = trial_delay_clock.getTime()
            current_pos = lib.get_x(input_task)
            position_data["elbow_pos"].append(current_pos[0])
            position_data["time"].append(current_time)

        if not condition.full_feedback[i]:
            int_cursor.color = None

        # Start vibration
        output_task.write(vib_output)

        # Display target position
        lib.set_position(current_target_pos, target)
        win.flip()

        # run trial until time limit is reached or target is reached
        move_clock.reset()
        while move_clock.getTime() < timeLimit:
            # Run trial
            current_time = move_clock.getTime()
            current_pos = lib.get_x(input_task)
            target.draw()
            lib.set_position(current_pos, int_cursor)
            win.flip()

            # Save position data
            position_data["elbow_pos"].append(current_pos[0])
            position_data["time"].append(current_time)

        # if current_vel <= 20:
        output_task.write([False, False])
        # Append trial data to storage variables
        if condition.terminal_feedback[i]:
            int_cursor.color = "Green"
            int_cursor.draw()
            target.draw()
            win.flip()

        # Leave current window for 200ms
        core.wait(0.2, hogCPUperiod=0.2)
        int_cursor.color = None
        int_cursor.draw()
        win.flip()

        # Print trial information
        print(f"Trial {i+1} done.")
        print(f"Movement time: {round((current_time*1000),1)} ms")
        print(
            f"Target position: {condition.target_amp[i]}     Cursor Position: {round(lib.pixel_to_cm(int_cursor.pos[0]),3)}"
        )
        print(
            f"Error: {round((lib.pixel_to_cm(int_cursor.pos[0]) - condition.target_amp[i]),3)}"
        )
        print(" ")

        # Write and save data for individual trial
        current_trial["move_times"].append(current_time)
        current_trial["elbow_end"].append(lib.pixel_to_cm(current_pos[0]))
        current_trial["curs_end"].append(lib.pixel_to_cm(int_cursor.pos[0]))
        current_trial["error"].append(
            lib.pixel_to_cm(int_cursor.pos[0]) - condition.target_amp[i]
        )
        current_trial["trial_num"].append(i + 1)
        current_trial["block"].append(ExpBlocks[block])
        current_trial["target"].append(target_amplitude)

        # Save data to CSV
        pd.DataFrame.from_dict(current_trial).to_csv(
            f"{file_path}_trial_{str(i+1)}_{file_ext}.csv", index=False
        )
        pd.DataFrame.from_dict(position_data).to_csv(
            f"{file_path}_position_{str(i+1)}_{file_ext}.csv", index=False
        )

        # Append data for whole block
        block_data["move_times"].append(current_time)
        block_data["elbow_end"].append(lib.pixel_to_cm(current_pos[0]))
        block_data["curs_end"].append(lib.pixel_to_cm(int_cursor.pos[0]))
        block_data["error"].append(
            lib.pixel_to_cm(int_cursor.pos[0]) - condition.target_amp[i]
        )
        block_data["trial_num"].append(i + 1)
        block_data["block"].append(ExpBlocks[block])
        block_data["target"].append(target_amplitude)

        del current_trial, position_data

    # End of bock saving
    print("Saving Data")
    trial_data = pd.merge(
        pd.DataFrame.from_dict(block_data),
        pd.DataFrame.from_dict(condition),
        on="trial_num",
    )

    trial_data.to_csv(file_path + "_" + file_ext + ".csv", index=False)
    trial_data.to_excel(file_path + "_" + file_ext + ".xlsx", index=False)

    print("Data Succesfully Saved")

    del condition, trial_data, block_data
    input_task.stop()
    output_task.stop()
    input("Press enter to continue to next block ... ")

input_task.close()
output_task.close()
print("Experiment Done")
