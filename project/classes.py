### import ####################################################################


import time

import numpy as np

from PyQt4 import QtGui, QtCore

import project_globals as g

import WrightTools.units as units


### gui items #################################################################


class Value(QtCore.QMutex):

    def __init__(self, initial_value=None):
        '''
        basic QMutex object to hold a single object in a thread-safe way
        '''
        QtCore.QMutex.__init__(self)
        self.value = initial_value

    def read(self):
        return self.value

    def write(self, value):
        '''
        bool value
        '''
        self.lock()
        self.value = value
        self.unlock()


class PyCMDS_Object(QtCore.QObject):
    updated = QtCore.pyqtSignal()
    disabled = False

    def __init__(self, initial_value=None,
                 ini=None, section='', option='',
                 import_from_ini=False, save_to_ini_at_shutdown=False):
        QtCore.QObject.__init__(self)
        self.has_widget = False
        self.tool_tip = ''
        self.value = Value(initial_value)
        # ini
        if ini:
            self.ini = ini
            self.section = section
            self.option = option
        else:
            self.has_ini = False
        if import_from_ini:
            self.get_saved()
        if save_to_ini_at_shutdown:
            g.shutdown.add_method(self.save)

    def read(self):
        return self.value.read()

    def write(self, value):
        self.value.write(value)
        self.updated.emit()

    def get_saved(self):
        if self.has_ini:
            self.value.write(self.ini.read(self.section, self.option))
        return self.value.read()
        self.updated.emit()

    def save(self, value=None):
        if value is not None:
            self.value.write(value)
        if self.has_ini:
            self.ini.write(self.section, self.option, self.value.read())

    def set_disabled(self, disabled):
        self.disabled = disabled
        if self.has_widget:
            self.widget.setDisabled(self.disabled)

    def set_tool_tip(self, tool_tip):
        self.tool_tip = tool_tip
        if self.has_widget:
            self.widget.setToolTip(self.tool_tip)


class Bool(PyCMDS_Object):
    '''
    holds 'value' (bool) - the state of the checkbox
    
    use read method to access
    '''
    
    def __init__(self, initial_value = False, 
                 ini = None, section='', option='',
                 import_from_ini = False, save_to_ini_at_shutdown = False):
        PyCMDS_Object.__init__(self, initial_value = False, 
                               ini = None, section='', option='',
                               import_from_ini = False, 
                               save_to_ini_at_shutdown = False)
    def give_control(self, control_widget):
        self.widget = control_widget
        #set
        self.widget.setChecked(self.value)   
        #connect signals and slots
        self.updated.connect(lambda: self.widget.setChecked(self.value))
        self.widget.stateChanged.connect(lambda: self.write(self.widget.checkState()))
        #finish
        self.widget.setToolTip(self.tool_tip)
        self.widget.setDisabled(self.disabled)
        self.has_widget = True


class Combo(PyCMDS_Object):
    '''
    holds 'value' (str) - the combobox displayed text
    
    holds 'allowed_values' (list of str)
    '''
    updated = QtCore.pyqtSignal()
    disabled = False
    def __init__(self, allowed_values, initial_value = None, ini = None, import_from_ini = False, save_to_ini_at_shutdown = False):
        gui_object.__init__(self, initial_value = initial_value, ini_inputs = ini, import_from_ini = import_from_ini, save_to_ini_at_shutdown = save_to_ini_at_shutdown)
        self.allowed_values = allowed_values
    def give_control(self, control_widget):
        self.widget = control_widget
        #fill out items
        self.widget.addItems(self.allowed_values)
        self.widget.setCurrentIndex(self.allowed_values.index(self.read()))       
        #connect signals and slots
        self.updated.connect(lambda: self.widget.setCurrentIndex(self.allowed_values.index(self.read())))
        self.widget.currentIndexChanged.connect(lambda: self.write(self.widget.currentText()))
        self.widget.setToolTip(self.tool_tip)
        self.widget.setDisabled(self.disabled)
        self.has_widget = True


class Filepath(PyCMDS_Object):
    '''
    holds 'value' (str) - the filepath as a string
    '''
    def __init__(self, initial_value = None, ini = None, import_from_ini = False, save_to_ini_at_shutdown = False):
        gui_object.__init__(self, initial_value = initial_value, ini_inputs = ini, import_from_ini = import_from_ini, save_to_ini_at_shutdown = save_to_ini_at_shutdown)
    def give_control(self, control_widget):
        self.widget = control_widget
        '''
        #fill out items
        self.widget.addItems(self.allowed_values)
        self.widget.setCurrentIndex(self.allowed_values.index(self.read()))       
        #connect signals and slots
        self.updated.connect(lambda: self.widget.setCurrentIndex(self.allowed_values.index(self.read())))
        self.widget.currentIndexChanged.connect(lambda: self.write(self.widget.currentText()))
        '''
        self.widget.setToolTip(self.tool_tip)
        self.widget.setDisabled(self.disabled)
        self.has_widget = True
    def give_button(self, button_widget):
        self.button = button_widget

          
