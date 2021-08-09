#!/usr/bin/python3
# Author: Tom Daniels
# File: utility.py
# License: Mozilla Public License v2.0. See LICENSE file included with repository for more details

#############
## Imports ##
#############
import datetime

###############
## Functions ##
###############
def from_epoch(epoch):
    """
    Purpose: Converts computer things to human things
    @param epoch (str or int) - the epoch time as a string or int
    @return (datetime) - the time represented by the epoch time, but
            actually readable
    """
    return datetime.datetime.fromtimestamp(epoch)
