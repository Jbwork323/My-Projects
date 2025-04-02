import importlib.metadata
import os
import logging
import csv
import threading
import subprocess
import sys
import re
import time
import webbrowser

#global thread lock used to prevent race condition when writing rollback data
lock = threading.Lock()
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
import meraki # type: ignore

#-------------------------------------------------------------------------------------
#USER INPUT FUNCTIONS
def getVlansFromUser():
    # gets a voice VLAN and vlan from the user while offering the chance to enter ? to learn more about the input field
    enteredVlan = ""
    enteredVoiceVlan = ""
    # while loop used to jump back to if the user chooses to display options
    while True:
        enteredVlan = input("Enter the VLAN Id that you want to change TO(leave blank if none): ")
        if enteredVlan == '?':
            dispOptions("This field takes a VLAN ID entered as an integer, leave the field blank if not changing the VLAN",
                        "leave both this and the voiceVLAN field empty to abort operation")
            continue
        break
    # while loop used to jump back to if the user chooses to display options
    while True:
        enteredVoiceVlan = input("Enter the Voice VLAN ID that you want to change TO(leave blank if none):")
        if enteredVoiceVlan == '?':
            dispOptions("This field takes a VLAN ID entered as an integer, leave the field blank if not changing the VLAN",
                        "leave both this and the voiceVLAN field empty to abort operation")
            continue 
        return enteredVlan, enteredVoiceVlan

def getSinglePortFromUser():
    """ gets a single port from the user while offering the option to enter ? to learn more about the field"""
    # while loop used to jump back to if the user chooses to display options
    while True:
        enteredPort = input("Enter the port you want to change: ")
        if enteredPort == '?':
            dispOptions("This input field takes a port number, entered as a integer",
                    "leave this or the next field blank to abort the operation")
            continue
        return enteredPort

def getMultiPortsFromUser():
    """ gets a list of ports from the user while letting them enter ? at any time to learn more about that input field """
    while True:
        makeMenu("CHANGE MULTIPLE PORTS MENU","1) Specify a range of ports to change", "2) Specify a list of ports to change","?) Display options", "X) Go back")
        selection=input("Enter your selection: ")
        # option 1 allows the user to enter a range of ports like 1-10 then populate that range with everything in between
        if selection == '1':
            while True:
                portStart = input("Enter the lower limit of ports to change: ")
                if portStart == '?':
                    dispOptions("This input field takes an integer which defines the start of a list",
                    "After entry of the start and end the list will be filled with numbers start-end")
                    continue
                break
            while True:
                portEnd = input("Enter the upper limit of ports to change: ")
                if portEnd == '?':
                    dispOptions("This input field takes an integer which defines the start of a list",
                    "After entry of the start and end the list will be filled with numbers start-end")
                    continue
                break
            if not portStart or not portEnd:
                print("Invalid port selections")
                return
            try:
                portList = list(range(int(portStart),int(portEnd)+1))           # populate a port list with ports in the range specied by the user
                return portList
            except Exception as e:
                    print("Invalid entries")

        elif selection == '2':
            # option 2 allows the users to enter a comma seperated list of ports
            while True:
                    enteredList = input("Enter a COMMA SEPERATED list of port numbers: ")
                    if enteredList == '?':
                        dispOptions("This input field takes a comma seperated list of integers",
                        "if you mistakenly forget a comma you must remember to abort the operation")
                        continue
                    portList = enteredList.split(',')
                    return portList
        elif selection == '?':
            dispOptions("1 - menu item 1", "2- menu item 2", "? - Display Options", "X - Go Back")
            continue
        elif selection == 'X' or selection == 'x':
            return
        else:
            print("Invalid Selection")
            continue


def getSerialFromUser(switches):
    """ gets a switch serial number/ name from the user, if a serial is entered it will convert to upper
     then grab the switch's name, if given a name it will attempt to convert into upper if possible
     then grab the serial associated with that name, returning both"""
    while True: # label used to jump to if the user enters a ? to display options
        serialNum =input("Enter the switch's name or serial: ")
        if serialNum == '?':
            dispOptions("This input field takes either a switch's name or serial number",
            "Serial Numbers are non case sensitive and you may enter names such as TR1450-xxxx as non case sensitive",
            "However a name such as core switch must be entered EXACTLY as you see it on Meraki dashboard")
            continue
        switchName = ""
        # check if what they entered is a serial or name 
        if not is_serial_number(serialNum):
            # then try to convert it to uppercase if possible 
            if not switchNameCase(serialNum):   # if the switch's name isn't something case sensitive like Access Switch or Core Switch
                serialNum=serialNum.upper()     # we can safely convert it to upper case
            # now that we have confirmed the switch's name is in the correct format we can grab the serial number using the name
            switchName = serialNum
            serialNum = getSerialByName(switches, serialNum)
        # else if we know they entered a serial number we can convert it to uppercase and grab the switch's name
        else:
            serialNum = serialNum.upper()
            switchName =getNameBySerial(switches,serialNum)
        
        return serialNum, switchName

def getListOfSerialsFromUser(switches):
    """ gets a list of serial numbers/names entered by the user, converting to upper and getting the associated 
     name/serial when applicable"""
    serialsList = []
    namesList =[]
    counter = 1
    # while loop used to jump back to if the user chooses to display options
    while True: 
                print("Enter switch", counter, end ="" )
                counter+=1
                while True:
                    entry = input("'s name or serial(enter X or leave blank to stop):")
                    if entry == '?':
                        dispOptions("This input field will take mutiple switch's names or serial numbers one at a time",
                        "Serial Numbers are non case sensitive and you may enter names such as TR1450-xxxx as non case sensitive",
                        "However a name such as core switch must be entered EXACTLY as you see it on Meraki dashboard",
                        "Once you are done entering switches, enter X or x or leave the field blank to continue")
                        continue
                    break
                # we allow the user to stop entering switches by entering an X or by leaving the field blank
                if entry.lower() == 'x' or not entry:
                    break
                else:  
                    # now that we have the entry we can check if it's a serial or name
                    # then convert it to uppercase and grab the associated name/serial
                    if not is_serial_number(entry):
                        if not switchNameCase(entry):
                            entry = entry.upper()
                        switchName = entry
                        entry = getSerialByName(switches, entry)
                        
                    else:
                        entry = entry.upper()
                        switchName = getNameBySerial(switches, entry)
                    serialsList.append(entry)
                    namesList.append(switchName)
                    continue
    return serialsList, namesList