class Number(PyCMDS_Object):
    '''
    holds 'value' (bool) - the state of the checkbox
    
    use read method to access
    '''
    
    def __init__(self, initial_value = np.nan, 
                 ini = None, section='', option='',
                 import_from_ini = False, save_to_ini_at_shutdown = False,
                 units = None, 
                 min_value = -1000000., 
                 max_value = 1000000.,
                 single_step = 1.,
                 decimals = 2):
        PyCMDS_Object.__init__(self, initial_value = False, 
                               ini = None, section='', option='',
                               import_from_ini = False, 
                               save_to_ini_at_shutdown = False)
        self.type = 'number'
        self.display = True
        self.units = units
        self.min_value = min_value
        self.max_value = max_value
        self.single_step = single_step
        self.decimals = decimals
        self.units_kind = 'nm'

    def set_limits(self, min_value = None, max_value = None, single_step =   None, decimals = None):
        limits = [self.min_value, self.max_value, self.single_step, self.decimals]
        inputs = [min_value, max_value, single_step, decimals]
        widget_methods = ['setMinimum', 'setMaximum', 'setSingleStep', 'setDecimals']
        for i in range(len(limits)):
            if not inputs[i] == None:
                limits[i] = inputs[i]
                if self.has_widget: getattr(self.widget, widget_methods[i])(limits[i])    
                
    def give_control(self, control_widget):
        self.widget = control_widget
        #set values
        self.widget.setDecimals(self.decimals)
        self.widget.setMaximum(self.max_value)
        self.widget.setMinimum(self.min_value)
        self.widget.setSingleStep(self.single_step)
        self.widget.setValue(self.value.read())
        #connect signals and slots
        self.updated.connect(lambda: self.widget.setValue(self.value.read()))
        self.widget.editingFinished.connect(lambda: self.write(self.widget.value()))
        #finish
        self.widget.setToolTip(self.tool_tip)
        self.has_widget = True
        
    def give_units_combo(self, units_combo_widget):
        self.units_widget = units_combo_widget
        if self.units_kind == 'color':
            self.units_widget.addItems(['nm', 'wn', 'eV'])
        elif self.units_kind == 'delay':
            self.units_widget.addItems(['fs', 'ps'])

  
class String(PyCMDS_Object):
    '''
    holds 'value' (string)
    '''
    def __init__(self, initial_value = None, ini = None, import_from_ini = False, save_to_ini_at_shutdown = False):
        gui_object.__init__(self, initial_value = initial_value, ini_inputs = ini, import_from_ini = import_from_ini, save_to_ini_at_shutdown = save_to_ini_at_shutdown)
    def give_control(self, control_widget):
        self.widget = control_widget
        #fill out items
        self.widget.setText(self.value)       
        #connect signals and slots
        self.updated.connect(lambda: self.widget.setText(self.value))
        self.widget.editingFinished.connect(lambda: self.write(self.widget.text()))
        self.widget.setToolTip(self.tool_tip)
        self.has_widget = True    
    
    
### hardware ##################################################################


class Busy(QtCore.QMutex):

    def __init__(self):
        '''
        QMutex object to communicate between threads that need to wait \n
        while busy.read(): busy.wait_for_update()
        '''
        QtCore.QMutex.__init__(self)
        self.WaitCondition = QtCore.QWaitCondition()
        self.value = False

    def read(self):
        return self.value

    def write(self, value):
        '''
        bool value
        '''
        self.lock()
        self.value = value
        self.WaitCondition.wakeAll()
        self.unlock()

    def wait_for_update(self, timeout=5000):
        '''
        wait in calling thread for any thread to call 'write' method \n
        int timeout in milliseconds
        '''
        if self.value:
            return self.WaitCondition.wait(self, msecs=timeout)


