'''
Created on Mar 9, 2016

@author: nanzhao@media.mit.edu, azaria@media.mit.edu
'''

import argparse
import os
import subprocess
import logging

from twisted.internet import reactor
from twisted.internet.serialport import SerialPort
from twisted.internet import stdio
#from autobahn.twisted.websocket import WebSocketServerFactory
from twisted.internet.protocol import ReconnectingClientFactory, Protocol

from Logger import DataLogger, WriteToLogLock, LoggingUserControl, LoggingWebsocketControlFactory

from E4BLEClient import E4ClientFactory
from BioharnessClient import BioharnessProtocol
from E4Commands import StreamMessagesDecoder
from IntraFaceClient import InrafaceSample, IntraFaceClientFactory

import json 

base_path = os.getcwd()

def parse_commandline_arguments():
    parser = argparse.ArgumentParser(description='Sensor Collection Server')
    parser.add_argument("output_file_prefix",
                        help="A prefix for the output files generated")
    parser.add_argument("-p", "--sample_period", dest="command_args_sample_period", type=int, default=0,
                        help="Pause sampling every X seconds. If not stated sampling will be continuous")
    return parser.parse_args()

class LoggersContainer(object):

    def __init__(self, data_base_path, write_to_log_lock, E4_stream_decoder):
        self.base_path = data_base_path
        self.write_to_log_lock = write_to_log_lock
        self.E4_stream_decoder = E4_stream_decoder
        self.in_session = False
        self.loggers = {}
        
    def set_setter_logger_pairs(self, setter_logger_pairs):
        self.setter_logger_pairs = setter_logger_pairs
        
    def update_loggers_for_portocols(self):
        for setter, logger in self.setter_logger_pairs:
            setter(self.loggers[logger])
            
    def new_logging_session(self, output_file_prefix):
        if self.in_session:
            self.close_logging_session()
            
        self.loggers["E4_loggers_L"] = self.create_loggers_for_E4_client(output_file_prefix, "L", self.E4_stream_decoder, self.write_to_log_lock)
        self.loggers["E4_loggers_R"] = self.create_loggers_for_E4_client(output_file_prefix, "R", self.E4_stream_decoder, self.write_to_log_lock)
        self.loggers["bioharness_loggers"] = self.create_loggers_for_bioharness(output_file_prefix, self.write_to_log_lock)
        self.loggers["intraface_logger"] = self.create_logger_for_intraface(output_file_prefix, self.write_to_log_lock)
        
        self.update_loggers_for_portocols()
        self.in_session = True
        
    def close_logging_session(self):
        self.loggers["intraface_logger"].close_log_file()
        self.close_loggers(self.loggers["bioharness_loggers"])
        self.close_loggers(self.loggers["E4_loggers_R"])
        self.close_loggers(self.loggers["E4_loggers_L"])
        self.in_session = False

    def create_loggers_for_E4_client(self, output_file_prefix, client_id, stream_decoder, write_to_log_lock):
        E4_loggers = {}
    
        for stream_type in self.E4_stream_decoder.possible_streams.keys():
            file_prefix = "%s_E4_%s_%s" % (output_file_prefix, client_id, stream_type)
            stream_columns =  self.E4_stream_decoder.possible_streams[stream_type].values
            E4_loggers[stream_type] = DataLogger(os.path.join(self.base_path, output_file_prefix), file_prefix, 
                                                 stream_columns, write_to_log_lock)
        return E4_loggers

    def create_loggers_for_bioharness(self, output_file_prefix, write_to_log_lock):
        bioharness_loggers = {}
        for stream_type in BioharnessProtocol.columns_of_streams.keys():
            file_prefix = "%s_BIO_%s" % (output_file_prefix, stream_type)
            stream_columns = BioharnessProtocol.columns_of_streams[stream_type]
            bioharness_loggers[stream_type] = DataLogger(os.path.join(self.base_path, output_file_prefix), file_prefix, 
                                                         stream_columns, write_to_log_lock)
        return bioharness_loggers

    def create_logger_for_intraface(self, output_file_prefix, write_to_log_lock):
        file_prefix = "%s_INTRA" % (output_file_prefix)
        intraface_columns = InrafaceSample._fields
        intraface_logger = DataLogger(os.path.join(self.base_path, output_file_prefix), file_prefix,
                                           intraface_columns, write_to_log_lock) 
        return intraface_logger

    def close_loggers(self, loggers):
        for logger in loggers.values():
            logger.close_log_file()
 


