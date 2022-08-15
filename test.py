import csv

filename = 'cameraSettings.txt'

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
            f.write(f"{key}\t{value}\n")

settings = SettingsFromFile(filename)
print(settings)

settings['ExposureAuto'] = 'On'

SettingsToFile(filename, settings)

settings = SettingsFromFile(filename)
print(settings)
