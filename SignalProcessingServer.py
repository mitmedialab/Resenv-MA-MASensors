'''
Created 2017

@author: nanzhao@media.mit.edu
'''

import sys
from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory, Protocol
from twisted.protocols.basic import LineReceiver

from twisted.internet import task
from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory

import numpy as np
import pandas as pd
from scipy import signal
from livestats import livestats

import pickle
import argparse
import os
import datetime, time
import json 
import logging 
import collections
from Logger import DataLogger, WriteToLogLock

base_path = os.getcwd()

list_of_features = ["timestamp", "Focus", "Restoration", "SDNN","head_pitch_high", "respiration", "neutral_expression", "head_pitch", "eeg_focus", "eeg_relax"]                                                         
ProcessedSample = collections.namedtuple("ProcessedSample", list_of_features)

def parse_commandline_arguments():
    parser = argparse.ArgumentParser(description='Sensor Collection Server')
    parser.add_argument("subject_name", default="Test",
                        help="Subject name to load physiology model")
    return parser.parse_args()
    
class AxesInterfaceProtocol(WebSocketServerProtocol):
    def onConnect(self, request):
        self.peer = request.peer
        logging.info("Axes - Received Connection from {}".format(request.peer))

    def onOpen(self):
        logging.info("Axes - Connection open.")
        self.factory.client_list.append(self)
        
    def onMessage(self, payload, isBinary):
        logging.debug("Axes - Received Command - %s" % (payload))
            
    def onClose(self, wasClean, code, reason):
        logging.info("Axes - Connection closed: {0}".format(reason))
        if self in self.factory.client_list:
            self.factory.client_list.remove(self)


class AxesInterfaceFactory(WebSocketServerFactory):
    def __init__(self, url):
        WebSocketServerFactory.__init__(self, url)
        self.client_list = []
          
    def buildProtocol(self, addr):
        proto = AxesInterfaceProtocol()
        proto.factory = self
        return proto

    def notifyAll(self, data_obj):
        data = json.dumps(data_obj, ensure_ascii = False).encode('utf8')
        for cli in self.client_list:
            logging.debug("Axes - Send Data to %s - %s" % (cli.peer, data))
            cli.sendMessage(data)
            
class ProcessingProtocol(Protocol):
    def __init__(self, factory):
        self.factory = factory
          
    def dataReceived(self, data):
        try:
            #logging.info('Data received {}'.format(data))
            for datum in data.split("}"): 
                if len(datum)>0:
                    data_obj = json.loads(datum+"}")
                    if data_obj['type'] == "rr_buffer":
                        self.factory.process_rr(data_obj)
                    elif data_obj['type'] == "respiration_rate":
                        self.factory.process_respiration_rate(data_obj)
                    elif data_obj['type'] == "facial_features":
                        self.factory.process_facial_features(data_obj)     
                    elif data_obj['type'] == "eeg_focus":
                        self.factory.process_eeg_focus_features(data_obj)  
                    elif data_obj['type'] == "eeg_relax":
                        self.factory.process_eeg_relax_features(data_obj)   
                      
        except: 
            logging.error("Processing Could not parse received data %s.", data)
            
    def connectionMade(self):
        logging.debug('Processing - Connected to {}'.format(self.transport.getPeer()))
        if len(self.factory.client_list)==0: 
            self.factory.first_client()
        self.factory.client_list.append(self)

    def connectionLost(self, reason):
        logging.debug('Processing - Lost connection because {}'.format(reason))
        if self in self.factory.client_list:
            self.factory.client_list.remove(self)
        if len(self.factory.client_list)==0: 
            self.factory.last_client()

