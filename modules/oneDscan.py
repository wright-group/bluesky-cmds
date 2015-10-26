### define ####################################################################

module_name = '1D SCAN'

### import ####################################################################

import sys
import time

import numpy as np

import matplotlib
matplotlib.pyplot.ioff()

import project.project_globals as g
import project.classes as pc
import project.widgets as pw

from PyQt4 import QtCore, QtGui
app = g.app.read()

import project.widgets as custom_widgets

import WrightTools as wt

### import hardware control ###################################################

import spectrometers.spectrometers as specs
MicroHR = specs.hardwares[0]
import delays.delays as delays
D1 = delays.hardwares[0]
D2 = delays.hardwares[1]
import opas.opas as opas
OPA1 = opas.hardwares[0]
OPA2 = opas.hardwares[1]
OPA3 = opas.hardwares[2]
import daq.daq as daq

### objects ###################################################################

# to do with communication between threads
fraction_complete = pc.Mutex()
go = pc.Busy()
going = pc.Busy()
pause = pc.Busy()
paused = pc.Busy()

# control objects
start = pc.Number(initial_value=39.25)
stop = pc.Number(initial_value=34)
npts = pc.Number(initial_value=20, decimals=0)
units = pc.Combo(['wn','nm','eV','meV','ps','mm'])
axis = pc.Combo(['Mono','OPA1','OPA2','OPA3','D1','D2','OPA1_grating','OPA1_bbo','OPA1_mixer',
'OPA2_grating','OPA2_bbo','OPA2_mixer','OPA3_grating','OPA3_bbo','OPA3_mixer'])
coscan_mono = pc.Bool()
mono_formula = pc.String()
### scan object ###############################################################

class scan(QtCore.QObject):
    update_ui = QtCore.pyqtSignal()
    done = QtCore.pyqtSignal()
    
    @QtCore.pyqtSlot(list)
    def run(self, inputs):
        
        # unpack inputs -------------------------------------------------------
        
        scan_dictionary = inputs[0]
        daq_widget = inputs[1]
        gui = inputs[2]

        ok_go = True        
        
        #proper units check
        if axis.read_index() < 4:
            if units.read_index() > 3:
                print "Units don't make sense."
                ok_go = False
        elif axis.read_index() < 6:
            if units.read_index() < 4:
                print "Units don't make sense."
                ok_go = False
        else:
            if not units.read() == 'mm':
                print "Units don't make sense."
                ok_go = False
        
        destinations = np.linspace(start.read(), stop.read(), npts.read())
        
        # startup -------------------------------------------------------------

        g.module_control.write(True)
        going.write(True)
        fraction_complete.write(0.)
        g.logger.log('info', '1D begun - axis = ' +axis.read(), '')

        # scan ----------------------------------------------------------------
        scan_axes = ['wm','w1','w2','w3','d1','d2','w1_grating','w1_bbo','w1_mixer',
                     'w2_grating','w2_bbo','w2_mixer','w3_grating','w3_bbo','w3_mixer']
        a = axis.read_index()
        # initialize scan in daq
        daq.control.initialize_scan(daq_widget, scan_origin=module_name, scan_axes=scan_axes[a], fit=False)
        daq.gui.set_slice_xlim(start.read(), stop.read())
        daq.control.index_slice(col=scan_axes[a])
        
        hws = [MicroHR,OPA1,OPA2,OPA3,D1,D2]        
        try:
        # do loop
            if ok_go:
                break_scan = False
                idx = 0
                for i in range(len(destinations)):
                    if a<=5:
                        hws[axis.read_index()].set_position(destinations[i],units.read())
                        if 1<=a<=3 and coscan_mono.read():
                            MicroHR.set_position(destinations[i],units.read())
                    else:
                        m_index = a%3
                        opa_index = a/3-1
                        m_array = [-1,-1,-1]
                        m_array[m_index] = destinations[i]
                        hws[opa_index].q.push('set_motors',m_array)
                        
                    g.hardware_waits.wait()            
                    # read from daq
                    daq.control.acquire()
                    daq.control.wait_until_daq_done()
                    # update
                    idx += 1
                    fraction_complete.write(float(idx)/float(npts.read()))
                    self.update_ui.emit()
                    if not self.check_continue():
                        break_scan = True
                    if break_scan:
                        break
        except:
            print "I failed. At least I tried."
        #end-------------------------------------------------------------------

        fraction_complete.write(1.)    
        going.write(False)
        g.module_control.write(False)
        g.logger.log('info', '1D Scan done', '1D scan of '+ str(axis.read())+' complete')
        self.update_ui.emit()
        self.done.emit()
        
    def check_continue(self):
        '''
        you should put this method into your scan loop wherever you want to check 
        for pause or stop commands from the main program
        
        at the very least this method MUST go into your innermost loop
        
        for loops, use it as follows: if not self.check_continue(): break
        '''
        while pause.read(): 
            paused.write(True)
            pause.wait_for_update()
        paused.write(False)
        return go.read()
        
