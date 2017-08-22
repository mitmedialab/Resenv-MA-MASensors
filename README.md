# Resenv-MA-MASensors


# Run code: 
```
python Main.py <output_file_prefix>
```

## Edit which sensors are used 
In SensorCellectionServer.py edit the parameter:
```
# Edit here what sensors are used
use_E4_L = False
use_E4_R = False
use_Bioharness = True
use_Intraface = False
use_Intraface_only_record = False
use_Muse = False
# Edit here whether to use real-time processing
use_real_time_processing = False
```

## Edit Bioharness Bluetooth port
In SensorCellectionServer.py edit the parameter:
```
Edit here Bioharness Bluetooth port information 
# pair device with you computer, code 1234
# ls /dev/cu.* find out with port it is connected to
BIOHARNESS_COM_PORT = "EDIT"
```

## Edit E4 Server information
In SensorCellectionServer.py edit the parameter:
```
# Edit here E4 Server information 
E4_SERVER_IP = "EDIT" 
E4_SERVER_PORT = EDIT
```

## Edit Interface Server information 
In SensorCellectionServer.py edit the parameter:
```
# Edit here Interface Server information 
INTRAFACE_SERVER_IP = "EDIT"
INTRAFACE_SERVER_PORT = EDIT
```

## Edit collected data path
In SensorCellectionServer.py edit the parameter
```
# Edit here the path where the collected data is store
DATA_BASE_PATH = "./CollectedData/"
```

## Edit port for signal processing server
This is the port were your service can subscribe to real-time data streams. In SensorCellectionServer.py edit the parameter:
```
# Edit here the port for signal processing server
PROCESSING_SERVER_IP = "127.0.0.1"
PROCESSING_SERVER_PORT = 12346
```