class Address(QtCore.QObject):
    update_ui = QtCore.pyqtSignal()
    queue_emptied = QtCore.pyqtSignal()
    
    def __init__(self, enqueued_obj, busy_obj, name, ctrl_class):
        '''
        do not override __init__ or dequeue unless you really know what you are doing
        '''
        QtCore.QObject.__init__(self)
        self.enqueued = enqueued_obj
        self.busy = busy_obj
        self.name = name
        self.ctrl_class = ctrl_class
  
    @QtCore.pyqtSlot(str, list)
    def dequeue(self, method, inputs):
        '''
        accepts queued signals from 'queue' (address using q method) \n
        string method, list inputs
        '''
        self.update_ui.emit()
        if g.debug.read():
            print self.name, 'dequeue:', method, inputs
        # execute method
        getattr(self, str(method))(inputs)  # method passed as qstring
        # remove method from enqueued
        self.enqueued.pop()
        if not self.enqueued.read():
            self.queue_emptied.emit()
            self.check_busy([])
            self.update_ui.emit()

    def check_busy(self, inputs):
        '''
        decides if the hardware is done and handles writing of 'busy' to False
        '''
        # must always write busy whether answer is True or False
        if self.ctrl.is_busy():
            time.sleep(0.01) # don't loop like crazy
            self.busy.write(True)
        elif self.enqueued.read():
            time.sleep(0.1) # don't loop like crazy
            self.busy.write(True)
        else:
            self.busy.write(False)

    def get_position(self, inputs):
        self.ctrl.get_position()
        self.update_ui.emit()

    def poll(self, inputs):
        '''
        polling only gets enqueued by Hardware when not in module control
        '''
        self.get_position([])
        self.is_busy([])

    def initialize(self, inputs):
        self.ctrl = self.ctrl_class(inputs)
        if g.debug.read():
            print self.name, 'initialization complete'

    def set_position(self, inputs):
        self.ctrl.set_position(inputs[0])
        self.get_position([])

    def close(self, inputs):
        self.ctrl.close()


class Enqueued(QtCore.QMutex):

    def __init__(self):
        '''
        holds list of enqueued options
        '''
        QtCore.QMutex.__init__(self)
        self.value = []

    def read(self):
        return self.value

    def push(self, value):
        self.lock()
        self.value.append(value)
        self.unlock()

    def pop(self):
        self.lock()
        self.value = self.value[1:]
        self.unlock()


class Q:

    def __init__(self, enqueued, busy, address):
        self.enqueued = enqueued
        self.busy = busy
        self.address = address
        self.queue = QtCore.QMetaObject()

    def push(self, method, inputs=[]):
        self.enqueued.push([method, time.time()])
        self.busy.write(True)
        # send Qt SIGNAL to address thread
        self.queue.invokeMethod(self.address,
                                'dequeue',
                                QtCore.Qt.QueuedConnection,
                                QtCore.Q_ARG(str, method),
                                QtCore.Q_ARG(list, inputs))


class Hardware(QtCore.QObject):
    update_ui = QtCore.pyqtSignal()

    def __init__(self, control_class, control_arguments, address_class=Address,
                 name='', initialize_hardware=True):
        '''
        container for all objects relating to a single piece
        of addressable hardware
        '''
        QtCore.QObject.__init__(self)
        self.name = name
        # create mutexes
        # BASED ON SOMETHING YET TO BE WRITTEN INSIDE OF CONTROL CLASS
        self._create_mutexes()
        # create objects
        self.thread = QtCore.QThread()
        self.enqueued = Enqueued()
        self.busy = Busy()
        self.address = address_class(self.enqueued, self.busy,
                                     name, control_class)
        self.q = Q(self.enqueued, self.busy, self.address)
        # start thread
        self.address.moveToThread(self.thread)
        self.thread.start()
        # connect to address object signals
        self.address.update_ui.connect(self.update)
        # initialize hardware
        self.q.push('initialize', control_arguments)
        # integrate close into PyCMDS shutdown
        self.shutdown_timeout = 30  # seconds
        g.shutdown.add_method(self.close)

    def close(self):
        # begin hardware shutdown
        self.q.push('close')
        # wait for hardware shutdown to complete
        start_time = time.time()
        while self.busy.read():
            if time.time()-start_time < self.shutdown_timeout:
                if not self.enqueued.read():
                    self.q.push('check_busy')
                self.busy.wait_for_update()
            else:
                g.logger.log('warning',
                             'Wait until done timed out',
                             self.name)
                break
        # quit thread
        self.thread.exit()
        self.thread.quit()

    def get_position(self):
        return self.current_position.read()

    def is_valid(self):
        # placeholder
        return True

    def poll(self, force=False):
        if force:
            self.q.push('poll')
            self.get_position()
        elif not g.module_control.read():
            self.q.push('poll')
            self.get_position()

    def set_position(self, destination):
        # must launch comove
        #   sent - destination
        #   recieved - busy object to be waited on once
        self.q.push('set_position', [destination])

    def update(self):
        self.update_ui.emit()

    def _create_mutexes(self):
        self.current_position = Number()