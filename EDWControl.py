import PySimpleGUI as sg
from pypylon import pylon
import cv2
import os
import time
from datetime import datetime
import json
from pymeasure.instruments.keithley import Keithley2450
import pyvisa
import sys


# Pyinstaller .\EDWControl.spec
# Note the importance of hooks for Keithley + importing some underscore modules manually

VERSION = 0.3
BUILD_DATE = '2022-08-16 12:30'
AUTHOR = 'Harmen Hoek'
GITHUB = 'github.com/harmenhoek/EDWControl'

'''

FIX:


git lfs uninstall
git add .\dist\EDWControl-0_2.exe
 

2022-08-11 Testing the delay
Recorded the screen with the external camera, where I printed the time continuously (py script in Prompt)
Compared the time in the image with the saved time in the filename
Differences are about 15-30ms (filename is ahead of actual, because grabbing happens afterwards).
Result is worse (-100ms) when the filename is determined after waiting for the grab result.
Thus the former method is implemented

'''

# sg.theme('BrownBlue')   # Add a touch of color
sg.theme('DarkAmber')   # Add a touch of color

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

icon_path = resource_path("EDWControl.ico")

def image_resize(image, width=None, height=None, inter=cv2.INTER_AREA):
    # initialize the dimensions of the image to be resized and
    # grab the image size
    dim = None
    (h, w) = image.shape[:2]

    # if both the width and height are None, then return the
    # original image
    if width is None and height is None:
        return image

    # check to see if the width is None
    if width is None:
        # calculate the ratio of the height and construct the
        # dimensions
        r = height / float(h)
        dim = (int(w * r), height)

    # otherwise, the height is None
    else:
        # calculate the ratio of the width and construct the
        # dimensions
        r = width / float(w)
        dim = (width, int(h * r))

    # resize the image
    resized = cv2.resize(image, dim, interpolation=inter)

    # return the resized image
    return resized



col1 = [
    [
        sg.T('Basler camera control', font='_ 14', justification='c', expand_x=True),
    ],
    [
        sg.Button('Start Camera', key='StartCamera'),
    ],
    [
        sg.HSeparator(),
    ],
    [
        sg.Text('Exposuretime [ms]'),
        sg.InputText(size=(10, 1), key='ExposureTime', disabled=True),
        sg.Button('Max', key='MaxExposureTime', disabled=True)
    ],
    [
        sg.Text('Gain'),
        sg.InputText(size=(10, 1), key='Gain', disabled=True)
    ],
    [
        sg.Button('Apply settings', key='ApplySettings', disabled=True),
    ],
    [
        sg.T('.tiff, no compression')
    ],
]


col2 = [
    [
        sg.Image(key="-IMAGE-", size=(400, 300))
    ],
]

output_row = [
    [
        sg.T('Output', font='_ 14', justification='c', expand_x=True),
    ],
    [
        sg.Output(s=(100, 15), key='outputbox'),
    ],
]

first_row = [
    [
        sg.T(f'Electrodewetting Control', font='_ 18', justification='c', expand_x=True),
    ],
    [
        sg.Text('Experiment name'),
        sg.InputText(size=(50, 1), key='ExperimentName', disabled=True)
    ],
    [
        sg.Text('Logging rate [Hz]'),
        sg.InputText(size=(10, 1), key='logging_rate')
    ],
    [
        sg.Text("Image Folder"),
        sg.In(size=(75, 1), enable_events=True, key="ExportFolder"),
        sg.FolderBrowse(),
    ],
    [
        sg.Button('Start image recording and logging', key='StartLogging', disabled=True),
    ],
    [
        sg.Button('Start voltage sweep', key='VoltageKeithley', disabled=True)
    ]
]

keithley_row = [
    [
        sg.T('Keithley2450 control', font='_ 14', justification='c', expand_x=True),
    ],
    [
        sg.Text('Device ID'),
        sg.InputText(size=(40, 1), key='KeithleyDeviceID', default_text="USB0::0x05E6::0x2450::04456958::INSTR"),
        sg.Button('Connect Keithley2450', key='StartKeithley'),
    ],
    [
        sg.Checkbox('Use front terminals', key='FrontTerminals')
    ],
    [
        sg.Text('Voltage range (comma seperate)'),
        sg.InputText(size=(50, 1), key='KeithleyVoltages', disabled=True),
    ],
    [
        sg.Text('Dwell times (comma seperate)'),
        sg.InputText(size=(50, 1), key='KeithleyDwellTimes', disabled=True),
    ],
]

