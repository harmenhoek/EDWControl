import PySimpleGUI as sg
from pypylon import pylon
import time
import numpy as np
import io
from PIL import Image, ImageTk
import cv2
import threading
import csv
import os

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


settingsFilename = 'cameraSettings.pfs'

def SettingsFromFile(filename):
    with open(filename, mode='r') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader)
        next(reader)
        next(reader)
        cameraSettings = dict(reader)
    return cameraSettings

def SettingsToFile(filename, settings, original_header=True):
    if original_header:
        with open(filename, mode='r') as f:
            header = f.readlines()[0:3]
    with open(filename, mode='w') as f:
        if original_header:
            for line in header:
                f.write(line)
        for key, value in settings.items():
            print(key, value)
            f.write(f"{key}\t{value}\n")

col1 = [
    [
        sg.T('Settings', font='_ 14', justification='c', expand_x=True),
    ],
    [
        sg.Button('Start Camera', key='StartCamera'),
        sg.Button('Test button', key='TestButtonPressed')
    ],
    [
        sg.HSeparator(),
    ],
    [
        sg.Text('Recording framerate'),
        sg.InputText(size=(10, 1), key='fps_output')
    ],
    [
        sg.Text('Exposuretime [ms]'),
        sg.InputText(size=(10, 1), key='ExposureTime')
    ],
    [
        sg.Button('Apply settings', key='ApplySettings'),
    ],
    [
        sg.T('.tiff, no compression')
    ],
    [
        sg.HSeparator(),
    ],
    [
        sg.Button('Record', key='Record')
    ],

]

camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())

img = Image.open('saved_pypylon_img_%d.jpeg')
col2 = [
    [
        sg.T('Viewer', font='_ 14', justification='c', expand_x=True),
    ],
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
        # sg.Output(s=(100, 15), key='outputbox'),
    ],
]

layout = [
    [
        sg.Column(col1, element_justification='c', vertical_alignment='top'),
        sg.Column(col2, element_justification='c')
    ],
    [
        # output_row,
    ],

]

window = sg.Window("Electrodewetting Control", layout)


def updateImage(camera):
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

        global new_settings
        if new_settings:
            camera.ExposureTime.SetValue(50000)
            new_settings = False

        # global stop_threads
        # if stop_threads:
        #     camera.Close()
        #     break
        time.sleep(0.5)
        # camera.StopGrabbing()


# ---------------------------------------------------------------
# camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    # https://github.com/basler/pypylon/issues/10
        # camera.PixelFormat = "Mono8"
        # camera.MaxNumBuffer = 2
        # camera.Gain = camera.Gain.Max
        # camera.Width = camera.Width.Max
        # camera.Height = camera.Height.Max
        # camera.ExposureTime = camera.ExposureTime.Min
        # camera.PixelFormat = "Mono12"


def SetCamera(settings):
    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    camera.Open()
    # pylon.FeaturePersistence.Save(settingsFilename, camera.GetNodeMap())
    # pylon.FeaturePersistence.Load(settingsFilename, camera.GetNodeMap())


    # # set camera settings: create default template from camera if no settings file exists, then load settings file into dict, change settings, save dict to file, save file settings to camera
    # if not os.path.exists(settingsFilename):
    #     pylon.FeaturePersistence.Save(settingsFilename, camera.GetNodeMap())
    # cameraSettings = SettingsFromFile(settingsFilename)
    # import json
    # print(json.dumps(cameraSettings, indent=4))
    # # cameraSettings['ExposureTime'] = int(50009.0)
    # SettingsToFile(settingsFilename, cameraSettings)
    # # pylon.FeaturePersistence.Load(settingsFilename, camera.GetNodeMap(), True)






    # print(settings['ExposureTime']*1000)
    # camera.ExposureTime.SetValue(settings['ExposureTime']*1000)

    # Print the model name of the camera.
    print("Using device ", camera.GetDeviceInfo().GetModelName())

    # Start the grabbing of c_countOfImagesToGrab images.
    # The camera device is parameterized with a default configuration which
    # sets up free-running continuous acquisition.
    camera.StartGrabbingMax(10000, pylon.GrabStrategy_LatestImageOnly)

    thread_image = threading.Thread(target=updateImage, args=(camera,))
    thread_image.setDaemon(True)
    thread_image.start()
    return thread_image

settings = {
    'ExposureTime': 500,
}

cameraStarted = False
stop_threads = False
new_settings = False
while True:
    event, values = window.read(timeout=100)
    if event == "Exit" or event == sg.WIN_CLOSED:
        break

    if event == "ApplySettings" and cameraStarted:
        print(f"Setting new camera settings ...")

        # new_settings = True
        # thread_image.join()
        # # settings['ExposureTime'] = int(values['ExposureTime'])
        # new_settings = False

        # stop_threads = True
        # thread_image.join()
        # settings['ExposureTime'] = int(values['ExposureTime'])
        # stop_threads = False

        thread_image = SetCamera(settings)

    if event == "StartCamera":
        cameraStarted = True
        thread_image = SetCamera(settings)

    if event == "TestButtonPressed":
        print('TestButtonPressed!')