class SensorProxyFactory(ReconnectingClientFactory):
    def __init__(self):
        logging.info("Proxy - Real-time processing proxy server started")
        self.client_list = []
    
    def buildProtocol(self, addr):
        self.protocol = Protocol()
        return self.protocol
    
    def clientConnectionLost(self, connector, reason):
        logging.error('Proxy - Lost connection.  Reason: %s' % (reason))
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        logging.error('Proxy - Connection failed.  Reason: %s' % (reason))
        ReconnectingClientFactory.clientConnectionFailed(self, connector, reason)
        
    def notifyAll(self, data):
        logging.debug("Proxy - Send %s data for real-time processing, buffer size %i" % (data['type'], len(data['value'])))
        if hasattr(self.protocol, 'transport'):
            self.protocol.transport.write(json.dumps(data))

        
def main(command_args, start_logging = True):
    print("Started Sensor Collection Server")
    
    # Edit here Bioharness Bluetooth port information 
    # pair device with you computer, code 1234
    # ls /dev/cu.* find out with port it is connected to
    #BIOHARNESS_COM_PORT = "/dev/cu.BHBHT502508A-iSerialPor"
    #BIOHARNESS_COM_PORT = "/dev/cu.BHBHT011334-iSerialPort1"
    BIOHARNESS_COM_PORT = "/dev/cu.BHBHT017270-iSerialPort1"
    
    # Edit here E4 Server information 
    E4_SERVER_IP = "18.85.59.169" 
    E4_SERVER_PORT = 6666
    
    # Edit here Interface Server information 
    INTRAFACE_SERVER_IP = "127.0.0.1"
    INTRAFACE_SERVER_PORT = 31400
    
    # Edit here port of the websocket for logging command
    LOGGING_WEB_CONTROL_PORT = 55556
    
    # Edit here the pather where the collected data is store
    DATA_BASE_PATH = "./CollectedData/StudyGershon"

    # Edit here the port for signal processing server
    PROCESSING_SERVER_IP = "127.0.0.1"
    PROCESSING_SERVER_PORT = 12346
    
    # Edit here what sensors are used
    use_E4_L = False
    use_E4_R = False
    use_Bioharness = True
    use_Intraface = True
    use_Intraface_only_record = False
    use_Muse = True
    # Edit here whether to use real-time processing
    use_real_time_processing = True
    
    #command_args = parse_commandline_arguments()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M')
    
    
    # data logger control
    write_to_log_lock = WriteToLogLock(reactor, command_args.command_args_sample_period)
    if start_logging:
        write_to_log_lock.unlock_writing_to_log_file()

    # Initializing the signal processing proxy for real-time processing
    real_time_processing_proxy_factory = SensorProxyFactory()

    # Setting up the E4 stream decoder
    E4_stream_decoder = StreamMessagesDecoder()

    # Setting up data loggers (Note that these are not associated with a client yet)
    loggers_container = LoggersContainer(DATA_BASE_PATH, write_to_log_lock, E4_stream_decoder)
    loggers_container.set_setter_logger_pairs([])
    loggers_container.new_logging_session(command_args.output_file_prefix)
    
    # Initializing one E4 for the Right Hand 
    client_factory_R = E4ClientFactory()
    client_factory_R.set_client_id("R")
    client_factory_R.set_stream_decoder(E4_stream_decoder)
    client_factory_R.set_data_loggers(loggers_container.loggers["E4_loggers_R"])

    # Initializing one E4 for the Left Hand 
    client_factory_L = E4ClientFactory()
    client_factory_L.set_client_id("L")
    client_factory_L.set_stream_decoder(E4_stream_decoder)
    client_factory_L.set_data_loggers(loggers_container.loggers["E4_loggers_L"])     
    
    # Initializing the Bioharness
    bioharness_protocol = BioharnessProtocol(real_time_processing_proxy_factory, BIOHARNESS_COM_PORT, reactor)
    bioharness_protocol.set_data_loggers(loggers_container.loggers["bioharness_loggers"])
    bioharness_protocol.set_event_callbacks() # Note: that would be the default callback, writing the sample to the appropriate logger
    bioharness_protocol.set_waveform_callbacks() # Note: that would be the default callback, writing the sample to the appropriate logger
    
    # Initializing the Intraface
    intraface_factory = IntraFaceClientFactory(real_time_processing_proxy_factory)
    intraface_factory.set_data_logger(loggers_container.loggers["intraface_logger"])
    
    
    # Connect proxy server for real time processing 
    if use_real_time_processing:
        real_time_processing_proxy = reactor.connectTCP(PROCESSING_SERVER_IP, PROCESSING_SERVER_PORT, real_time_processing_proxy_factory)
        subprocess.Popen(["python " + base_path + "/SignalProcessingServer.py " + command_args.output_file_prefix], shell=True)
    
    if use_Muse:
        eeg_path = os.path.abspath(os.path.join(os.path.dirname(base_path), '..', 'Documents', 'EEGAnalysis'))
        subprocess.Popen(["python3 " + eeg_path + "/__init__.py "], shell=True)
         
    if use_E4_L:
        # Connecting to the E4 Left Hand
        E4_client_L = reactor.connectTCP(E4_SERVER_IP, E4_SERVER_PORT , client_factory_L)
    if use_E4_R:    
        # Connecting to the E4 Right Hand
        E4_client_R = reactor.connectTCP(E4_SERVER_IP, E4_SERVER_PORT , client_factory_R)

    if use_Bioharness:   
        # Connecting to the Bioharness
        #ser = SerialPort(bioharness_protocol, BIOHARNESS_COM_PORT, reactor, baudrate=115200)
        #bioharness_protocol.set_serial(ser)
        bioharness_protocol.reconnect()
        
    if use_Intraface:   
        intraface_factory.run_server()
        # Connecting to the Intraface Server
        intraface_cliet = reactor.connectTCP(INTRAFACE_SERVER_IP, INTRAFACE_SERVER_PORT, intraface_factory)
    elif use_Intraface_only_record:
        intraface_factory.run_recorder()
        
    # Initializing the LoggingUserControl (Controlling logging from the terminal)
    user_control_protocol = LoggingUserControl()
    user_control_protocol.set_write_to_log_lock(write_to_log_lock)
    stdio.StandardIO(user_control_protocol)
    
    # Initializing the LoggingWebsocketControl (Controllign logging from the a Webserver for computerized tests)
    loggers_container.set_setter_logger_pairs([(client_factory_R.update_data_loggers,"E4_loggers_R"),
                                               (client_factory_L.update_data_loggers,"E4_loggers_L"),
                                               (bioharness_protocol.set_data_loggers,"bioharness_loggers"),
                                               (intraface_factory.update_data_logger,"intraface_logger")])
    factory = LoggingWebsocketControlFactory(u"ws://127.0.0.1:%s" % LOGGING_WEB_CONTROL_PORT)
    factory.logger_container = loggers_container
    reactor.listenTCP(LOGGING_WEB_CONTROL_PORT, factory)


    try:
        logging.debug("SensorCollectionServer - Reactor running")
        reactor.run()
    
    except Exception as e:
        Logging.error(e)
        
        logging.error("Received Keyinterrupt - Stopping reactor and closing connections")
        if ser is not None:
            ser._serial.close()
        #E4_client_R.disconnect()
        #E4_client_L.disconnect()
        #intraface_cliet.disconnect()
        loggers_container.close_logging_session()
    
if __name__ == '__main__':
    command_args = parse_commandline_arguments()
    main(command_args)