class ProcessingFactory(ServerFactory):
    AXES_SAMPLEING_RATE = 1.0 # in seconds
    AXES_UPDATE_RATE_COUNTER_LIMIT = 0
    
    def __init__(self, axesInterface, subject_name):
        self.client_list = []
        self.axesInterface = axesInterface
        self.subject_name = subject_name
        self.received_data = pd.DataFrame() # data buffer 
        self.features = list_of_features[3:]
        self.feature_stats = self.load_models(self.features)
        self.loop = task.LoopingCall(self.process_scores) # process and announce focus and restoration scores with constant sampling rate
        #self.loop = task.LoopingCall(self.runEverySecond) # test function
        self.axes_counter = 0
        self.focus_score = 0
        self.restoration_score = 0
        
    def buildProtocol(self, addr):
        proto = ProcessingProtocol(self)
        return proto
        
    def set_data_logger(self, logger):
        self.logger = logger    
   
    def first_client(self):
        self.loop.start(self.AXES_SAMPLEING_RATE) 
    
    def last_client(self):
        self.save_models(self.features, self.feature_stats)
        self.loop.stop()
         
    def runEverySecond(self):
        print("a second has passed")
        
    def process_rr(self, data):
        # resample and interpolate rr buffer
        rr_buffer = data['value']
        rr_df = pd.Series(np.array(rr_buffer))
        rr_df[rr_df.diff().abs() == 0] = np.nan
        std = rr_df.dropna().std() #drop outliers
        rr_df[rr_df>5*std] = np.nan
        try:
            rr_df = rr_df.abs().interpolate(method='cubic')
        except ValueError:
            logging.warn("Processing - Could not interpolate rr data.")
            return None 
            
        # power density estimation 
        #f, Pxx_den = signal.periodogram(rr_df.fillna(0).values, 18, nfft = 1024, detrend = "linear")
        #df = f[1]-f[0]
        #this_LF = (np.sum(Pxx_den[3:8]) * df)
        #this_HF = (np.sum(Pxx_den[9:23]) * df)
        ##logging.debug("HF raw: %f , LF raw: %f" % (this_HF, this_LF))
        #self.add_data_point(this_LF, "LF", data["timestamp"])
        #self.add_data_point(this_HF, "HF", data["timestamp"])
        
        # timedomain HRV
        this_SDNN = rr_df.std()
        self.add_data_point(this_SDNN, "SDNN", data["timestamp"])

        
    def process_respiration_rate(self, data):
        self.add_data_point(data['value'][0], "respiration", data["timestamp"])
    
    def process_facial_features(self, data):
        self.add_data_point(data['value'][0], "neutral_expression", data["timestamp"])
        self.add_data_point(data['value'][1], "head_pitch", data["timestamp"])
        self.add_data_point(max(data['value'][1],0), "head_pitch_high", data["timestamp"])

    def process_eeg_focus_features(self, data):
        self.add_data_point(data['value'][0], "eeg_focus", data["timestamp"])
        
    def process_eeg_relax_features(self, data): 
        self.add_data_point(data['value'][0], "eeg_relax", data["timestamp"])
        
    def add_data_point(self, data_point, data_type, timestamp):
        self.feature_stats[data_type].add(data_point)
        zscore = (data_point-self.feature_stats[data_type].mean())/np.sqrt(self.feature_stats[data_type].variance())
        df = pd.DataFrame({"type": [data_type], "value": [data_point], "zscore": [zscore], "timestamp": [timestamp]})
        self.received_data = self.received_data.append(df)
                           
    def process_scores(self):
        self.axes_counter += 1
        
        try:
            if self.received_data.size>0: 
                # Use only data within time limit and discard older data
                time_now = time.time()
                time_limit = time_now - 10
                self.received_data = self.received_data[self.received_data["timestamp"]>time_limit]
                #print(self.received_data[self.received_data["type"]=="head_pitch"].size)
            
                # HRV
                #LF_zscore_smoothed = self.received_data[self.received_data["type"]=="LF"]["zscore"].dropna().mean()
                #HF_zscore_smoothed = self.received_data[self.received_data["type"]=="HF"]["zscore"].dropna().mean()
                ##logging.info("HF: %f , LF: %f" % (HF_zscore_smoothed, LF_zscore_smoothed))
                SDNN_zscore_smoothed = self.received_data[self.received_data["type"]=="SDNN"]["zscore"].dropna().mean()
                #logging.info("HRV: %f" % (SDNN_zscore_smoothed))
                
                # Respiration
                respiration_zscore_smoothed = self.received_data[self.received_data["type"]=="respiration"]["zscore"].dropna().mean()
                #logging.info("Respiration: %f" % respiration_zscore_smoothed)
            
                # Facial features
                neutral_zscore_smoothed = self.received_data[self.received_data["type"]=="neutral_expression"]["zscore"].dropna().mean()
                #logging.info("Neutral Expression: %f" % neutral_zscore_smoothed)
                pitch_zscore_smoothed = self.received_data[self.received_data["type"]=="head_pitch"]["zscore"].dropna().mean()
                #logging.info("Head Pitch: %f" % pitch_zscore_smoothed)
                pitch_high_zscore_smoothed = self.received_data[self.received_data["type"]=="head_pitch_high"]["zscore"].dropna().mean()
                #logging.info("Head High: %f" % pitch_high_zscore_smoothed)
                
                # EEG features
                eeg_focus_zscore_smoothed = self.received_data[self.received_data["type"]=="eeg_focus"]["zscore"].dropna().mean()
                #logging.info("EEG Focus: %f" % eeg_focus_zscore_smoothed)
                eeg_relax_zscore_smoothed = self.received_data[self.received_data["type"]=="eeg_relax"]["zscore"].dropna().mean()
                #logging.info("EEG Relax: %f" % eeg_relax_zscore_smoothed)
               
               
                # Scores
                alpha = 0.97
                focus_factors = pd.Series([-pitch_zscore_smoothed, neutral_zscore_smoothed, eeg_focus_zscore_smoothed])
                restoration_factors = pd.Series([SDNN_zscore_smoothed,-respiration_zscore_smoothed, pitch_high_zscore_smoothed, eeg_relax_zscore_smoothed])
                focus_score = (alpha)*self.focus_score + (1-alpha)*focus_factors.dropna().mean()
                restoration_score = (alpha)*self.restoration_score + (1-alpha)*restoration_factors.dropna().mean()    
                
                if (focus_score == focus_score) and (restoration_score == restoration_score):
                    self.focus_score = focus_score
                    self.restoration_score = restoration_score
                    sample = (time.time(), self.focus_score, self.restoration_score, SDNN_zscore_smoothed, pitch_high_zscore_smoothed, -respiration_zscore_smoothed, 
                              neutral_zscore_smoothed, -pitch_zscore_smoothed, eeg_focus_zscore_smoothed, eeg_relax_zscore_smoothed)
                    self.logger.write_tuple_to_log_file(sample)
                    logging.info("Focus: %.2f , Restor: %.2f, SDNN: %.2f, Head High: %.2f, Resp: %.2f, Neutr. Exp.: %.2f, Head Pitch: %.2f, EEG Focus: %.2f, EEG Relax: %.2f" % sample[1:])
                                           
                    # send out focus and restoration scores
                    if self.axes_counter > self.AXES_UPDATE_RATE_COUNTER_LIMIT:
                        data_obj = {"type": "COORDS", "focus": self.focus_score, "restoration": self.restoration_score, "features": list(sample[1:])}
                        self.axesInterface.notifyAll(data_obj)
                        self.axes_counter = 0
            
        except:
            logging.warn("Processing - Could not calculate Axes Scores")
          
    def load_models(self, features):
        feature_stats = {}
        for feature in features:
            try:
                model_path = os.path.join(base_path,"Models")
                name_string = self.subject_name + "_" + feature 
                path = max([os.path.join(model_path,name) for name in os.listdir(model_path) if name_string in name], key=os.path.getctime)
                model_file = open( path, "rb" ) 
                feature_stats[feature] = pickle.load(model_file)
                model_file.close()
                logging.info("Processing - Loaded model for %s. Mean %.2f, Std %.2f" 
                             % (feature, feature_stats[feature].mean(), np.sqrt(feature_stats[feature].variance())))
            except:
                logging.warn("Processing - Could not load model from file. Create new model for %s" % feature)
                feature_stats[feature] = livestats.LiveStats([0.10, 0.5, 0.90])
        return feature_stats
            
    def save_models(self, features, feature_stats):
        for feature in features:
            try:
                current_time = datetime.datetime.now().strftime("%Y%m%d_%I%M%S")
                path = base_path + "/Models/" + self.subject_name + "_" + feature + "_" + current_time +".p"
                model_file = open( path, "wb" )
                pickle.dump(feature_stats[feature],  model_file)
                model_file.close()
                logging.info("Processing - Saved model for %s. Mean %.2f, Std %.2f" 
                             % (feature, feature_stats[feature].mean(), np.sqrt(feature_stats[feature].variance())))
            except:
                logging.error("Processing - Could not save model for %s" % feature)    
                
                