layout = [
    [
        first_row
    ],
    [
        sg.HSeparator(),
    ],
    [
        sg.Column(col1, element_justification='c', vertical_alignment='top'),
        sg.VSeparator(),
        sg.Column(col2, element_justification='c')
    ],
    [
        sg.HSeparator(),
    ],
    [
        keithley_row
    ],
    [
        sg.HSeparator(),
    ],
    [
        output_row,
    ],
    [
        sg.Button('Help'),
        sg.Push(),
        sg.Button('Set settings as default'),
        sg.Button('Exit'),
    ],
[
        sg.T(f'{AUTHOR} | Version {VERSION} | Build {BUILD_DATE} | {GITHUB}', font='_ 8', justification='c', expand_x=True),
    ],

]



def updateImage(camera):
    camera.StartGrabbingMax(10000, pylon.GrabStrategy_LatestImageOnly)
    while camera.IsGrabbing():
        # Wait for an image and then retrieve it. A timeout of 5000 ms is used.
        grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

        converter = pylon.ImageFormatConverter()
        # converting to opencv bgr format
        converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

        # Image grabbed successfully?
        if grabResult.GrabSucceeded():

            image = converter.Convert(grabResult)
            img = image.GetArray()
            img = image_resize(img, width=400)
            imgbytes = cv2.imencode('.png', img)[1].tobytes()  # ditto

            window['-IMAGE-'].update(data=imgbytes)

        else:
            print("Error: ",
                  grabResult.ErrorCode)  # grabResult.ErrorDescription does not work properly in python could throw UnicodeDecodeError
        grabResult.Release()

        camera.StopGrabbing()


def SaveAsDefault():
    data = {
        'ExposureTime': window["ExposureTime"].get(),
        'Gain': window["Gain"].get(),
        'ExperimentName': window["ExperimentName"].get(),
        'KeithleyVoltages': window["KeithleyVoltages"].get(),
        'KeithleyDwellTimes': window["KeithleyDwellTimes"].get(),
        'FrontTerminals': window["FrontTerminals"].get(),
        'KeithleyDeviceID': window["KeithleyDeviceID"].get(),
        'logging_rate': window["logging_rate"].get(),
        'ExportFolder': window["ExportFolder"].get(),
    }
    with open('EDWControlSettings.json', 'w') as f:
        json.dump(data, f, indent=2)
        print(f"{datetime.now().strftime('%H:%M:%S')} OK        Settings saved as defaults to 'EDWControlSettings.json'.")

def SetInitialValues():
    print('----- Electrodewetting Control -----')
    print(f'by {AUTHOR}')
    print(f"Version: {VERSION} ({GITHUB})")
    print(f"Build date: {BUILD_DATE}")
    print('\n')

    try:
        with open('EDWControlSettings.json') as f:
            settings = json.load(f)
            window["ExposureTime"].update(settings['ExposureTime'])
            window["Gain"].update(settings['Gain'])
            window["ExperimentName"].update(settings['ExperimentName'])
            window["KeithleyVoltages"].update(settings['KeithleyVoltages'])
            window["KeithleyDwellTimes"].update(settings['KeithleyDwellTimes'])
            window["FrontTerminals"].update(settings['FrontTerminals'])
            window["KeithleyDeviceID"].update(settings['KeithleyDeviceID'])
            window["logging_rate"].update(settings['logging_rate'])
            window["ExportFolder"].update(settings['ExportFolder'])
            print(f"{datetime.now().strftime('%H:%M:%S')} OK        Default settings loaded from 'EDWControlSettings.json'.")
    except:
        print(f"{datetime.now().strftime('%H:%M:%S')} WARNING   No default settings found. Press 'Set settings as default' to create default settings.")