#---------------------------------------------------------------------------------------

#---------------------------------------------------------------------------------------
# UTILITY FUNCTIONS
def removeChanges(changeList,changeType,secondList = []):
        """removes an entry from the changelog when a rollback is executed"""
        print("Enter the index of the",changeType, "you want to remove(starting at 1)",end="")
        index = int(input(":"))
        index -= 1      # dec the index because lists start at 0 in python
        try:
            removed = changeList.pop(index)
            print("Removed entry", removed)
            if secondList:
                secondList.pop(index)
            return
        except Exception as e:
            print(e)
            print("Invalid input")
            return
        
def dispOptions(*args):
    """ basically the same as make menu but makes the user press enter before continuing
 takes in a varaidic amount of string arguments"""
    makeMenu(*args)
    input("Press enter to continue")

def getSerialByName(switches, switchName):
        """ given a switch's name this function retunrs the switch's serial number"""
        return next((switch['serial'] for switch in switches if switch['name'].startswith(switchName)), None)
        # return serial number as string

def getNameBySerial(switches, switchSerial):
    """Get a switch's name given its serial number."""
    return next((switch['name'] for switch in switches if switch['serial'] == switchSerial), None)

# checks if the user entered a serial number or not
def is_serial_number(entry):
    """Check if what was entered by the user is name or a serial number using a regex"""
    serial_pattern = r"^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$"
    return bool(re.fullmatch(serial_pattern, entry))

# this should match switch names like Core Switch or Access Switch while not matching names like TR1450-12XX
def switchNameCase(name):
    """determine whether a switch's name can be converted into uppercase
    for example a switch named TR1450 can be while a switch called Access Switch 1 can't"""
    namePattern = r"^[A-Z][a-z]*\s[A-Z][a-z]*\s\d+$"                                                
    return bool(re.fullmatch(namePattern, name))

def getOrgID():
    """# Get the orgID from meraki dashboard"""
    orgs = dashboard.organizations.getOrganizations()  # get organizations list
    return orgs[0]['id'] if orgs else None  # return the ID from that list

def makeMenu(menuTitle, *args):
    """takes a variadic amount of string arguments and a title to display a menu"""
    print("-------------------------------------------------------------------")
    print(menuTitle)
    for arg in args:
        print(arg)
#---------------------------------------------------------------------------------------

#---------------------------------------------------------------------------------------
# LOGGING FUNCTIONS
""" Configure logging"""
logging.basicConfig(filename="vlanChanges.log", level=logging.INFO, format='%(asctime)s - %(message)s')

def clearVlanLog():
    """Clear the contents of the VLAN changes log file using logging library."""
    with open("vlanChanges.log", 'w') as logFile:
        logFile.truncate()
   
    print("VLAN changes log cleared.")

def logAction(action = "", switchSerial=0, portId=0, vlan=0, voiceVlan=0):
    """Log VLAN changes to a file.
    change log message to be more reusable"""
    log_message = f"{action} - Switch: {switchSerial}, Port: {portId}, VLAN: {vlan}, Voice VLAN: {voiceVlan}"
    logging.info(log_message)
#----------------------------------------------------------------------------------------

#---------------------------------------------------------------------------------------
# BULK SWITCH VLAN CHANGE OPERATIONS

def bulkChangePortVlan(switchSerial, switchName, portList, vlanId, voiceVlanId):
    """ Divide the portList into equal parts for each thread"""
    # worker function to be called by each thread that performs the changeVlan operations
    def worker(portSubList, failedPorts):
        for portNumber in portSubList:
            if not changeVlan( portNumber, vlanId, voiceVlanId, "bulk",False, switchSerial,switchName):
                print("Failed operation on port ", portNumber)
                failedPorts.append(portNumber) # if any ports fail append them to a list so we can only display successful ones later
            print(".", end="")

    num_threads = 4  # max num of threads is 4 to avoid exceeding rate limit
    portList_chunks = [portList[i::num_threads] for i in range(num_threads)]
    threads = []
    failedPorts = []
    # for each chunk (should be 4) create a thread that will change the vlans on ports in that chunk
    for chunk in portList_chunks:
        thread = threading.Thread(target=worker, args=(chunk, failedPorts))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    
    print(f"\nSuccessfully updated VLAN settings for ports {list(set(portList) - set(failedPorts))} on switch {switchName}.")
    # Subtract list of failed port operations from the whole list to display which ports were successful

