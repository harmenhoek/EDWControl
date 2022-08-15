import PySimpleGUI as sg
from pypylon import pylon
import cv2
import os
import time
from datetime import datetime
import json
from pymeasure.instruments.keithley import Keithley2450
import pyvisa


# PyInstaller -F --onefile --noconsole -n EDWControl-0_1 .\gui2.p
#  Pyinstaller .\EDWControl-0_1.spec

version = 0.1

'''

2022-08-11 Testing the delay
Recorded the screen with the external camera, where I printed the time continuously (py script in Prompt)
Compared the time in the image with the saved time in the filename
Differences are about 15-30ms (filename is ahead of actual, because grabbing happens afterwards).
Result is worse (-100ms) when the filename is determined after waiting for the grab result.
Thus the former method is implemented

'''

sg.theme('DarkAmber')   # Add a touch of color


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
    # [
    #     sg.Text('Recording framerate'),
    #     sg.InputText(size=(10, 1), key='fps_output', disabled=True)
    # ],
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

    # [
    #     sg.Button('Record', key='Record', disabled=True)
    # ],

]


col2 = [
    [
        # sg.Image(key="-IMAGE-", size=(400, 400))

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
        sg.T('Electrodewetting Control', font='_ 18', justification='c', expand_x=True),
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
    # [
    #     sg.Text('Readout rate'),
    #     sg.InputText(size=(10, 1), key='KeithleyReadOutRate', disabled=True),
    # ],
    [
        sg.Text('Voltage range (comma seperate)'),
        sg.InputText(size=(50, 1), key='KeithleyVoltages', disabled=True),
    ],
    [
        sg.Text('Dwell times (comma seperate)'),
        sg.InputText(size=(50, 1), key='KeithleyDwellTimes', disabled=True),
    ],
    # [
    #     sg.Button('Apply settings', key='ApplySettingsKeithley', disabled=True),
    # ],
    # [
    #     sg.HSeparator(),
    # ],
    # [
    #     sg.Button('Start logging', key='LogKeithley', disabled=True),
    # ],
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
        sg.Push(),
        sg.Button('Set settings as default'),
        sg.Button('Exit'),
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
        # 'fps_output': window["fps_output"].get(),
        'ExposureTime': window["ExposureTime"].get(),
        'Gain': window["Gain"].get(),
        'ExperimentName': window["ExperimentName"].get(),
        # 'KeithleyReadOutRate': window["KeithleyReadOutRate"].get(),
        'KeithleyVoltages': window["KeithleyVoltages"].get(),
        'KeithleyDwellTimes': window["KeithleyDwellTimes"].get(),
        'FrontTerminals': window["FrontTerminals"].get(),
        'KeithleyDeviceID': window["KeithleyDeviceID"].get(),
        'logging_rate': window["logging_rate"].get(),
    }
    with open('EDWControlSettings.json', 'w') as f:
        json.dump(data, f, indent=2)
        print(f"{datetime.now().strftime('%H:%M:%S')} OK        Settings saved as defaults to 'EDWControlSettings.json'.")

def SetInitialValues():
    print('----- Electrodewetting Control -----')
    print('by Harmen Hoek')
    print(f"Version: {version} (https://github.com/harmenhoek/EDWControl)")

    try:
        with open('EDWControlSettings.json') as f:
            settings = json.load(f)
            # window["fps_output"].update(settings['fps_output'])
            window["ExposureTime"].update(settings['ExposureTime'])
            window["Gain"].update(settings['Gain'])
            window["ExperimentName"].update(settings['ExperimentName'])
            # window["KeithleyReadOutRate"].update(settings['KeithleyReadOutRate'])
            window["KeithleyVoltages"].update(settings['KeithleyVoltages'])
            window["KeithleyDwellTimes"].update(settings['KeithleyDwellTimes'])
            window["FrontTerminals"].update(settings['FrontTerminals'])
            window["KeithleyDeviceID"].update(settings['KeithleyDeviceID'])
            window["logging_rate"].update(settings['logging_rate'])


            print(f"{datetime.now().strftime('%H:%M:%S')} OK        Default settings loaded from 'EDWControlSettings.json'.")

    except:
        print(f"{datetime.now().strftime('%H:%M:%S')} WARNING   No default settings found. Press 'Set settings as default' to create default settings.")


# def ReadOutToLogFile(filename, setvoltage):
#     with open(filename, 'w') as f:
#         datetimestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
#         print(f"{datetimestamp}, {keithley.current}, {keithley.voltage}, {setvoltage}")
#         f.write(f"{datetimestamp}, {keithley.current}, {keithley.voltage}, {setvoltage}\n")

def updateCameraSetting(camera, settings):
    camera.ExposureTime.SetValue(settings['ExposureTime'])
    camera.Gain.SetValue(settings['Gain'])

settings = {
    'ExposureTime': 100,
    'Gain': 0,
    'fps_output': 1,
}

window = sg.Window("Electrodewetting Control", layout, finalize=True)
SetInitialValues()

updateInterval = 1
outputFolder = 'recordings'

cameraStarted = False
recording = False
keithleyStarted = False
keithleyRecording = False
keithleyRamp = False
setVoltage = 0

loggingAll = False

tUpdate = time.time()
tRecording = time.time()
while True:
    event, values = window.read(timeout=100)
    if event == "Exit" or event == sg.WIN_CLOSED:
        break

    if event == "StartKeithley":
        if not keithleyStarted:
            print("Keithley2450Control program")
            print('Checking available devices ...')
            rm = pyvisa.ResourceManager()  # should use Keysight by default
            print(f"Found devices: {rm.list_resources()}. Needs device {values['KeithleyDeviceID']}")
            try:
                keithley = Keithley2450(values['KeithleyDeviceID'])
                print('Connection successfull.')
                keithley.reset()
                if values['FrontTerminals']:
                    keithley.use_front_terminals()
                keithley.measure_current()
                keithley.enable_source()
                print('Keithley setup correctly.')
                if cameraStarted:
                    window['StartLogging'].Update(disabled=False)
            except:
                print("Unable to connect to the Keithley 2450.")
                continue
            # window['KeithleyReadOutRate'].Update(disabled=False)
            window['KeithleyVoltages'].Update(disabled=False)
            window['KeithleyDwellTimes'].Update(disabled=False)
            # window['ApplySettingsKeithley'].Update(disabled=False)
            window['FrontTerminals'].Update(disabled=True)
            window['KeithleyDeviceID'].Update(disabled=True)
            keithleyStarted = True
        else:
            # window['KeithleyReadOutRate'].Update(disabled=True)
            window['KeithleyVoltages'].Update(disabled=True)
            window['KeithleyDwellTimes'].Update(disabled=True)
            # window['ApplySettingsKeithley'].Update(disabled=True)
            window['FrontTerminals'].Update(disabled=False)
            window['KeithleyDeviceID'].Update(disabled=False)
            keithleyStarted = False
            window['StartLogging'].Update(disabled=True)

    # if event == 'LogKeithley':
    #     if not keithleyRecording:
    #         filenameKeithley = f"Keithley_Logfile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    #         with open(filenameKeithley, 'w') as f:
    #             f.write("datetimestamp, current (A), voltage (V), set voltage (V)\n")
    #             print(f"Created log file '{filenameKeithley}'.")
    #             tReadoutKeithley = time.time()
    #             tVoltagechangeKeithley = time.time()
    #         window['Record'].Update('Stop logging')
    #         print('Logging started')
    #         keithleyRecording = True
    #     else:
    #         window['Record'].Update('Start logging')
    #         print('Logging stopped')
    #         keithleyRecording = False

    if event == 'VoltageKeithley':
        if not keithleyRamp:
            window['KeithleyVoltages'].Update(disabled=False)
            window['KeithleyDwellTimes'].Update(disabled=False)
            window['VoltageKeithley'].Update('Stop voltage sweep')
            keithleyRamp = True
            keithleyDwellIdx = 0
            KeithleyVoltages = [float(x) for x in values['KeithleyVoltages'].split(',')]
            KeithleyDwellTimes = [float(x) for x in values['KeithleyDwellTimes'].split(',')]
            print('Voltage sweep started')
        else:
            window['KeithleyVoltages'].Update(disabled=True)
            window['KeithleyDwellTimes'].Update(disabled=True)
            window['VoltageKeithley'].Update('Start voltage sweep')
            setVoltage = 0
            keithleyRamp = False
            print('Voltage sweep stopped')

    # if keithleyRecording and time.time() - tReadoutKeithley > float(values['KeithleyReadOutRate']):
    #     try:
    #         ReadOutToLogFile(filenameKeithley, setVoltage)
    #     except:
    #         print('Logging to file failed ...')
    #     tReadoutKeithley = time.time()

    if keithleyRamp and time.time() - tVoltagechangeKeithley > KeithleyDwellTimes[keithleyDwellIdx]:
        if keithleyDwellIdx < len(KeithleyVoltages):
            setVoltage = KeithleyVoltages[keithleyDwellIdx]
            print(f'Voltage set to {setVoltage}V.')
            keithley.source_voltage = setVoltage
            keithley.current
            tVoltagechangeKeithley = time.time()
            keithleyDwellIdx = keithleyDwellIdx + 1
        else:
            window['KeithleyVoltages'].Update(disabled=True)
            window['KeithleyDwellTimes'].Update(disabled=True)
            window['VoltageKeithley'].Update('Start voltage sweep')
            keithleyRamp = False
            setVoltage = 0
            print('Voltage ramping ended')






    if event == "ApplySettings" and cameraStarted:
        print(f"Setting new camera settings ...")

        settings['ExposureTime'] = int(values['ExposureTime'])
        settings['Gain'] = int(values['Gain'])

        updateCameraSetting(camera, settings)

    if event == 'MaxExposureTime':
        # window['ExposureTime'].Update(int(values['fps_output'])*1000)
        window['ExposureTime'].Update(int(values['logging_rate'])*1000)


    if event == 'Set settings as default':
        SaveAsDefault()

    if event == "StartCamera":
        if not cameraStarted:
            try:
                camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
                camera.Open()
                print("Using device ", camera.GetDeviceInfo().GetModelName())
                updateImage(camera)
                window['StartCamera'].Update('Stop camera')
                cameraStarted = True
                # window['Record'].Update(disabled=False)
                window['ApplySettings'].Update(disabled=False)
                window['ExposureTime'].Update(disabled=False)
                window['MaxExposureTime'].Update(disabled=False)
                window['Gain'].Update(disabled=False)
                # window['fps_output'].Update(disabled=False)
                window['ExperimentName'].Update(disabled=False)
                print('Camera started')
                if keithleyStarted:
                    window['StartLogging'].Update(disabled=False)
            except Exception as err:
                print('ERROR     Cannot connect to camera. ', err)
        else:
            camera.Close()
            cameraStarted = False
            # window['Record'].Update(disabled=True)
            window['ApplySettings'].Update(disabled=True)
            window['ExposureTime'].Update(disabled=True)
            window['MaxExposureTime'].Update(disabled=True)
            window['Gain'].Update(disabled=True)
            # window['fps_output'].Update(disabled=True)
            window['ExperimentName'].Update(disabled=True)
            window['StartCamera'].Update('Start camera')
            print('Camera stopped')
            window['StartLogging'].Update(disabled=True)

    # if event == 'Record':
    #     if not recording:
    #         settings['fps_output'] = float(values['fps_output'])
    #         window['Record'].Update('Stop recording')
    #         recording = True
    #         fps_output = float(values['fps_output'])
    #         experimentName = values['ExperimentName']
    #         print('Recording now ...')
    #     else:
    #         recording = False
    #         window['Record'].Update('Record')
    #         print('Recoding stopped')



    # if recording and time.time() - tRecording > fps_output:
    #     timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    #     filename = os.path.join(outputFolder, f"{experimentName}_{timestamp}.tiff")
    #     img = pylon.PylonImage()
    #     camera.StartGrabbing()
    #     with camera.RetrieveResult(2000) as result:
    #         img.AttachGrabResultBuffer(result)
    #         img.Save(pylon.ImageFileFormat_Tiff, filename)
    #         img.Release()
    #     camera.StopGrabbing()

    if cameraStarted and time.time() - tUpdate > updateInterval:
        updateImage(camera)
        t = time.time()


    if event == 'StartLogging':
        if not loggingAll:
            logging_rate = float(values['logging_rate'])
            experimentName = values['ExperimentName']
            filenameKeithley = f"Keithley_Logfile_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            window['StartLogging'].Update('Stop logging')
            with open(filenameKeithley, 'w') as f:
                f.write("datetimestamp image, datetimestamp keithley, current (A), voltage (V), set voltage (V)\n")
            print(f"Created log file '{filenameKeithley}'.")
            tLogging = time.time()
            loggingAll = True
            print('Logging started')
        else:
            window['StartLogging'].Update('Start logging')
            loggingAll = False
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

        with open(filenameKeithley, 'w') as f:
            timestamp2 = datetime.now().strftime('%Y%m%d_%H%M%S_%f')  # redo, so more accurate in log file
            print(f"{timestamp1}, {timestamp2}, {keithley.current}, {keithley.voltage}, {setVoltage}")
            f.write(f"{timestamp1}, {timestamp2}, {keithley.current}, {keithley.voltage}, {setVoltage}\n")

        tLogging = time.time()