# scan object exists in the shared scan thread   
scan_obj = scan()
scan_thread = g.scan_thread.read()
scan_obj.moveToThread(scan_thread)
 
### gui #######################################################################

class gui(QtCore.QObject):

    def __init__(self):
        QtCore.QObject.__init__(self)
        scan_obj.update_ui.connect(self.update)
        self.create_frame()
        self.create_advanced_frame()
        self.show_frame()  # check once at startup
        g.shutdown.read().connect(self.stop)
        scan_obj.done.connect(self.plot)
        
    def create_frame(self):
        layout = QtGui.QVBoxLayout()
        layout.setMargin(5)
        
        # input table
        input_table = pw.InputTable()
        input_table.add('Start', start)
        input_table.add('Stop', stop)
        input_table.add('Number', npts)
        input_table.add('Scan Axis', axis)
        input_table.add('Scan Units',units)
        input_table.add('Scan Mono too?', coscan_mono)
        input_table.add('Mono Formula (TBD)', mono_formula)
        layout.addWidget(input_table)
        
        # daq widget
        self.daq_widget = daq.Widget()
        layout.addWidget(self.daq_widget)
        
        # go button
        self.go_button = custom_widgets.module_go_button()
        self.go_button.give_launch_scan_method(self.launch_scan)
        self.go_button.give_stop_scan_method(self.stop)  
        self.go_button.give_scan_complete_signal(scan_obj.done)
        self.go_button.give_pause_objects(pause, paused)
        
        layout.addWidget(self.go_button)
        
        layout.addStretch(1)
        
        self.frame = QtGui.QWidget()
        self.frame.setLayout(layout)
        
        g.module_widget.add_child(self.frame)
        g.module_combobox.add_module(module_name, self.show_frame)

    def create_advanced_frame(self):
        layout = QtGui.QVBoxLayout()
        layout.setMargin(5)

        self.advanced_frame = QtGui.QWidget()   
        self.advanced_frame.setLayout(layout)
        
        g.module_advanced_widget.add_child(self.advanced_frame)

    def show_frame(self):
        self.frame.hide()
        self.advanced_frame.hide()
        if g.module_combobox.get_text() == module_name:
            self.frame.show()
            self.advanced_frame.show()

    def launch_scan(self):        
        go.write(True)
        print 'running'
        scan_dictionary = {}
        inputs = [scan_dictionary, self.daq_widget, self]
        QtCore.QMetaObject.invokeMethod(scan_obj, 'run', QtCore.Qt.QueuedConnection, QtCore.Q_ARG(list, inputs))    
        g.progress_bar.begin_new_scan_timer()
        
    def plot(self):
        print 'plotting'
        data_path = daq.data_path.read()
        data_obj = wt.data.from_PyCMDS(data_path)
        artist = wt.artists.mpl_1D(data_obj)
        fname = data_path.replace('.data', '')
        artist.plot(fname=fname, autosave=True)
        
    def update(self):
        g.progress_bar.set_fraction(fraction_complete.read())
              
    def stop(self):
        print 'stopping'
        go.write(False)
        while going.read(): going.wait_for_update()
        print 'stopped'
        
gui = gui()