# user callbacks file  
# following class is incorporated into the PlotCallback class which is used
# in the zmq_dispatcher.  Thus it uses the plot portion of bluesky_cmds  to insert extra
# start, stop, event, and descriptor processes, avoiding any further dispatchers.
# This was deemed suitable as it was considered that additional processing for
# data acqusitions would likely occur from the console operating the laser system
# and not from some remote access.  It can also operate on the wt5 data file instead
# of the docs, although one might have to wait until the data file is definitely
# updated, which might take time

# import modules here as needed.  Examples include : time, WrightTools, yaqc

class UserCallbacks():
    def start(self, doc):
        # User-defined process for the start of the acquisition here
        pass

    def descriptor(self, doc):
        # User-defined process for descriptors here
        pass

    def event(self, doc):
        # User-defined process for events here (This is most likely where code is entered)
        pass

    def stop(self, doc):
        # User-defined process for stopping a run here
        pass
