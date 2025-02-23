# user callbacks file  
# following class is incorporated into the PlotCallback class which is used
# in the zmq_dispatcher.  Thus it uses the plot portion of bluesky_cmds  to insert extra
# init, start, stop, event, and descriptor processes, avoiding any further zmq dispatcher subscriptions.
# This was deemed suitable as it was considered that additional processing for
# data acqusitions would likely occur from the console operating the laser system
# and not from some remote access.  The class can also operate on the wt5 data file instead
# of the docs, although one might have to wait until the data file is definitely
# updated, which might take time, and require some method to know that it in fact
# has updated.

# import modules here as needed.  Examples include : time, WrightTools, yaqc
# one should incorporate a logger on init to test and report on the methods' success at launch of
# bluesky_cmds, as well as point out they are active

# These methods are followed at the **end** of the Plot callback process.  It may be
# important to have a separate set of methods **before** any plotting occurs, or to modify
# the plot script to move the calls to these methods at some time where users can conclude
# they are most satisfactory **within** the plot processing.

import yaqc
import time

c=yaqc.Client(38996)

class UserCallbacks():
    def init(self):
        # User-defined process for initialization at time of zmq-dispatcher subscription 
        # of _plot.   Cannot use docs.
        print("initialization done")
        pass

    def start(self, doc):
        # User-defined process for the start of the acquisition here
        print("start done")
        pass

    def descriptor(self, doc):
        # User-defined process for Bluesky descriptors here
        pass

    def event(self, doc):
        # User-defined process for Bluesky events here (This is most likely where code is entered)
        id=c.get_measured()['measurement_id']
        idn=id
        while idn==id:
            data=c.get_measured()
            idn=data['measurement_id']
            
            time.sleep(0.1)
        meas=data['random_walk']
        print(meas)
        pass

    def stop(self, doc):
        # User-defined process at stop of a run here
        print("stop done")
        pass