def changeOnePortMultSwitches(switches, serialsList = [], namesList =[]):
            """Changes a single port across multiple switches in defined by the user"""
            threads = []
            max_threads = 4
            # only allow 4 threads to avoid hitting rate limit
            if not serialsList:
                serialsList, namesList = getListOfSerialsFromUser(switches)
            enteredPort = getSinglePortFromUser()
            enteredVlan,enteredVoiceVlan = getVlansFromUser()
            if not enteredPort or (not enteredVlan and not enteredVoiceVlan): 
                print("Invalid Input")
                return
            # ask for confirmation or let them remove individual changes
            while True:
                print("Switches", namesList, "will have ports", enteredPort, "changed to VLAN", enteredVlan, "and voiceVLAN", enteredVoiceVlan)
                choice=input("Continue with the operation?(Y/N):")
                if choice.lower() !='y':
                    choice = input("Remove individual changes?:(Y/N)")
                    if choice.lower() == 'y':
                        removeChanges(serialsList,"Switch",namesList)
                        continue
                    print("Operation Cancelled")
                    return serialsList, namesList
                if len(serialsList) <= 0:
                    print("No entries left in list")
                    return serialsList, namesList
                break
            try:
                # define a worker function that will be called by each thread to change the vlans on the ports
                def worker(switch_chunk):
                    for serial in switch_chunk:
                        changeVlan(enteredPort, enteredVlan, enteredVoiceVlan,"bulk", False, serial)
                        print(".", end="")
                        time.sleep(0.1)  # Add delay to prevent rate limiting
                
                switch_chunks = [serialsList[i::max_threads] for i in range(max_threads)]
            # create a thread to operate on each chunk
                for chunk in switch_chunks:
                    thread = threading.Thread(target=worker, args=(chunk,))
                    threads.append(thread)
                    thread.start()
                for thread in threads:
                    thread.join()
                
            except Exception as e:
                    print("Invalid entries")
                    return
            # then display that the operation is completed and restart the loop 
            print("Successfully changed port", enteredPort, "to VLAN", enteredVlan,"and voice vlan", enteredVoiceVlan, "on switches ",namesList)
            return serialsList, namesList

def changeMultPortsOneSwitch(switches, serialNum ="",switchName=""):
        """Changes a list of ports given by the user on one single switch"""
        while True:
                portList = getMultiPortsFromUser()
                if not portList:
                    return
                if not serialNum:
                    serialNum, switchName = getSerialFromUser(switches)
                try:
                    enteredVlan, enteredVoiceVlan = getVlansFromUser()
                    if not portList or not serialNum or (not enteredVlan and not enteredVoiceVlan): 
                        print("Invalid Input")
                        return
                    # let user remove indivudual changes if they want
                    while True:
                        print("Switch", switchName, "will have ports", portList, "changed to VLAN", enteredVlan, "and voiceVLAN", enteredVoiceVlan)
                        choice=input("Continue with the operation?(Y/N):")
                        if choice.lower() != 'y':
                            choice = input("Remove individual changes?:(Y/N)")
                            if choice.lower() == 'y':
                                removeChanges(portList,"port")
                                continue
                            print("Operation Cancelled")
                            return serialNum, switchName
                        # check if they removed every change which invalided the operation
                        if len(portList) <= 0:
                            print("No entries left in list")
                            return serialNum, switchName
                       
                        else:
                            bulkChangePortVlan(serialNum, switchName, portList, enteredVlan,enteredVoiceVlan)   # if they confirm to change the vlans call the bulk change function
                            return serialNum, switchName
              
                except Exception as e:
                    print("Invalid entries")
                    return serialNum, switchName

def changeMultPortsMultSwitches(switches, serialsList = [], namesList =[]):
    """Change a list of ports across a list of switches supplied by the user"""
    threads = []
    while True:
                portList = getMultiPortsFromUser()
                if not serialsList:
                    serialsList, namesList = getListOfSerialsFromUser(switches)
                try:
                    enteredVlan = input("What VLAN do you want to change the ports to?(leave blank if none): ")
                    enteredVoiceVlan = input("What voice VLAN do you want to change the ports to(leave blank if none): ")
                    if not portList or not serialsList: 
                        print("Invalid Input")
                        return
                    # allow them to cancel individual changes or continue with them
                    while True:
                        print("Switches", namesList, "will have ports", portList, "changed to VLAN", enteredVlan, "and voiceVLAN", enteredVoiceVlan)
                        choice=input("Continue with the operation?(Y/N):")
                        if choice.lower() != 'y':
                            choice = input("Remove individual changes?:(Y/N)")
                            if choice.lower() == 'y':
                                entry = input("Enter a 1 to remove a switch or 2 to remove a port:")
                                if entry == '1':
                                    removeChanges(serialsList,"Switch",namesList)
                                elif entry == '2':
                                    removeChanges(portList,"port")
                                else:
                                    print("Invalid choice")
                                continue
                            print("Operation Cancelled")
                            return serialsList, namesList
                        if len(serialsList) <= 0:
                            print("No entries left in list")
                            return serialsList, namesList
                        break
                    
                  
                    for serial, switchName in zip(serialsList, namesList):
                        bulkChangePortVlan(serial,switchName, portList, enteredVlan, enteredVoiceVlan)
                    return serialsList, namesList
                except Exception as e:
                    print("Invalid entries")
                    return

def changePortAllSwitches(switches):
    """change one single port on every single switch in the organization"""
    serialsList = []
    threads = []
    max_threads = 4 # only allow 4 threads to avoid hitting rate limit
    while True:
        try:
            print("This operation will change a port VLAN on EVERY SWITCH in your organization")
            entry = input("Continue with the operation?(Y/N): ")
            if entry.lower() != 'y':
                    return
            enteredPort = getSinglePortFromUser()  
            enteredVlan, enteredVoiceVlan = getVlansFromUser()                  
            entry = input("Continue with the operation?(Y/N): ")
            if entry.lower() != 'y':
                    return
            if not enteredPort or (not enteredVlan and not enteredVoiceVlan): 
                        print("Invalid Input")
                        return
            # to avoid hitting rate limit I divide the list of switches into four then use 4 threads
            for switch in switches:
                serialsList.append(switch["serial"])

            def worker(switch_chunk):
                for serial in switch_chunk:
                    changeVlan(enteredPort, enteredVlan, enteredVoiceVlan,"bulk", False, serial)
                    print(".", end="")
                    time.sleep(0.1)  # Add delay to prevent rate limiting

            # divide switch list into 4 chunks then make 4 threads to perform the operations
            switch_chunks = [serialsList[i::max_threads] for i in range(max_threads)]
            for chunk in switch_chunks:
                thread = threading.Thread(target=worker, args=(chunk,))
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()
            print("Operation finished, check logs to ensure all ports were successful")
            return
        except Exception as e:
                    print("Invalid entries")
                    return
                
#---------------------------------------------------------------------------------------

