#!/usr/bin/env python

# call script with 2 arguments: <serialnumber> <accesscode>

import serial
import os
import time
import sys
from datetime import datetime


# globals
ser = serial.Serial()
maxtimeouts = 15  # number of times to try getting a response from seismo
interval = 1800  # number of seconds to wait between data checks/dumps
running = 0  # is the seismo in scan mode? 0 = no, 1 = yes
directory = "/home/pi/FTP/"  # directory to download events to
logfile = "log.txt"  # name of log file


try:
    serialnum = str(sys.argv[1])
    accesscode = str(sys.argv[2])
    logincmd = "key " + accesscode + "\r"


except:
    raise Exception(
        'Please call on script in the following manner: python <script> <serial> <ac>')


def timestamp():
    return datetime.strftime(datetime.now(), '%m-%d-%Y %H:%M:%S -')


def stopped():
    log("Seismo stopped commicating for some reason.")


def toggleDTR():
    # toggle DTR to 'wake-up' 3000 machine's serial port comms
    ser.setDTR(0)
    time.sleep(2)
    ser.setDTR(1)
    time.sleep(3)


def log(string):
    f = open(directory + logfile, 'a')
    f.write(timestamp() + " - " + string + '\n')
    f.close()
    print(string)


def prompt():
    ser.write('\r')
    a = ser.read(ser.inWaiting())
    timeout = 0
    while(a.find('>') == -1):
        if(timeout > maxtimeouts):
            log("Trouble commicating with siesmo.")
            return 0
        else:
            timeout += 1
            log(" Trying to get a prompt " + str(timeout) +
                " out of " + str(maxtimeouts))
            time.sleep(10)
            ser.write('\r')
            a = ser.read(ser.inWaiting())
    return 1


def init():
    # setup com port

    # some simple error handling here
    try:
        ser.port = "/dev/ttyUSB0"
    except:
        raise Exception('Could not use ttyUSB0 for comms')

    ser.baudrate = 9600

    # Check if there is a log file already...
    #  if true, it's all good... our log() will work
    #  if false, create one!
    if(os.path.isfile(directory + logfile)):
        print("Logfile present.")
    else:
        f = open(directory + logfile, 'w')
        f.close()
    log("Script started ----------------------------------")


def wakeup():
    # toggle DTR and listen for 'ATE0'   exit on successfully finding 'ATE0'
    ser.close()
    ser.open()
    a = ser.read(ser.inWaiting())
    log("Waiting for seismo to acknowledge...")
    timeout = 0
    while(a.find('ATE0') == -1):
        if(timeout > maxtimeouts):
            log(timestamp(
            ) + " - Seismo not responding. It could be busy, bad battery, or bad comm setup.")
            end()
            return
        else:
            timeout += 1
            toggleDTR()
            a = ser.read(ser.inWaiting())
    log("OK.")
    check()


def check():
    log("Checking seismo for new data...")
    ser.write('inf\r')
    time.sleep(2)
    a = ser.read(ser.inWaiting())
    if(a.find('[05.') != -1):
        # split returned string to find out how many events are on seismo
        b = a.split("(")
        c = b[1].split(",")
        log(c[0] + " values found.")
        if(int(c[0]) > 1):
            if(prompt()):
                login()
            else:
                stopped()
                start()
        else:
            log(" Just a template.")
            end()
    else:
        log("Incorrect firmware?")
        end()


def login():
    log("Logging into seismo...")
    ser.write(logincmd)
    time.sleep(2)
    a = ser.read(ser.inWaiting())
    if(a.find('OK') != -1):
        log("OK.")
        is_running()
    else:
        log("Incorrect response from seismo. Restarting comms.")
        start()


def is_running():
    global running
    log("Checking to see if seismo is currently scanning...")
    ser.write("lst\r")
    time.sleep(5)
    a = ser.read(ser.inWaiting())
    if(a.find('NOT STOPPED') != -1):
        log("Currently in scan mode. Halting...")
        running = 1
        b = prompt()
        if(b):
            ser.write("hlt\r\r")
            time.sleep(2)
            c = ser.read(ser.inWaiting())
            if(c.find('OK') != -1):
                log("Temporarily halted.")
                dump()
        else:
            stopped()
            start()
    else:
        running = 0
        log("Not in scan mode.")
        dump()


def dump():
    log("Transferring files...")
    try:
        os.system('sudo stty -F /dev/ttyUSB0 9600')
        os.chdir(directory)
    except:
        raise Exception('Could not connect ttyUSB0 to terminal')

    ser.write('xfr 0\r')

    try:
        os.system('rb --ymodem > /dev/ttyUSB0 < /dev/ttyUSB0')
    except:
        raise Exception('Problem recieving files with rb --ymodem')
    time.sleep(5)
    log("Transfer complete!")
    a = prompt()
    if(a):
        log("Clearing events downloaded from seismo..")
        ser.write("clr E\r")
        time.sleep(2)
        b = ser.read(ser.inWaiting())
        if (b.find('OK') != -1):
            log("Events cleared.")
    else:
        stopped()
        start()
    run()


def run():
    if(running == 1):
        log("Returning unit back to scan mode...")
        ser.write("run\r\r")
        time.sleep(5)
        b = ser.read(ser.inWaiting())
        if(b.find('OK') == -1):
            stopped()
            run()
        c = prompt()
        if(c == 0):
            stopped()
            end()
        log("Unit scanning.")
        end()


def end():
    log("Ending communications with seismo.")


# wakeup -> check -> prompt -> login -> is_running -> dump -> run -> wait -> wakeup
#
#
#

# main program loop
def start():
    while(1):
        wakeup()
        log("Waiting " + str(interval) + " seconds before next check.")
        time.sleep(interval)


# Actual first code to RUN
print timestamp(), "Script starting..."
init()
start()