def updateCameraSetting(camera, settings):
    camera.ExposureTime.SetValue(settings['ExposureTime'])
    camera.Gain.SetValue(settings['Gain'])

settings = {
    'ExposureTime': 100,
    'Gain': 0,
}

window = sg.Window(f"Electrodewetting Control {VERSION}", layout, finalize=True, icon=icon_path)
SetInitialValues()

updateInterval = 1

cameraStarted = False
recording = False
keithleyStarted = False
keithleyRecording = False
keithleyRamp = False
currentVoltage = 0

loggingAll = False

outputFolder = window["ExportFolder"].get()

tUpdate = time.time()
tRecording = time.time()
tVoltagechangeKeithley = time.time()
while True:
    event, values = window.read(timeout=50)
    if event == "Exit" or event == sg.WIN_CLOSED:
        if loggingAll:
            print('Closing log file ...')
            f.close()
            print('Log file closed.')
        print('Closing program now. Bye!')
        break

    if event == "StartKeithley":
        if not keithleyStarted:
            print("Keithley2450Control program")
            print('Checking available devices ...')
            rm = pyvisa.ResourceManager()  # should use Keysight by default
            print(f"Found devices: {rm.list_resources()}. Needs device {values['KeithleyDeviceID']}")
            window.Refresh()
            try:
                keithley = Keithley2450(values['KeithleyDeviceID'])
                print('Connection successfull.')
                window.Refresh()
                keithley.reset()
                if values['FrontTerminals']:
                    keithley.use_front_terminals()
                keithley.measure_current()
                keithley.enable_source()
                window['VoltageKeithley'].Update(disabled=False)
                print('Keithley connected.')
                window.Refresh()
                if cameraStarted:
                    window['StartLogging'].Update(disabled=False)
            except:
                print("Unable to connect to the Keithley 2450.")
                window.Refresh()
                continue
            window['KeithleyVoltages'].Update(disabled=False)
            window['KeithleyDwellTimes'].Update(disabled=False)
            window['FrontTerminals'].Update(disabled=True)
            window['KeithleyDeviceID'].Update(disabled=True)
            keithleyStarted = True
        else:
            window['KeithleyVoltages'].Update(disabled=True)
            window['KeithleyDwellTimes'].Update(disabled=True)
            window['FrontTerminals'].Update(disabled=False)
            window['KeithleyDeviceID'].Update(disabled=False)
            keithleyStarted = False
            window['StartLogging'].Update(disabled=True)
            window['VoltageKeithley'].Update(disabled=True)
            print('Keithley disconnected.')
            window.Refresh()

    if event == 'VoltageKeithley':
        if not keithleyRamp:
            KeithleyVoltages = [float(x) for x in values['KeithleyVoltages'].split(',')]
            KeithleyDwellTimes = [float(x) for x in values['KeithleyDwellTimes'].split(',')]
            if len(KeithleyVoltages) is not len(KeithleyDwellTimes):
                print('The number of voltages should equal the number of dwell times.')
                continue
            window['KeithleyVoltages'].Update(disabled=False)
            window['KeithleyDwellTimes'].Update(disabled=False)
            window['VoltageKeithley'].Update('Stop voltage sweep')
            keithleyRamp = True
            keithleyDwellIdx = 0
            currentDwellTime = 0  # make sure we start immediately
            tVoltagechangeKeithley = time.time()
            print('Voltage sweep started')
        else:
            window['KeithleyVoltages'].Update(disabled=True)
            window['KeithleyDwellTimes'].Update(disabled=True)
            window['VoltageKeithley'].Update('Start voltage sweep')
            currentVoltage = 0
            keithleyRamp = False
            print('Voltage sweep stopped')

    if keithleyRamp and time.time() - tVoltagechangeKeithley > currentDwellTime:
        if keithleyDwellIdx > len(KeithleyVoltages):  # if this was already the last voltage, stop
            window['KeithleyVoltages'].Update(disabled=True)
            window['KeithleyDwellTimes'].Update(disabled=True)
            window['VoltageKeithley'].Update('Start voltage sweep')
            keithleyRamp = False
            currentVoltage = 0
            print('Voltage ramping ended')
        else:
            currentVoltage = KeithleyVoltages[keithleyDwellIdx]
            currentDwellTime = KeithleyDwellTimes[keithleyDwellIdx]
            print(f'Voltage set to {currentVoltage}V.')
            keithley.source_voltage = currentVoltage
            keithley.current
            tVoltagechangeKeithley = time.time()
            keithleyDwellIdx = keithleyDwellIdx + 1

    if event == "ExportFolder":
        outputFolder = values["ExportFolder"]
        print(f"Folder {outputFolder} selected.")

    if event == "ApplySettings" and cameraStarted:
        print(f"Setting new camera settings ...")
        settings['ExposureTime'] = int(values['ExposureTime'])
        settings['Gain'] = int(values['Gain'])
        window.Refresh()
        updateCameraSetting(camera, settings)

    if event == 'MaxExposureTime':
        window['ExposureTime'].Update(int(values['logging_rate'])*1000)

    if event == 'Set settings as default':
        SaveAsDefault()

    if event == "StartCamera":
        if not cameraStarted:
            try:
                camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
                camera.Open()
                print("Using device ", camera.GetDeviceInfo().GetModelName())
                window.Refresh()
                updateImage(camera)
                window['StartCamera'].Update('Stop camera')
                cameraStarted = True
                window['ApplySettings'].Update(disabled=False)
                window['ExposureTime'].Update(disabled=False)
                window['MaxExposureTime'].Update(disabled=False)
                window['Gain'].Update(disabled=False)
                window['ExperimentName'].Update(disabled=False)
                print('Camera started')
                window.Refresh()
                if keithleyStarted:
                    window['StartLogging'].Update(disabled=False)
            except Exception as err:
                print('ERROR     Cannot connect to camera. ', err)
        else:
            camera.Close()
            cameraStarted = False
            window['ApplySettings'].Update(disabled=True)
            window['ExposureTime'].Update(disabled=True)
            window['MaxExposureTime'].Update(disabled=True)
            window['Gain'].Update(disabled=True)
            window['ExperimentName'].Update(disabled=True)
            window['StartCamera'].Update('Start camera')
            print('Camera stopped')
            window.Refresh()
            window['StartLogging'].Update(disabled=True)

    if cameraStarted and time.time() - tUpdate > updateInterval:
        updateImage(camera)
        t = time.time()


    if event == 'StartLogging':
        if not loggingAll:
            if not outputFolder:
                print('Select an output folder first')
                continue
            logging_rate = float(values['logging_rate'])
            experimentName = values['ExperimentName']
            filenameKeithley = os.path.join(outputFolder, f"Keithley_Logfile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            window['StartLogging'].Update('Stop logging')
            f = open(filenameKeithley, 'w')
            f.write("datetimestamp image, datetimestamp keithley, current (A), voltage (V), set voltage (V)\n")
            print(f"Created log file '{filenameKeithley}'.")
            tLogging = time.time()
            loggingAll = True
            print('Logging started')
            window.Refresh()
        else:
            window['StartLogging'].Update('Start logging')
            loggingAll = False
            f.close()
            print('Logging stopped')

    if loggingAll and time.time() - tLogging > logging_rate:
        timestamp1 = datetime.now().strftime('%Y%m%d_%H%M%S_%f')

        img = pylon.PylonImage()
        camera.StartGrabbing()
        with camera.RetrieveResult(2000) as result:
            img.AttachGrabResultBuffer(result)
            img.Save(pylon.ImageFileFormat_Tiff, os.path.join(outputFolder, f"{experimentName}_{timestamp1}.tiff"))
            img.Release()
        camera.StopGrabbing()

        timestamp2 = datetime.now().strftime('%Y%m%d_%H%M%S_%f')  # redo, so more accurate in log file
        print(f"{timestamp1}, {timestamp2}, {keithley.current}, {keithley.voltage}, {currentVoltage}")
        f.write(f"{timestamp1}, {timestamp2}, {keithley.current}, {keithley.voltage}, {currentVoltage}\n")

        tLogging = time.time()

    if event == 'Help':
        with open('help.txt', 'r') as f:
            helpText = f.read()
        sg.popup_ok(helpText, keep_on_top=True, title="EDWControl help", line_width=100)