#----------------------------------------------------------------------------------------
# SINGLE SWITCH VLAN CHANGE OPERATIONS

def changeVlan(portNumber, vlanId, voiceVlanId, operationType = "single", rollback = False, switchSerial= "",switchName=""):
   """change the vlan of an individual port on a switch"""
   try:
        # Get current port settings before making changes
        currentSettings = dashboard.switch.getDeviceSwitchPort(serial=switchSerial, portId=portNumber)
        previousVlan = currentSettings.get("vlan")
        previousVoiceVlan = currentSettings.get("voiceVlan")
        
        # Save rollback data
        if not rollback:
            saveRollbackData(operationType, switchSerial, portNumber, previousVlan, previousVoiceVlan)
            
        # Update VLAN settings
        if not vlanId:
            vlanId = previousVlan
        if not voiceVlanId:
            voiceVlanId = previousVoiceVlan
    
        dashboard.switch.updateDeviceSwitchPort(
            serial=switchSerial,
            portId=portNumber,
            vlan = vlanId,
            voicevlan = previousVoiceVlan
        )
        if not rollback:
            logAction("Changed port VLAN", switchSerial, portNumber, vlanId, voiceVlanId)
        if not rollback and operationType == "single":
            print("Successfully changed Switch",switchName, "port", portNumber, "to VLAN", vlanId, "and voice VLAN", voiceVlanId)
        return switchSerial, switchName
   
   except Exception as e:
        print(f"Failed Operation: {e}")
        return False
   
def swapPorts(port1, port2, rollBack = False,switchSerial= "",switchName=""):
    """Swap VLAN assignments between two ports on a switch."""
    try:
        
        ports = dashboard.switch.getDeviceSwitchPorts(switchSerial) # get all ports on the switch
        port1Data = next((port for port in ports if port["portId"] == port1), None) # populate port1Data with the right port
        port2Data = next((port for port in ports if port["portId"] == port2), None) # do the same with port 2

        if not port1Data or not port2Data:  # if they entered an invalid port then print that
            print("One or both ports not found.")
            return
        
        if not rollBack: # if we're not performing a rollback then save the rollback data
            saveRollbackData('3',switchSerial, port1, port1Data.get("vlan"), port1Data.get("voiceVlan"))    #save the rollback data to the csv
            saveRollbackData('3',switchSerial, port2, port2Data.get("vlan"), port2Data.get("voiceVlan"))
        
        # update port 1 with port 2's data
        dashboard.switch.updateDeviceSwitchPort(switchSerial, port1, vlan=port2Data.get("vlan"), voiceVlan=port2Data.get("voiceVlan"))
        # then update port 2 with port 1's data
        dashboard.switch.updateDeviceSwitchPort(switchSerial, port2, vlan=port1Data.get("vlan"), voiceVlan=port1Data.get("voiceVlan"))
        
        # log both actions
        logAction("Ports Swapped", switchSerial, port1, port2Data.get("vlan"), port2Data.get("voiceVlan"))
        logAction("Ports Swapped", switchSerial, port2, port1Data.get("vlan"), port1Data.get("voiceVlan"))
        print(f"Successfully swapped ports {port1} and {port2} on {switchName}")
        return switchSerial, switchName
        # if they entered a bad switch serial catch the error then return without doing anything
    except Exception as e:
        print(f"Error swapping ports on {switchSerial}: {e}")

def changeVlanPortsMenu(switches): # this menu allows for the changing of ports on vlans and switches
    """The primary menu for changing vlans based on port"""
    switchSerial = ""
    switchName = ""
    serialsList =[]
    namesList = []
    while True:
        try:
            makeMenu("CHANGE PORT VLAN BY PORT MENU","1) Swap two port's VLANS on the SAME switch","2) Change an individual port's VLAN","3) Change multiple port vlans on a single switch",
            "4) Change one port VLAN on multiple switches", "5) Change multiple port VLANS across multiple switches",
            "6) Change a port VLAN on ALL switches in your organization","?) View options", "X) Return to main menu")
            selection = input("Enter your selection: ")
            
            if selection == '1': # option A is to swap two ports on a switch
                while True:
                    print("-------------------------------------------------------------------")
                    print("This allows you swap what VLANs two ports are on")
                    try:
                        # prompt the user for the switch's serial and what ports they want to swap
                        if not switchSerial:
                            switchSerial, switchName = getSerialFromUser(switches)
                        port1 = input("Enter the first port: ")
                        if port1 == '?':
                            dispOptions("This input field takes a port number, entered as a integer",
                            "leave this or the next field blank to abort the operation")
                            continue
                        while True:
                            port2 = input("Enter the second port: ")
                            if port2 == '?':
                                dispOptions("This input field takes a port number, entered as a integer",
                                "leave this or the next field blank to abort the operation")
                                continue
                            else:
                                break
                        if not port1 or not port2 or not switchSerial: 
                            print("Invalid Input")
                            return
                        print("Switch ", switchName, "will have ports", port1, "and", port2, " swapped.")
                        # ask for confirmation or let them remove individual changes
                        selection = input("Continue with this operation?(Y/N): ")
                        if selection == 'Y' or selection == 'y':
                            switchSerial, switchName = swapPorts(port1, port2,False,switchSerial,switchName)
                            break
                        elif selection == '?':
                            dispOptions("This input field takes a Y or y to confirm then perform the operation",
                            "enter any other key to cancel the operation")
                            continue
                        else:
                            print("Operation cancelled")
                    except Exception as e:
                        print("Invalid entries")
                        continue
            elif selection == '2':
                    try:
                        print("This function allows you to change both the vlan and voice vlan of a port.")
                        # if the serial is not already set then prompt the user for the serial
                        if not switchSerial:
                            switchSerial, switchName = getSerialFromUser(switches)
                        enteredPort = getSinglePortFromUser()
                        enteredVlan, enteredVoiceVlan = getVlansFromUser()
                        # check if they entered valid input or not
                        if not switchSerial or not enteredPort or (not enteredVlan and not enteredVoiceVlan):
                            print("Invalid input")
                            return
                        print("Switch ", switchName, "will have port", enteredPort, "changed to vlan", enteredVlan,"and voiceVLAN", enteredVoiceVlan)
                        selection = input("Continue with this operation?(Y/N):")
                        while True:
                            if selection == 'Y' or selection == 'y':
                                if not enteredPort or not switchSerial or (not enteredVlan and not enteredVoiceVlan): 
                                    print("Invalid Input")
                                    return
                                switchSerial, switchName = changeVlan(enteredPort, enteredVlan,enteredVoiceVlan,"single",False, switchSerial, switchName)
                            elif selection == '?':
                                dispOptions("This field confirms whether you want to procede with the operation or not",
                                "press Y or y to confirm or anything else to cancel the operation")
                            else:
                                print("Operation cancelled")
                                break
                    except Exception as e:
                        print("Invalid entries")
                        continue
            elif selection == '3':            # option 3 is to change a range of ports on a single switch
                    switchSerial, switchName = changeMultPortsOneSwitch(switches, switchSerial, switchName)
            elif selection == '4':            # option 4 is to change multiple ports on one switch
                    serialsList, namesList = changeOnePortMultSwitches(switches, serialsList, namesList)
            elif selection == '5':            # option 5 is to change multiple ports on multiple switches
                    serialsList, namesList = changeMultPortsMultSwitches(switches, serialsList, namesList)
            elif selection == '6':            # option 6 is to change a single port on all switches
                    changePortAllSwitches(switches)
            elif selection == '?':            # allow the user to enter ? to see options
                    makeMenu("OPTIONS","1 - menu item 1","2 - menu item 2","3 - menu item 3","4 - menu item 4","5- menu item 5","6 - menu item 6","? - view options","X or x - exit menu")
                    input("Press enter to continue")
                    continue
            elif selection == 'X' or selection == 'x':
                    return
            else:
                print("Invalid selection")
                continue
            while True:
                if serialsList:
                    print("Continue operations on switches",namesList,"?(Y/N):")
                else: 
                    print("Continue operations on switch", switchName,"?(Y/N):")
                entry = input("")
                # ask if they want to continue operations on that switch or not
                if entry.lower() != 'y':
                    switchSerial = ""
                    switchName = ""
                    serialsList = []
                    namesList = []
                break
        except Exception as e:
                ("Invalid entries")
                continue
      
