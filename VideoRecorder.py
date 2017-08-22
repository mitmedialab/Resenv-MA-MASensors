'''
Created on Mar 24, 2016

This script is a backup solution to store for post-hoc facial analysis
The code has some major problems as framerate cannot reach higher than 10fps
The stored video can also not be opened on any device. It need to be re-saved with quicktime
TODO: This script needs to be redone

@author: nanzhao@media.mit.edu
'''
import cv2
import numpy as np
import time
import logging

if __name__ == '__main__':
    name = time.ctime(time.time()).replace(" ","_").replace(":","_")
    cap = cv2.VideoCapture(1)
    logging.info("VideoRecorder - is now running")
    writer = cv2.VideoWriter()
    writer.open(name, cv2.VideoWriter_fourcc(*'mp4v'), 30.0, (int(cap.get(3)),int(cap.get(4))))
    
    
    
    while True:
        ret, frame = cap.read()
        #cv2.imshow('Window' ,frame)
        if ret: writer.write(frame) 
        if cv2.waitKey(1) & 0xFF == ord('q'): break
        
    writer.release()
    cap.release() 
    cv2.destroyAllWindows()