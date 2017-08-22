'''
@author: nanzhao@media.mit.edu
'''

import argparse
import os
from SensorCollectionServer import main, parse_commandline_arguments
 
if __name__ == '__main__':

    command_args = parse_commandline_arguments()
    main(command_args)
