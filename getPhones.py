from datetime import datetime
import importlib.metadata
import os
import threading
import subprocess
import sys
import time
import webbrowser
import concurrent.futures
#from queue import Queue
from pathlib import Path
#global thread lock used to prevent race condition when writing to the file
file_lock = threading.Lock()
api_semaphore = threading.Semaphore(10)  # semaphore to limit API calls
# make sure that meraki is installed by first declaring a list of external libraries required
required = {'meraki'}
# then get a list of installed packages
installed = {pkg.metadata['Name'] for pkg in importlib.metadata.distributions()}
# find what's missing by subtracting what's installed from what's required
missing = required - installed
# if anything is missing install it via pip
if missing:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', *missing])
# now that we can sure sure meraki is installed import the library
import meraki

def getSwitches(orgID):
    # Retrieve all switches in the organization.
    devices = dashboard.organizations.getOrganizationDevices(
        orgID)  # get all organization devices
    return [
        device for device in devices
        if device['productType'].startswith('switch')
    ]  

def getOutputDir():
     # Create output_files directory if it doesn't exist
    output_dir = os.path.join(Path.home(), "Documents", "MerakiPhoneOutput")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir

def getOrgID():
    # Get the orgID from meraki dashboard
    orgs = dashboard.organizations.getOrganizations()  # get organizations list
    return orgs[0]['id'] if orgs else None  # return the ID from that list

def getPhonesOnSwitch(serial, switchName, output_filename):
    try:
        # Use the semaphore to control API call rate
        with api_semaphore:
            # Slight delay to help distribute API calls
            time.sleep(0.1)
            # Retrieve all devices from the switch
            response = dashboard.devices.getDeviceClients(serial)
            # Filter only phone devices (names starting with SEP)
            phoneDevices = [client for client in response if client.get('description') and client['description'].startswith('SEP')]
            # Sort phone devices by switchport
            sortedPhoneDevices = sorted(phoneDevices, key=lambda client: int(client.get('switchport')) if client.get('switchport') and client.get('switchport').isdigit() else float('inf'))
            # Thread-safe file writing
            with file_lock:
                with open(output_filename, "a") as file:
                    file.write(f"Phones on switch {switchName}:\n")
                    for client in sortedPhoneDevices:
                        file.write(f"Phone: {client.get('description')}, " # write it's name, mac, ip, port, and vlan
                                   f"Port: {client.get('switchport')}, "
                                   f"MAC: {client.get('mac', 'N/A')}, "
                                   f"IP: {client.get('ip', 'N/A')},"
                                   f" VLAN: {client.get('vlan', 'N/A')}\n")
                    file.write("\n")  # Add a newline for readability
            
            print(f"Processed phones on switch {switchName}. Total phones found: {len(sortedPhoneDevices)}")
    
    except meraki.APIError as e:
        print(f"Meraki API Error on switch {switchName}: {e}")
    except Exception as e:
        print(f"Error processing switch {switchName}: {e}")

def main():
    KEY_FILE = "vlanScriptKey.txt"
    url = "https://documentation.meraki.com/General_Administration/Other_Topics/Cisco_Meraki_Dashboard_API"
    while True:
        if not os.path.exists(KEY_FILE):
            open(KEY_FILE, "w").close()
            # introductory message displayed at the start of the script if the user's API key is not set
            # after this runs it will verify the API key is valid and the dashboard connected successfully
            print("-------------------------------------------------------------------------")
            print("Welcome, this script will find all phones connected to switches on Meraki, to run this you need a Meraki API key")
            print("Paste your API key into the file vlanScriptkey.txt to continue")
            entry = input("Enter a ? to get instructions on how to get your API key\nOr press enter to continue once it's set:")
            if entry == '?':
                webbrowser.open(url)
                continue
            else:
                with open(KEY_FILE, "r") as file:
                    API_KEY = file.read().strip()
                    break
        else:
            with open(KEY_FILE, "r") as file:
                API_KEY = file.read().strip()
                break
            
        if not API_KEY: # if there is no valid API key 
            print("No valid API Key, check vlanScriptKey.txt(should contain ONLY the API key)")
            os.remove(KEY_FILE)
            continue
        else:
            break
    
    global dashboard 
    global orgID
    try:
        dashboard = meraki.DashboardAPI(API_KEY, output_log=False,print_console=False,suppress_logging=True)  # open dashboard
    except Exception as e:
        print ("Failed to connect with dashboard, ending script...")
        return # display an error and end the script
    try:
        orgID = getOrgID()  # get the orgID
    except Exception as e:
        print("Unable to get org ID, ending script...")
        return
    switches = getSwitches(orgID) # get all switches and store them in a list   
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Get output directory
    output_dir = getOutputDir()
    # Create output filename
    output_filename = os.path.join(output_dir, f"meraki_phones_{run_timestamp}.txt")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Create a list to hold our futures
        futures = []
        
        # Submit jobs for each switch
        for switch in switches:
            serial = switch['serial']
            switchName = switch['name']
            print(f"Queuing phones retrieval for switch {switchName}...")
            # Submit the task to the thread pool
            future = executor.submit(
                getPhonesOnSwitch, 
                serial, 
                switchName,  
                output_filename
            )
            futures.append(future)
        
        # Wait for all futures to complete
        concurrent.futures.wait(futures)
    
    print(f"All switches processed. Output saved to {output_filename}")
      
if __name__ == "__main__":
    main()