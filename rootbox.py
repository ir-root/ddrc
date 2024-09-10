# Rootboi version 0.20.3
import tkinter as tk
from tkinter import Scale, Entry, Label, HORIZONTAL, messagebox
import subprocess
from picamera2 import Picamera2, Preview
from gpiozero import LED
import time
import os
from libcamera import controls, Transform
import threading
import sys
import re
from PIL import Image, ImageTk
import glob

base_dir = "/home/pi/rootbox/" # Set base directory
usb_media = "/media/pi" # Path to usb stick
#distance = 0.20

led = LED(24) # Set led to GPIO Pin 24
experiment_running_event = threading.Event() # Global Thread variable is set so the experiment thread can be closed when the main GUI thread is closed


def program_updater():
    global base_dir, usb_media

    if any(os.path.isdir(os.path.join(usb_media, i)) for i in os.listdir(usb_media)): # Check if a USB stick is connected
        update_file_path = os.path.join(usb_media, os.listdir(usb_media)[-1], "rootbox.py")

        if os.path.exists(update_file_path):
            with open(update_file_path, 'r') as update_file: # Read the first line of the update file to get the version
                new_version = update_file.readline().split()[-1]

            current_version = ''
            with open(os.path.join(base_dir, "rootbox.py"), 'r') as current_file: # Read the first line of the current rootbox.py file to get the version
                current_version = current_file.readline().split()[-1]

            if new_version != current_version:
                with open(os.path.join(base_dir, "rootbox.py"), 'w') as rootbox_file: # If versions are different, overwrite rootbox.py in the base_dir with the new rootbox.py
                    with open(update_file_path, 'r') as update_file:
                        rootbox_file.write(update_file.read())
                print(f"updated to version {new_version}")
                messagebox.showinfo("Program update", f"Program version {new_version} was found on the USB stick and updated. Please restart program to run the new version")



def create_setup_window(): # Sets up the starting window for the experiment where the experiment parameters can be entered
    global root, entry, scale_time, scale_distance
    root = tk.Tk()
    root.title("Rootboi v0.20.3")
    root.geometry("1000x200+0+0")

    # Check for update file on USB stick
    program_updater()

    # Experiment Name Label and Entry
    label1 = Label(root, text="Experiment Name:", height=3)
    label1.grid(row=0, column=0, sticky='e', padx=(50, 0))  # Align label to the east (right)
    entry = Entry(root)
    entry.grid(row=0, column=1)
    entry.bind("<FocusIn>", open_keyboard)  # Open the keyboard when cursor is in text field
    entry.bind("<FocusOut>", close_keyboard)  # Close the keyboard when out of text field

    # Time Between Images Label and Scale
    label2 = Label(root, text="Time between images (min):", height=3)
    label2.grid(row=1, column=0, sticky='e')  # Align label to the east (right)
    scale_time = Scale(root, from_=5, to=60, orient=HORIZONTAL, length =150)
    scale_time.set(10)  # Setting the default time
    scale_time.grid(row=1, column=1)

    # Distance Scale
    label3 = Label(root, text="Distance from camera to object (mm)", height=3)
    label3.grid(row=2, column=0, sticky='e')  # Align label to the east (right)
    scale_distance = Scale(root, from_=170, to=230, orient=HORIZONTAL, length =150)
    scale_distance.set(21)  # Setting the default distance
    scale_distance.grid(row=2, column=1)

    # Preview Button
    preview_button = tk.Button(root, text="Preview", command=on_preview, width=25, height=2)
    preview_button.grid(row=0, rowspan=2, column=2, columnspan=2, sticky='e', padx=(300, 0))

    # Start Experiment Button
    start_button = tk.Button(root, text="Start experiment", command=on_start, width=25, height=2)
    start_button.grid(row=2, column=3, columnspan=2, padx=(300, 0))    # Preview Button

    root.protocol("WM_DELETE_WINDOW", close_keyboard_and_exit)

def update_time(start_time, label, experiment_name): # Updates the elapsed time since the experiment started

    elapsed_seconds = time.time() - start_time

    days, hours, minutes, seconds = format_time(elapsed_seconds) # Transform elapsed seconds to days, hours, minutes, seconds

    formatted_time = f"{days} days, {hours:02d}:{minutes:02d}:{seconds:02d}" # Format into a string

    label.config(text=f"Experiment '{experiment_name}' is running... Time Elapsed: {formatted_time}")
    label.after(1000, update_time, start_time, label, experiment_name)  # Update every second