def main(subject_name):
    # Edit here data collection path
    DATA_PATH = "./CollectedData/Study1"
    
    # Edit here port for web interface
    AXES_INTERFACE_PORT = 12348
    
    # Edit here port to connect to the Sensor Collector Service
    PROCESSING_SERVER_IP = "127.0.0.1"
    PROCESSING_SERVER_PORT = 12346
    
    print('------------------------------------------')
    print('Start Real-time Signal Processing Server..')
    
    # logging to file
    current_time = datetime.datetime.now().strftime("%Y%m%d_%I%M%S")
    logfilename = "log/SignalProcessingServer_"+subject_name+"_"+current_time+".log"
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M', filename = logfilename)
    
    # set up logging to console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%m-%d %H:%M')
    console.setFormatter(formatter)
    logging.getLogger("").addHandler(console)

    axesFactory = AxesInterfaceFactory(u"ws://127.0.0.1:%s" % AXES_INTERFACE_PORT)
    reactor.listenTCP(AXES_INTERFACE_PORT, axesFactory)
    
    writeLock = WriteToLogLock(reactor, 0)
    writeLock.unlock_writing_to_log_file()
    processingLogger = DataLogger(os.path.join(DATA_PATH, subject_name), "PROCESSED_", ProcessedSample._fields, writeLock)
    processingFactory = ProcessingFactory(axesFactory, subject_name)
    processingFactory.set_data_logger(processingLogger)
    reactor.listenTCP(PROCESSING_SERVER_PORT, processingFactory)
    reactor.run()
    processingLogger.close_log_file()
    
if __name__ == '__main__':
    command_args = parse_commandline_arguments()
    main(command_args.subject_name)

        
    