#----------------------------------------------------------------------------------------

#---------------------------------------------------------------------------------------
# ROLLBACK FUNCTIONS
ROLLBACK_FILE = "rollback_data.csv"
def clearRollbackData():
    """Clear the contents of the rollback data CSV file using csv library."""
    with open(ROLLBACK_FILE, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([])
    print("Rollback data cleared.")

def getNextRollbackId():
    """Get the next available rollback ID."""
    try:
        with open(ROLLBACK_FILE, mode='r') as file:
            reader = csv.reader(file)
            rollbackData = list(reader)
            if not rollbackData:
                return 1  # Start with ID 1 if no data exists
            last_id = int(rollbackData[-1][0])
            return last_id + 1
    except FileNotFoundError:
        return 1  # Start with ID 1 if file does not exist
    
def removeRollbackEntryById(unique_id):
    """Remove the rollback entry matching the unique ID from the CSV file."""
    with lock:
        try:
            with open(ROLLBACK_FILE, mode='r') as file:
                reader = csv.reader(file)
                rollbackData = list(reader)  # Read all rows into memory
            # Filter out the entry with the matching unique ID
            rollbackData = [row for row in rollbackData if row[0] != unique_id]
            # Write back the filtered data
            with open(ROLLBACK_FILE, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerows(rollbackData)  # Write remaining data

        except FileNotFoundError:
            pass  # Do nothing if file is missing

# saves rollback data to a CSV file saves serial port# vlan id and voice vlan ID, called by changeVLAN
def saveRollbackData(operationType, switchSerial, portId, vlan, voiceVlan):
    """Save rollback data to a CSV file with a unique ID."""
    unique_id = getNextRollbackId() 
    with lock: 
        with open(ROLLBACK_FILE, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([unique_id, operationType, switchSerial, portId, vlan, voiceVlan])

# loads the saved rollback data from the CSV file, called by rollbackChanges()
def loadRollbackDataById(unique_id):
    """Load rollback data from a CSV file by unique ID."""
    with lock:
        try:
            with open(ROLLBACK_FILE, mode='r') as file:
                reader = csv.reader(file)
                for row in reader:
                    if row and row[0] == str(unique_id):
                        return {
                            "unique_id": row[0],
                            "operationType": row[1],
                            "serial": row[2],
                            "port": row[3],
                            "vlan": int(row[4]),
                            "voiceVlan": int(row[5]) if row[5].isdigit() else None
                        }
        except FileNotFoundError:
            return None  # Return None if file is missing

    return None  # Return None if no matching entry is found
# operation type 1 = port VLAN change type 2 = bulk single switchport changes
def rollbackPortVlanById(unique_id, bulkRollback = False):
    """Rollback a port VLAN change by unique ID."""
    rollbackData = loadRollbackDataById(unique_id)
    # try to load rollback data, if not found return false
    if not rollbackData:
        print("No rollback data available for the provided ID.")
        return False
    try:
        changeVlan(rollbackData['port'], rollbackData['vlan'], rollbackData['voiceVlan'], "", True, rollbackData['serial'],)
        logAction("Rollback Port VLAN Executed", rollbackData['serial'], rollbackData['port'], rollbackData['vlan'], rollbackData['voiceVlan'])
        removeRollbackEntryById(unique_id)
    except Exception as e:
        print("Rollback with id", unique_id, "failed.")
        return False
    if not bulkRollback:
        print("Port VLAN rollback completed and processed rollback data removed.")
    return True

# operation type 2, single switch bulk port change
# multi threaded approach
def bulkRollbackPortVlan(listofIds):
    """ rollback recent port VLAN changes"""
    max_threads = 4
    threads = []
    def worker(idChunk):
        for id in idChunk:
            rollbackPortVlanById(id, True)
            print(".",end="")
    idChunks = [listofIds[i::max_threads] for i in range(max_threads)]
    
    for chunk in idChunks:
            thread = threading.Thread(target=worker, args=(chunk,))
            threads.append(thread)
            thread.start()
            
    for thread in threads:
        thread.join()
    print("Bulk Rollback Operation Finished")

# operation type 3 - port VLAN swap
def rollbackSwapById(unique_id1, unique_id2):
    """Rollback a port swap operation by restoring the original VLANs of two ports using their unique IDs."""
    rollbackEntry1 = loadRollbackDataById(unique_id1)
    rollbackEntry2 = loadRollbackDataById(unique_id2)

    if not rollbackEntry1 or not rollbackEntry2:
        print("Insufficient rollback data for port swap.")
        return

    # Swap ports back to their original VLAN assignments
    swapPorts(rollbackEntry1['port'], rollbackEntry2['port'], True,rollbackEntry1['serial'])

    # Log the rollback actions
    logAction("Rollback Swap Executed", rollbackEntry1['serial'], rollbackEntry1['port'], rollbackEntry1['vlan'], rollbackEntry1['voiceVlan'])
    logAction("Rollback Swap Executed", rollbackEntry2['serial'], rollbackEntry2['port'], rollbackEntry2['vlan'], rollbackEntry2['voiceVlan'])
    # remove rollback entries from the file
    removeRollbackEntryById(unique_id1)
    removeRollbackEntryById(unique_id2)
    print("Port swap rollback completed.")

def listRollbackEntries():
    """List all rollback entries with their unique IDs."""
    try:
        with open(ROLLBACK_FILE, mode='r') as file:
            reader = csv.reader(file)
            rollbackData = list(reader)  # Read all rows into memory
        if not rollbackData:
            print("No rollback entries found.")
            return
        print("Rollback Entries:")
        for row in rollbackData:
            print(f"ID: {row[0]}, Operation Type: {row[1]}, Switch Serial: {row[2]}, Port: {row[3]}, VLAN: {row[4]}, Voice VLAN: {row[5]}")

    except FileNotFoundError:
        print("No rollback entries found.")

# divided this into it's own menu from the rollback one because it was too big
def bulkRollbackMenu():
    """Menu that allows users to bulk rollback recent changes"""
    while True:
                makeMenu("BULK ROLLBACK MENU", "1) Use a comma seperated list of ID's", "2) Use a range of ID's","?) Display options","X) Go back")
                selection = input("Enter your selection: ")
                # option 1 allows the user to enter a comma seperated list of IDs, if any they enter are invalid they will be ignored
                if selection == '1':
                    while True:
                        entry = input("Enter a COMMA SEPERATED list of IDs: ")
                        if entry == '?':
                            dispOptions("This field takes a comma seperated list of unique IDs for a rollback change",
                            "To find these, go to the rollback_data.csv file or select to list it to the console")
                            continue
                        break
                    try:
                        idList = entry.split(',')
                    except Exception as e:
                        print("Invalid entries")
                        return
                    if not idList:
                        print("Invalid input")
                        continue
                    print("Changes with IDs", idList, "will be rolled back")
                    selection = input("Confirm Operation(Y/N): ")
                    if selection in('Y','y'):
                        bulkRollbackPortVlan(idList)
                    else:
                        continue  
                # operation 2 allows them to enter a range of ids which is then populated into a list
                elif selection == '2':
                    while True:
                        start = input("Enter the first ID in the range: ")
                        if start == '?':
                            dispOptions("This input field takes an integer which defines the start of a list",
                            "After entry of the start and end the list will be filled with numbers start-end")
                            continue
                        break
                    while True:
                        end = input("Enter the first ID in the range: ")
                        if end == '?':
                            dispOptions("This input field takes an integer which defines the start of a list",
                            "After entry of the start and end the list will be filled with numbers start-end")
                            continue
                        break
                    if not start or not end:
                        print("Invalid entries")
                        continue
                    try:
                        idList = list(map(str,range(int(start),int(end)+1)))           # populate a port list with ports in the range specied by the user
                    except Exception as e:
                        print("Invalid entries")
                        return
                    if not idList:
                        print("Invalid input")
                        continue
                    print("Changes with IDs", idList, "will be rolled back")
                    selection = input("Confirm Operation(Y/N): ")
                    if selection in('Y','y'):
                        bulkRollbackPortVlan(idList)
                    else:
                        continue
                elif selection == '?':
                    makeMenu("OPTIONS","1 - menu item 1","2 - menu item 2","3 - menu item 3","4 - menu item 4","? - view options","X or x - exit menu")
                    input("Press enter to continue")
                elif selection == 'X' or selection == 'x':
                    return

def rollbackMenu():
    """Display the rollback menu and handle user input for rollbacks."""
    while True:
        makeMenu("ROLLBACK MENU", "1) List rollback entries", "2) Rollback a port VLAN change by ID", "3) Rollback a port swap by IDs"
                 ,"4) Bulk rollback changes","?) View options","X) Cancel rollback operation")
        selection = input("Enter your selection: ")\
        # option 1 allows the user to list all the rollback entries in the file
        if selection == '1':
            listRollbackEntries()
        # option 2 allows the user to rollback a single port VLAN change by ID
        elif selection == '2':
            while True:
                unique_id = input("Enter the ID of the port VLAN change to rollback: ")
                if unique_id == '?':
                    dispOptions("This field take an ID for a rollback change entered as an integer",
                    "to find these, look at rollback_data.csv or select to list the entires in the console")
                    continue
                break
            if not unique_id:
                print("Invalid input")
                continue
            print("Change with ID", unique_id, "will be rolled back")
            selection = input("Confirm Operation(Y/N): ")
            if selection in('Y','y'):
                rollbackPortVlanById(unique_id)
            else:
                continue
        # option 3 allows the user to rollback a port swap operation by two unique IDs
        elif selection == '3':
            while True:
                unique_id1 = input("Enter the ID of the first port swap entry: ")
                if unique_id1 == '?':
                    dispOptions("This field take an ID for a rollback change entered as an integer",
                    "to find these, look at rollback_data.csv or select to list the entires in the console")
                    continue
                break
            while True:
                unique_id2 = input("Enter the ID of the second port swap entry: ")
                if unique_id2 == '?':
                    dispOptions("This field take an ID for a rollback change entered as an integer",
                    "to find these, look at rollback_data.csv or select to list the entires in the console")
                    continue
                break
            if not unique_id1 or not unique_id2:
                print("Invalid input")
                continue
            print("Changes with IDs", unique_id1,"and",unique_id2, "will be rolled back")
            selection = input("Confirm Operation(Y/N): ")
            if selection in('Y','y'):
                rollbackSwapById(unique_id1, unique_id2)
            else:
                continue
            # operation 4 opens the bulk rollback menu
        elif selection == '4':
                bulkRollbackMenu()
                
        elif selection == '?':
                makeMenu("OPTIONS","1 - menu item 1","2 - menu item 2","? - view options","X or x - exit menu")
                input("Press enter to continue")
        elif selection == 'X' or selection == 'x':
            return
        else:
            print("Invalid selection.")
#---------------------------------------------------------------------------------------

#--------------------------------------------------------------------------------------
# NETWORK INFO FUNCTIONS
def getSwitches():
    """Retrieve all switches in the organization."""
    devices = dashboard.organizations.getOrganizationDevices(
        orgID)  # get all organization devices
    return [
        device for device in devices
        if device['productType'].startswith('switch') 
    ]  # only return switches from response


#-------------------------------------------------------------------------------------
#INTRODUCTION 
def introduction():
    """Introduction function that handles getting the API key from the user if it isn't already set"""
    global KEY_FILE 
    KEY_FILE = "vlanScriptKey.txt"
    url = "https://documentation.meraki.com/General_Administration/Other_Topics/Cisco_Meraki_Dashboard_API"
    while True:
        if not os.path.exists(KEY_FILE):
            open(KEY_FILE, "w").close()
            # introductory message displayed at the start of the script
            # after this runs it will verofy the API key is valid and the dashboard connected successfully
            print("-------------------------------------------------------------------------")
            print("Welcome. This script uses the Meraki API to display and change the VLANs of ports on switches in your organization. It is designed to be used with the Meraki dashboard.")
            print("To use this script you must have a valid meraki API key, the script has created a file in the same directory titled vlanScriptKey.txt ")
            print("paste ONLY your Meraki API KEY into the file to continue OR if your key is already in the file, continue")
            entry = input("Enter a ? to get instructions on how to get your API key\nOr press enter to continue once it's set:")
            if entry == '?':
                try:
                    webbrowser.open(url)
                except webbrowser.Error as e:
                    print("From meraki API docs:\n To generate an API key, go to the My Profile page accessed via the avatar icon in the top right-hand corner of dashboard.")
                    print("Scroll down to the API Access section and click \"Generate new API key\"")
                    print("API keys and Webhooks can also be configured via the dedicated API & Webhooks Dashboard UI page. Navigate to  Organization → Configure → API & Webhooks.") 
                introduction()
                continue
            else:
                with open(KEY_FILE, "r") as file:
                    api_key = file.read().strip()
                return api_key
        else:
            with open(KEY_FILE, "r") as file:
                api_key = file.read().strip()
            return api_key

#-----------------------------------------------------------------------------------------
# CHANGE VLAN BY VLAN

def getSingleVlanFromUser():
    """Get a single VLAN or voice VLAN ID from the user, returns the ID and a bool saying
    whether it was a VLAN or voice VLAN"""
    while True:
        voiceBool = False # used to tell whether this a VLAN or voiceVLAN
        makeMenu("VLAN OR VOICE VLAN", "1) VLAN","2) Voice VLAN")
        entry = input("Enter your selection:")
        if entry == '1':
            vlanID = input("Enter the VLAN that you want to change FROM:")
        elif entry == '2':
            vlanID = input("Enter the Voice VLAN that you want to change FROM:")
            voiceBool = True
        else:
            print("Invalid selection")
            continue
        if vlanID == '?':
            dispOptions("This field takes a VLAN or Voice VLAN ID entered as an integer, to find all available VLAN ids in your org",
                        "use meraki dashboard or run the Meraki_Network_Info.py script to display them")
            continue
        else:
            return vlanID, voiceBool
        
def getPortsonVLAN(serial, vlanId, voiceBool):
    """Returns all ports on a specific VLAN or voice VLAN, using voiceBool to tell which it should be searching for"""
    ports = dashboard.switch.getDeviceSwitchPorts(serial)
    if not voiceBool:
        vlanPorts = [port["portId"] for port in ports if str(port.get("vlan")) == str(vlanId)]
    else:
        vlanPorts = [port["portId"] for port in ports if str(port.get("voiceVlan")) == str(vlanId)]
    return vlanPorts


def singleSwitchChangebyVLAN(switches, serial = "", switchName = ""):
            """Change all ports on VLAN on a single switch to a different VLAN"""
            if not serial:
                serial,switchName = getSerialFromUser(switches)
            vlanID, voiceBool = getSingleVlanFromUser()
            portList = getPortsonVLAN(serial,vlanID,voiceBool)
            print("On switch",switchName,"ports",portList,"are on VLAN",vlanID)
            vlanID2, voiceVlan = getVlansFromUser()
            print("On Switch",switchName,"ports",portList,"will be changed to VLAN",vlanID2)
            choice = input("Continue with the operation(Y/N):")
            if choice.lower() != 'y':
                print("Operation Cancelled")
                return
            bulkChangePortVlan(serial,switchName,portList,vlanID2,voiceVlan)
            return serial,switchName

def multiSwitchChangeByVLAN(switches, serialsList = [], namesList = []):
        """Change all ports on VLAN on multiple switches to a different VLAN"""
        portLists = []
        if not serialsList:
            serialsList,namesList = getListOfSerialsFromUser(switches)
        vlanID,voiceBool = getSingleVlanFromUser()
        vlanID2, voicevlan = getVlansFromUser()
        for serial in serialsList:
            portLists.append(getPortsonVLAN(serial,vlanID,voiceBool))
        while True:
            for name,portList in zip(namesList,portLists):
                print("On switch", name, "ports", portList, "will be changed to VLAN",vlanID2)
            choice = input("Continue with the operation(Y/N):")
            if choice.lower() !='y':
                            choice = input("Remove individual changes?:(Y/N)")
                            if choice.lower() == 'y':
                                removeChanges(serialsList,"Switch",namesList)
                                continue
                            else:
                                return serialsList, namesList
            for serial, name, portList in zip(serialsList, namesList,portLists):
                bulkChangePortVlan(serial,name,portList,vlanID2, voicevlan)
            return serialsList, namesList

def everySwitchChangeByVLAN(switches):
    """Change all ports on VLAN on every switch to a different VLAN"""
    portLists = []
    print("This operation will change port VLAN assignments on EVERY SWITCH in your organization")
    choice = input("Continue?(Y/N)")
    if choice.lower() != 'y':
        print("Operation cancelled")
        return
    vlanID,voiceBool = getSingleVlanFromUser()
    for switch in switches:
        portLists.append(getPortsonVLAN(switch['serial'],vlanID,voiceBool))
    vlanID2, voicevlan = getVlansFromUser()
    for switch, portList in zip(switches,portLists):
        bulkChangePortVlan(switch['serial'],switch['name'],portList,vlanID2, voicevlan)

def bulkChangeVlansbyVlanMenu(switches):
    """menu used to handle bulk VLAN change operations"""
    switchName = ""
    switchSerial = ""
    namesList = []
    serialsList = []
    while True:
        try:
            makeMenu("CHANGE VLANS BY VLAN MENU","1) Change port VLANs by VLAN on a single switch","2) Change port VLANs by VLAN on multiple switches"
                     ,"3) Change port VLANs by VLAN on every switch","?) Display options", "X) Go back")
            entry = input("Enter your selection: ")
            if entry == '1':
                switchSerial, switchName = singleSwitchChangebyVLAN(switches, switchName, switchSerial)
            elif entry == '2':
                serialsList, namesList = multiSwitchChangeByVLAN(switches, serialsList, namesList)
            elif entry == '3':
                everySwitchChangeByVLAN(switches)
            elif entry == '?':  
                dispOptions("1 - menu item 1", "2 - menu item 2", "3 - menu item 3", "? - display options","X - return to main menu")
                continue
            elif entry.lower() == 'x':
                return
            else:
                print("Invalid entry")
                continue

            while True:
                    if serialsList:
                        print("Continue operations on switches",namesList,"?(Y/N):")
                    else: 
                        print("Continue operations on switch", switchName,"?(Y/N):")
                    entry = input("")
                    if entry.lower() != 'y':
                        switchSerial = ""
                        switchName = ""
                        serialsList = []
                        namesList = []
                    break
        
        except Exception as e:
            print("Invalid entries", e)

#---------------------------------------------------------------------------------------------
# MAIN MENU
def menu(switches):
    """main menu that allows navigation to the other main functions of the script"""
    print("WELCOME TO THE MERAKI SWITCHPORT VLAN MANAGER")
    while True:
        makeMenu("MAIN MENU", "1) Change port VLAN Assignments by VLAN",
                "2) Change port VLAN Assignments by PORT",
                "3) Rollback Changes", "4) Clear generated files", "?) View options", "X) End script")
        choice = input("Enter your choice: ") 
        if choice == '1':           # choice 1 is for changing VLANs by VLAN
            bulkChangeVlansbyVlanMenu(switches)
        elif choice == '2':        # choice 2 allows the user to change VLANs by port
            changeVlanPortsMenu(switches)
            continue
        elif choice == '3':        # choice 3 allows the user to rollback changes
            rollbackMenu()
            continue
        elif choice == '4':        # choice E allows the user to clear out any files generated by the script
            makeMenu("CLEAR GENERATED FILES MENU", "1) Clear the vlanChanges.log file","2) Clear the rollback_data.csv file(ENSURE YOU DON'T NEED THIS DATA)",
                     "3) Clear both files(ENSURE YOU DON'T NEED THIS DATA)","X) Go Back")
            selection = input("Enter your choice: ")
            if selection == '1':            # option 1 clears the vlanChanges.log file
                clearVlanLog()
            elif selection == '2':          # option 2 clears the rollback_data.csv file
                clearRollbackData()
            elif selection == '3':          # option 3 clears both files
                clearVlanLog()
                clearRollbackData()
            elif selection.lower() == 'x':  # option X allows the user to return to the main menu
                continue
            else:
                print("Invalid entry")
            continue
        elif choice == '?':
                makeMenu("OPTIONS","1 - menu item 1","2 - menu item 2","3 - menu item 3","4 - menu item 4","5 - menu item 5","? - view options","X or x - exit menu")
                input("Press enter to continue")
        elif choice.lower() == 'x':        # choice X allows the user to end the script
            print("Exiting script.")
            sys.exit(0)  # Use sys.exit to end the script
        else:
            print("Invalid selection.")
        continue
#--------------------------------------------------------------------------------------------------

def main():
    global API_KEY
    while True:
        API_KEY = introduction()
        if not API_KEY: # if there is no valid API key   
            print("No valid API Key, check vlanScriptKey.txt(should contain ONLY the API key)")
            if os.path.exists(KEY_FILE): 
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
    switches = getSwitches() # get all switches and store them in a list   
    menu(switches)

if __name__ == "__main__":
    main()
