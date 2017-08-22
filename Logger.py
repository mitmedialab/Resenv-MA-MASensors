'''
Created on Mar 8, 2016

@author: nanzhao@media.mit.edu, azaria@media.mit.edu
'''

import os
import datetime
import json
from twisted.protocols import basic


from autobahn.twisted.websocket import WebSocketServerProtocol, WebSocketServerFactory


class LoggingWebsocketControll(WebSocketServerProtocol):

    def onConnect(self, request):
        print("LoggingWebsocketControll: Received Contol Connection")

    def onOpen(self):
        print("LoggingWebsocketControll: WebSocket connection open.")

    def onMessage(self, payload, isBinary):
        print("LoggingWebsocketControll: Received Command - %s" % (payload))
        command = json.loads(payload)
        self.handle_command(command)
            
    def onClose(self, wasClean, code, reason):
        print("LoggingWebsocketControll: WebSocket connection closed: {0}".format(reason))
        
    def handle_command(self, command):
        dispatcher = {"LOG": self.handle_log_command,
                      "STOP_LOG": self.handle_stop_log_command}
        dispatcher[command["type"]](command)

    def handle_stop_log_command(self,command):
        self.logger_container.write_to_log_lock.lock_writing_to_log_file()
        
    def handle_log_command(self, command):        
        log_files_prefix = "%s_%s" % (command["subject"],command["name"])
        self.logger_container.write_to_log_lock.lock_writing_to_log_file()
        self.logger_container.new_logging_session(log_files_prefix)
        self.logger_container.write_to_log_lock.unlock_writing_to_log_file()
        
    def set_logger_container(self, logger_container):
        self.logger_container = logger_container
    
    
class LoggingWebsocketControlFactory(WebSocketServerFactory):
        def buildProtocol(self, addr):
            proto = LoggingWebsocketControll()
            proto.set_logger_container(self.logger_container) # This part will be set externally by the user.
            proto.factory = self
            return proto


class LoggingUserControl(basic.LineReceiver):
    # This part sets the delimiter to be the one of the OS in which the server is running.
    from os import linesep as delimiter

    def connectionMade(self):
        self.transport.write('LoggingUserControl: Initializing Logging to OFF - Send ON to start Logging \n')
        
    def set_write_to_log_lock(self, lock):
        self.write_to_log_lock = lock

    def lineReceived(self, line):
        self.transport.write("LoggingUserControl: Received user request - " + line)
        if "ON" in line: 
            self.write_to_log_lock.unlock_writing_to_log_file()
            self.transport.write("LoggingUserControl: Logging enabled \n")
            
        if "OFF" in line: 
            self.write_to_log_lock.lock_writing_to_log_file()
            self.transport.write("LoggingUserControl: Logging disabled \n")        
        
class WriteToLogLock(object):
    def __init__(self, reactor, period):
        self.is_write_locked = True
        self.reactor = reactor
        self.period = period
                    
    def unlock_writing_to_log_file(self):
        def lock_writing_to_log_file_callback(): 
            self.is_write_locked = True
            print "Logging is paused after period timeout"
        self.is_write_locked = False
        if self.period != 0:
            self.reactor.callLater(self.period, lock_writing_to_log_file_callback)
    
    def lock_writing_to_log_file(self):
        self.is_write_locked = True
        


class DataLogger(object):
    def __init__(self, base_path, file_name, columns_list, write_to_log_lock):
        current_time = datetime.datetime.now().strftime("%Y%m%d_%I%M%S")
        self.create_directory_if_does_not_exist(base_path, current_time)
        self.path = os.path.join(base_path + "_" + current_time, file_name + "_" + current_time)
        self.log_file = open(self.path, "wa")
        self.log_file.write(",".join(columns_list))
        self.log_file.write("\r\n")
        print "Logging incoming data into %s " % self.path
        
        self.lock = write_to_log_lock
        self.columns_list = columns_list
                
    def create_directory_if_does_not_exist(self, base_path, current_time):
        if os.path.exists(base_path + "_" + current_time): return
        os.makedirs(base_path + "_" + current_time)
        
    def write_tuple_to_log_file(self, values_in_tuple, show_on_screen=False):
        tuple_to_list = [str(value) for value in values_in_tuple]
        self.write_list_to_log_file(tuple_to_list, show_on_screen)
        
    def write_dict_to_log_file(self, values_in_dictionary, show_on_screen=False):
        dict_to_list = [values_in_dictionary[key] for key in self.columns_list]
        self.write_list_to_log_file(dict_to_list, show_on_screen)
        
    def write_list_to_log_file(self, values_in_list, show_on_screen=False):
        if self.lock.is_write_locked:
            return
        
        line_to_write = ",".join(values_in_list) + "\r\n"

        self.log_file.write(line_to_write)
        
        if show_on_screen:
            print line_to_write
            
    def write_line(self, line):
        if self.lock.is_write_locked:
            return
        self.log_file.write(line + "\r\n") 
    
    def close_log_file(self):
        self.log_file.flush()
        self.log_file.close()
        
        
if __name__ == "__main__":
    print "hey!"
