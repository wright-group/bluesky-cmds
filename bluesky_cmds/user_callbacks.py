# user callbacks file  
# following class is incorporated into the PlotCallback class which is used
# in the zmq_dispatcher.  Thus it uses the plot portion of bluesky_cmds  to insert extra
# init, start, stop, event, and descriptor processes, avoiding any further zmq dispatcher subscriptions.
# This was deemed suitable because additional processing for
# data acqusitions would likely occur from the console operating the laser system
# and not from some remote access.  The class can also operate on the wt5 data file instead
# of the (Bluesky) docs, although one might have to wait until the data file is definitely
# updated, which might take time, and require some method to know that it in fact
# has updated.


# Recommendations and Points:

# one should incorporate a logger on init to test and report on the methods' success at launch of
# bluesky_cmds, as well as point out they are active

# These methods are followed at the **end** of the Plot callback process.  It may be
# important to have a separate set of methods **before** any plotting occurs, or to modify
# the plot script to move the calls to these methods at some time where users can conclude
# they are most satisfactory **within** the plot processing.

# You may also want to have try, except routines and report on those if they fail, will help
# validate callbacks are working as they should, and perhaps allow the other portion of 
# bluesky-cmds to proceed even if they do fail.

# Create methods for validating an updated wt5, validating any Clients specially used here are working,
# etc. here.  Call these in the Callbacks below as needed.

# recommend parsing text generated during callbacks into a text file that should get appended to 
# a wt data file at the stop callback.  It might be good to read this script as text and put it into
# the parsed text, in order to keep a record of it.  It can also be written to a separate text file
# in the data folder.


# import modules here as needed.  Examples include : time, WrightTools, yaqc, bluesky_queueserver_api

import sys
#import os
#import pathlib
#import WrightTools as wt
#import time

if sys.platform:
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class UserCallbacks():
    def init(self):
        # User-defined process for initialization at time of zmq-dispatcher subscription 
        # of _plot.   This occurs at launch of bluesky-cmds.  Cannot use docs.
        #print("User callback initialization complete")        
        pass

    def start(self, doc):
        # User-defined process for the start of the acquisition here.  
        
        # sample code for finding the wt5 data folder for the current run (see wt5 in bluesky-in-a-box)
        '''
        time.sleep(0.5)
        timestamp = wt.kit.TimeStamp(self.start_doc["time"])
        path_parts = []
        path_parts.append(timestamp.path)
        path_parts.append(self.start_doc.get("plan_name"))
        path_parts.append(self.start_doc.get("Name"))
        path_parts.append(self.start_doc.get("uid")[:8])
        dirname = " ".join(x for x in path_parts if x)
        self.run_dir = pathlib.Path("C:/Users/john/bluesky-cmds-data") / dirname
        # would be good to examine wt5 file size as reference to see if it is being updated
        '''
        #print("User start callback done")
        pass

    def descriptor(self, doc):
        # User-defined process for Bluesky descriptors here
        pass

    def event(self, doc):
        # User-defined process for Bluesky events here (This is most likely where code is entered)
        #print("User event callback done")
        pass

    def stop(self, doc):
        # User-defined process at stop of a run here
        #print("User stop callback done")
        pass