def format_time(elapsed_seconds):
    # Transforms seconds into days, hours, minutes, and seconds
    days = int(elapsed_seconds // (24 * 3600))
    remaining_time = elapsed_seconds % (24 * 3600)
    hours = int(remaining_time // 3600)
    remaining_time %= 3600
    minutes = int(remaining_time // 60)
    seconds = int(remaining_time % 60)
    return days, hours, minutes, seconds

def create_runtime_window(experiment_name, experiment_path, wait_time): # Sets up the runtime window which shows the elapsed time of the experiment and the file saving path for the images
    global runtime_window
    runtime_window = tk.Tk()
    runtime_window.title("Experiment Runtime")
    runtime_window.geometry("1000x510+0+0")

    # Elapsed time label
    runtime_label = tk.Label(runtime_window, text=f"Experiment '{experiment_name}' is running...")
    runtime_label.pack()

    # File path label
    filepath_label = tk.Label(runtime_window, text=f"Taking an image every {int(wait_time/60)} minutes. Images are saved to '{experiment_path}'")
    filepath_label.pack()

    # Start the timer
    start_time = time.time()
    update_time(start_time, runtime_label, experiment_name)

    # Preview label of last image taken
    image_label = tk.Label(runtime_window, image = None)
    image_label.pack()

    update_image_label(image_label, experiment_path, wait_time)

    # Quit button
    quit_button = tk.Button(runtime_window, text="Quit Experiment", command=close_application)
    quit_button.pack()

    runtime_window.protocol("WM_DELETE_WINDOW", close_application)

def update_image_label(label, experiment_path, wait_time):
    print("updating image...")
    preview_update_frequency = wait_time * 1000 + 5000
    list_of_files = glob.glob(experiment_path + '/*')  # * means all if need specific format then *.csv

    if not list_of_files:  # Checks if the list of files in the experiment folder is empty
        #print("short loop 1 second")
        label.after(1000, update_image_label, label, experiment_path, wait_time)  # Update image afer 1 second

    else:
        #print("long loop wait_time")

        try:
            latest_file = max(list_of_files, key=os.path.getctime)
            print("latest file is: ", latest_file)
            image = Image.open(latest_file)
            resized_image = image.resize((400, 400))  # Resize the image if necessary
            photo = ImageTk.PhotoImage(resized_image)
            label.configure(image=photo)
            label.image = photo  # To prevent garbage collection
        except Exception as e:
            print(f"Failed to load or display the image {latest_file}: {e}")
            label.after(1000, update_image_label, label, experiment_path, wait_time)  # Update image afer 1 second

        label.after(preview_update_frequency, update_image_label, label, experiment_path, wait_time)  # Update image after image interval time + 5 seconds

def close_application():
    experiment_running_event.clear()
    led.off()
    runtime_window.destroy()
    sys.exit()

def on_start():
    global experiment_running_event

    experiment_name = entry.get()
    if any(os.path.isdir(os.path.join(usb_media, i)) for i in os.listdir(usb_media)):  # Checks if a USB stick is connected
        experiment_path = os.path.join(usb_media, os.listdir(usb_media)[-1], "experiments", experiment_name)
    else:
        experiment_path = os.path.join(base_dir, "experiments", experiment_name)

    if experiment_name == "" or experiment_name.isspace() or re.search(r'[\\/:*?"<>|]', experiment_name):
        messagebox.showinfo("Invalid name", "Please enter a valid experiment name")
    elif os.path.exists(experiment_path):
        messagebox.showinfo("Name exists", "Experiment already exists. Please enter another name")

    else:
        experiment_running_flag = True
        slider_value = scale_time.get() # Get time between picture taking (in minutes) from slider
        slider_value = scale_time.get() # Get time between picture taking (in minutes) from slider
        distance = scale_distance.get()
        distance_r = 1 / (distance/1000) # Get the distance from camera to object, calculate reciprocal distance
        #distance_r = 1 / (distance) # Calculate reciprocal distance for the camera settings
        slider_value_seconds = slider_value * 60
        close_keyboard_and_exit()  # Closes the keyboard and the setup window
        create_runtime_window(experiment_name, experiment_path, slider_value_seconds)  # Open the new runtime window

        experiment_running_event.set() # Signal that the experiment is running

        experiment_thread = threading.Thread(target=run_experiment, args=(experiment_path, slider_value_seconds, distance_r)) # Start the experiment in a separate thread to keep the UI responsive meanwhile
        experiment_thread.start()

def run_experiment(experiment_path, wait_time, distance_r):
    os.makedirs(experiment_path, exist_ok = True)

    camera = camera_setup("still", distance_r)

    start_time = time.time() # Save start time of the experiment

    while experiment_running_event.is_set():

        camera.start()

        elapsed_seconds = int(time.time() - start_time)  # Calculate elapsed time in seconds

        days, hours, minutes, seconds = format_time(elapsed_seconds)  # Transform elapsed seconds to days, hours, minutes, seconds

        filename = f'{experiment_path}/img_{days}d{hours}h{minutes}m{seconds}s.png' # Set filename to Year-month-day-hour-minute-second.jpg

        led.on() # Turn IR LEDs on and give them 3 sec to start up before image is taken
        time.sleep(3)

        try:    # Try/except: In some rare occasions the camera was not available, so by using try/except the loop keeps running even if there is an error with accessing the camera
            camera.capture_file(filename)  # Take picture
            print(f"image {filename} has been taken")
            print("set distance for the image was: ", distance_r)
            # Update the image in the GUI
        except Exception as e:
            print(f"An error has ocurred during taking image {filename}: {e}")

        camera.stop()

        led.off()

        # Check every second for the remaining wait time if experimet_running_event flag is still set or if the process should be closed
        for _ in range(int(wait_time-3)):
            if not experiment_running_event.is_set():
                break
            time.sleep(1)

def camera_setup(mode, distance_r):

    camera = Picamera2()     # Initialize camera

    if mode == "preview":
        camera_config = camera.create_preview_configuration() # Create a camera configuration object for preview mode
    elif mode == "still":
        camera_config = camera.create_still_configuration() # Create a camera configuration object for image taking mode

    camera_config["main"]["size"] = (2400, 1800) # Maximum resolution for Pi Camera Module 3 is 4608 x 2592

    # camera_config["transform"] = Transform(vflip=True) # Flips the camera image 180 degrees if necessary

    camera_config["controls"]["ExposureTime"] = 5000 # Set a fixed exposure time

    # Set white balance
    #camera_config["controls"]["AwbMode"] = controls.AwbModeEnum.Custom
    #camera_config["controls"]["ColourGains"] = (1.2, 1.5) # For white balance, first is red gain and second is blue gain

    #camera_config["controls"]["AnalogueGain"] = 200  # Set ISO value

    #camera_config["controls"]["Contrast"] = 1 # Set contrast form 0-32, default is 1

    camera_config["controls"]["Saturation"] = 0 # set to greyscale
    camera_config["controls"]["ScalerCrop"] = (1000,400,2400,1800) # Camera cropping: x_offset, y_offset, width, height


    camera_config["controls"]["AfMode"] = controls.AfModeEnum.Manual
    camera_config["controls"]["LensPosition"] = distance_r

    camera.configure(camera_config)  # Configure the camera with the configuration specified above


    #camera.start()

    #camera.set_controls({"AfMode": controls.AfModeEnum.Manual, "LensPosition": distance_r})  # Set additional controls: Autofocus manual and distance to object

    return camera

def open_keyboard(event):
    subprocess.Popen(["wvkbd-mobintl", "-L", "300"]) # The wvkbd on-screen keyboard is used for text input.

def close_keyboard(event):
    subprocess.Popen(["pkill", "wvkbd-mobintl"])

def close_keyboard_and_exit():
    subprocess.Popen(["pkill", "wvkbd-mobintl"])
    root.destroy()


def on_preview():
    global scale_distance

    root.focus_set()  # Shift focus to the root window
    close_keyboard(None)

    distance = scale_distance.get()
    distance_r = 1 / (distance / 1000)  # Get the distance from camera to object, calculate reciprocal distance

    #distance_r = 1 / (distance)  # Calculate reciprocal distance for the camera settings

    led.on()

    camera = camera_setup("preview", distance_r)

    print("set distance is: ", distance_r)

    camera.start_preview(Preview.QT)
    camera.start()
    time.sleep(10)
    try:
        camera.stop_preview()
    except Exception as e:
        pass
    camera.stop()
    camera.close()
    led.off()

create_setup_window() # Create the initial setup window

root.mainloop() # Start the Tkinter event loop



