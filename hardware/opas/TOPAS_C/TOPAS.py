### import ####################################################################


import os
import time
import copy
import collections

import numpy as np

from types import FunctionType
from functools import wraps

from PyQt4 import QtGui, QtCore

import ctypes
from ctypes import *

import WrightTools as wt
import WrightTools.units as wt_units
from PyCMDS.hardware.opas import BaseOPA

import project.classes as pc
import project.widgets as pw
import project.project_globals as g
from project.ini_handler import Ini
main_dir = g.main_dir.read()
#ini = Ini(os.path.join(main_dir, 'hardware', 'opas',
#                                 'TOPAS_C',
#                                 'TOPAS.ini'))
                                 
                                 
### define ####################################################################
              
curve_indicies = {'Base': 1,
                  'Mixer 1': 2,
                  'Mixer 2': 3,
                  'Mixer 3': 4}

### OPA object ################################################################


class TOPAS(BaseOPA):

    def __init__(self):
        self.native_units = 'nm'
        # mutex attributes
        self.limits = pc.NumberLimits(units=self.native_units)
        self.current_position = pc.Number(name='Color', initial_value=1300.,
                                          limits=self.limits,
                                          units=self.native_units, display=True,
                                          set_method='set_position')
        self.offset = pc.Number(initial_value=0, units=self.native_units, display=True)
        self.shutter_position = pc.Bool(name='Shutter',
                                        display=True, set_method='set_shutter')
        # objects to be sent to PyCMDS
        self.exposed = [self.current_position, self.shutter_position]
        self.recorded = collections.OrderedDict()
        self.motor_names = ['Crystal_1', 'Delay_1', 'Crystal_2', 'Delay_2', 'Mixer_1', 'Mixer_2', 'Mixer_3']
        # finish
        self.gui = GUI(self)
        self.auto_tune = AutoTune(self)
        self.initialized = pc.Bool()
        
    def _home_motors(self, motor_indexes):
        motor_indexes = list(motor_indexes)
        section = 'OPA' + str(self.index)
        # close shutter
        original_shutter = self.shutter_position.read()
        self.set_shutter([False])
        # record current positions
        original_positions = []
        for motor_index in motor_indexes:
            error, current_position = self.api.get_motor_position(motor_index)
            original_positions.append(current_position)
        # send motors to left reference switch --------------------------------
        # set all max, current positions to spoof values
        overflow = 8388607
        for motor_index in motor_indexes:
            self.api.set_motor_positions_range(motor_index, 0, overflow)
            self.api.set_motor_position(motor_index, overflow)
        # send motors towards zero
        for motor_index in motor_indexes:
            self.api.start_motor_motion(motor_index, 0)
        # wait for motors to hit left reference switch
        motor_indexes_not_homed = copy.copy(motor_indexes)
        while len(motor_indexes_not_homed) > 0:
            for motor_index in motor_indexes_not_homed:
                time.sleep(0.1)
                error, left, right = self.api.get_reference_switch_status(motor_index)
                if left:
                    motor_indexes_not_homed.remove(motor_index)
                    # set counter to zero
                    self.api.set_motor_position(motor_index, 0)
        # send motors to 400 steps --------------------------------------------
        for motor_index in motor_indexes:
            self.api.start_motor_motion(motor_index, 400)
        self.wait_until_still()
        # send motors left reference switch slowly ----------------------------
        # set motor speed
        for motor_index in motor_indexes:
            min_velocity = ini.read(section, 'motor {} min velocity (us/s)'.format(motor_index))
            max_velocity = ini.read(section, 'motor {} max velocity (us/s)'.format(motor_index))
            acceleration = ini.read(section, 'motor {} acceleration (us/s^2)'.format(motor_index))
            error = self.api.set_speed_parameters(motor_index, min_velocity, int(max_velocity/2), acceleration)
        # set all max, current positions to spoof values
        for motor_index in motor_indexes:
            self.api.set_motor_positions_range(motor_index, 0, overflow)
            self.api.set_motor_position(motor_index, overflow)
        # send motors towards zero
        for motor_index in motor_indexes:
            self.api.start_motor_motion(motor_index, 0)
        # wait for motors to hit left reference switch
        motor_indexes_not_homed = copy.copy(motor_indexes)
        while len(motor_indexes_not_homed) > 0:
            for motor_index in motor_indexes_not_homed:
                time.sleep(0.1)
                error, left, right = self.api.get_reference_switch_status(motor_index)
                if left:
                    motor_indexes_not_homed.remove(motor_index)
                    # set counter to zero
                    self.api.set_motor_position(motor_index, 0)
        # send motors to 400 steps (which is now true zero) -------------------
        for motor_index in motor_indexes:
            self.api.start_motor_motion(motor_index, 400)
        self.wait_until_still()
        for motor_index in motor_indexes:
            self.api.set_motor_position(motor_index, 0)
        # finish --------------------------------------------------------------
        # set speed back to real values
        for motor_index in motor_indexes:
            min_velocity = ini.read(section, 'motor {} min velocity (us/s)'.format(motor_index))
            max_velocity = ini.read(section, 'motor {} max velocity (us/s)'.format(motor_index))
            acceleration = ini.read(section, 'motor {} acceleration (us/s^2)'.format(motor_index))
            error = self.api.set_speed_parameters(motor_index, min_velocity, max_velocity, acceleration)
        # set range back to real values
        for motor_index in motor_indexes:
            min_position = ini.read(section, 'motor {} min position (us)'.format(motor_index))
            max_position = ini.read(section, 'motor {} max position (us)'.format(motor_index))
            error = self.api.set_motor_positions_range(motor_index, min_position, max_position)
        # launch return motion
        for motor_index, position in zip(motor_indexes, original_positions):
            self.api.start_motor_motion(motor_index, position)
        # wait for motors to finish moving
        self.wait_until_still()
        # return shutter
        self.set_shutter([original_shutter])
        
    def _set_motors(self, motor_indexes, motor_destinations, wait=True):
        for motor_index, destination in zip(motor_indexes, motor_destinations):
            error, destination_steps = self.api.convert_position_to_steps(motor_index, destination)
            self.api.start_motor_motion(motor_index, destination_steps)
        if wait:
            self.wait_until_still()
        
    def close(self):
        self.api.set_shutter(False)
        self.api.close()
        
    def home_motor(self, inputs):
        motor_name = inputs[0]
        motor_index = self.motor_names.index(motor_name)
        self._home_motors([motor_index])
    
    def home_all(self, inputs=[]):
        self._home_motors(np.arange(len(self.motor_names)))

    def load_curve(self, inputs=[]):
        '''
        inputs can be none (so it loads current curves) 
        or ['curve type', filepath]
        '''
        # TODO: actually support external curve loading
        # write to TOPAS ini
        self.api.close()
        for curve_type, curve_path_mutex in self.curve_paths.items():
            curve_path = curve_path_mutex.read()            
            section = 'Optical Device'
            option = 'Curve ' + str(curve_indicies[curve_type])
            self.TOPAS_ini.write(section, option, curve_path)
            print section, option, curve_path
        self.api = TOPAS(self.TOPAS_ini_filepath)
        # update own curve object
        interaction = self.interaction_string_combo.read()
        crv_paths = [m.read() for m in self.curve_paths.values()]
        self.curve = wt.tuning.curve.from_TOPAS_crvs(crv_paths, 'TOPAS-C', interaction)
        # update limits
        min_nm = self.curve.colors.min()
        max_nm = self.curve.colors.max()
        self.limits.write(min_nm, max_nm, 'nm')
        # update position
        self.get_position()
        # save current interaction string
        ini.write('OPA%i'%self.index, 'current interaction string', interaction)
        
    def get_crv_paths(self):
        return [o.read() for o in self.curve_paths.values()]

    def get_points(self):
        return self.curve.colors

    def get_position(self):
        motor_indexes = [self.motor_names.index(n) for n in self.curve.get_motor_names(full=False)]
        motor_positions = [self.motor_positions.values()[i].read() for i in motor_indexes]
        position = self.curve.get_color(motor_positions, units='nm')        
        if not np.isnan(self.address.hardware.destination.read()):
            position = self.address.hardware.destination.read()
        self.current_position.write(position, 'nm')
        return position

    def get_motor_positions(self, inputs=[]):
        for motor_index, motor_mutex in enumerate(self.motor_positions.values()):
            error, position_steps = self.api.get_motor_position(motor_index)
            error, position = self.api.convert_position_to_units(motor_index, position_steps)
            motor_mutex.write(position)
    
    def get_speed_parameters(self, inputs):
        motor_index = inputs[0]
        error, min_speed, max_speed, acceleration = self.api._get_speed_parameters(motor_index)
        return [error, min_speed, max_speed, acceleration]

    def initialize(self, inputs, address):
        '''
        OPA initialization method. Inputs = [index]
        '''
        self.address = address
        self.index = inputs[0]
        self.serial_number = ini.read('OPA' + str(self.index), 'serial number')
        self.recorded['w%d'%self.index] = [self.current_position, 'nm', 1., str(self.index)]
        # load api 
        self.TOPAS_ini_filepath = os.path.join(g.main_dir.read(), 'hardware', 'opas', 'TOPAS_C', 'configuration', str(self.serial_number) + '.ini')
        self.api = TOPAS(self.TOPAS_ini_filepath)
        self.api.set_shutter(False)
        self.TOPAS_ini = Ini(self.TOPAS_ini_filepath)
        self.TOPAS_ini.return_raw = True
        # motor positions
        self.motor_positions = collections.OrderedDict()
        for motor_index, motor_name in enumerate(self.motor_names):
            error, min_position_steps, max_position_steps = self.api.get_motor_positions_range(motor_index)
            valid_position_steps = np.arange(min_position_steps, max_position_steps+1)
            valid_positions_units = [self.api.convert_position_to_units(motor_index, s)[1] for s in valid_position_steps]
            min_position = min(valid_positions_units)
            max_position = max(valid_positions_units)
            limits = pc.NumberLimits(min_position, max_position)
            number = pc.Number(initial_value=0, limits=limits, display=True, decimals=6)
            self.motor_positions[motor_name] = number
            self.recorded['w%d_'%self.index + motor_name] = [number, None, 1., motor_name]
        self.get_motor_positions()
        # tuning curves
        self.curve_paths = collections.OrderedDict()
        for curve_type in curve_indicies.keys():
            section = 'Optical Device'
            option = 'Curve ' + str(curve_indicies[curve_type])
            initial_value = self.TOPAS_ini.read(section, option)
            options = ['CRV (*.crv)']
            curve_filepath = pc.Filepath(initial_value=initial_value, options=options)
            curve_filepath.updated.connect(self.load_curve)
            self.curve_paths[curve_type] = curve_filepath
        # interaction string
        allowed_values = []
        for curve_path_mutex in self.curve_paths.values():
            with open(curve_path_mutex.read()) as crv:
                crv_lines = crv.readlines()
            for line in crv_lines:
                if 'NON' in line:
                    allowed_values.append(line.rstrip())
        self.interaction_string_combo = pc.Combo(allowed_values=allowed_values)
        current_value = ini.read('OPA%i'%self.index, 'current interaction string')
        self.interaction_string_combo.write(current_value)
        self.interaction_string_combo.updated.connect(self.load_curve)
        g.queue_control.disable_when_true(self.interaction_string_combo)
        self.load_curve()
        # finish
        self.get_position()
        self.initialized.write(True)
        self.address.initialized_signal.emit()       

    def is_busy(self):
        if self.api.open:
            error, still = self.api.are_all_motors_still()
            return not still
        else:
            return False

    def is_valid(self, destination):
        return True

    def set_offset(self, offset):
        pass

    def set_position(self, destination):
        # coerce destination to be within current tune range
        destination = np.clip(destination, self.curve.colors.min(), self.curve.colors.max())
        # get destinations from curve
        motor_names = self.curve.get_motor_names()
        motor_destinations = self.curve.get_motor_positions(destination, 'nm')
        # send command
        motor_indexes = [self.motor_names.index(n) for n in motor_names]
        self._set_motors(motor_indexes, motor_destinations)
        # finish
        self.get_position()
        
    def set_position_except(self, inputs):
        '''
        set position, except for motors that follow
        
        does not wait until still...
        '''
        destination = inputs[0]
        self.address.hardware.destination.write(destination)
        self.current_position.write(destination, 'nm')
        exceptions = inputs[1]  # list of integers
        motor_destinations = self.curve.get_motor_positions(destination, 'nm')
        motor_indexes = []
        motor_positions = []
        for i in [self.motor_names.index(n) for n in self.curve.get_motor_names()]:
            if i not in exceptions:
                motor_indexes.append(i)
                motor_positions.append(motor_destinations[i])
        self._set_motors(motor_indexes, motor_positions, wait=False)
        
    def set_motor(self, inputs):
        '''
        inputs [motor_name (str), destination (steps)]
        '''
        motor_name, destination = inputs
        motor_index = self.motor_names.index(motor_name)
        self._set_motors([motor_index], [destination])

    def set_motors(self, inputs):
        motor_indexes = range(len(inputs))
        motor_positions = inputs
        self._set_motors(motor_indexes, motor_positions)
    
    def set_shutter(self, inputs):
        shutter_state = inputs[0]
        error = self.api.set_shutter(shutter_state)
        self.shutter_position.write(shutter_state)
        return error
         
    def set_speed_parameters(self, inputs):
        motor_index, min_speed, max_speed, accelleration = inputs
        error = self.api._set_speed_parameters(motor_index, min_speed, max_speed, acceleration)
        return error
    
    def wait_until_still(self, inputs=[]):
        while self.is_busy():
            time.sleep(0.1)  # I've experienced hard crashes when wait set to 0.01 - Blaise 2015.12.30
            self.get_motor_positions()
        self.get_motor_positions()
    
    
def OPA_offline(OPA):
    
    def initialize(self):
        pass

    
### gui #######################################################################
    
    
class MotorControlGUI(QtGui.QWidget):
    
    def __init__(self, motor_name, motor_mutex, driver):
        QtGui.QWidget.__init__(self)
        self.motor_name = motor_name
        self.driver = driver
        self.layout = QtGui.QVBoxLayout()
        self.layout.setMargin(0)
        # table
        input_table = pw.InputTable()
        input_table.add(motor_name, motor_mutex)
        self.destination = motor_mutex.associate(display=False)
        input_table.add('Dest. ' + motor_name, self.destination)
        self.layout.addWidget(input_table)
        # buttons
        home_button, set_button = self.add_buttons(self.layout, 'HOME', 'advanced', 'SET', 'set')
        home_button.clicked.connect(self.on_home)
        set_button.clicked.connect(self.on_set)
        g.queue_control.disable_when_true(home_button)
        g.queue_control.disable_when_true(set_button)
        # finish
        self.setLayout(self.layout)
            
    def add_buttons(self, layout, button1_text, button1_color, button2_text, button2_color):
        colors = g.colors_dict.read()
        # layout
        button_container = QtGui.QWidget()
        button_container.setLayout(QtGui.QHBoxLayout())
        button_container.layout().setMargin(0)
        # button1
        button1 = QtGui.QPushButton()
        button1.setText(button1_text)
        button1.setMinimumHeight(25)
        StyleSheet = 'QPushButton{background:custom_color; border-width:0px;  border-radius: 0px; font: bold 14px}'.replace('custom_color', colors[button1_color])
        button1.setStyleSheet(StyleSheet)
        button_container.layout().addWidget(button1)
        g.queue_control.disable_when_true(button1)
        # button2
        button2 = QtGui.QPushButton()
        button2.setText(button2_text)
        button2.setMinimumHeight(25)
        StyleSheet = 'QPushButton{background:custom_color; border-width:0px;  border-radius: 0px; font: bold 14px}'.replace('custom_color', colors[button2_color])
        button2.setStyleSheet(StyleSheet)
        button_container.layout().addWidget(button2)
        g.queue_control.disable_when_true(button2)
        # finish
        layout.addWidget(button_container)
        return [button1, button2]
        
    def on_home(self):
        self.driver.address.hardware.q.push('home_motor', [self.motor_name])
    
    def on_set(self):
        destination = self.destination.read()
        self.driver.address.hardware.q.push('set_motor', [self.motor_name, destination])


class GUI(QtCore.QObject):

    def __init__(self, driver):
        QtCore.QObject.__init__(self)
        self.driver = driver

    def create_frame(self, layout):
        layout.setMargin(5)
        self.layout = layout
        self.frame = QtGui.QWidget()
        self.frame.setLayout(self.layout)
        if self.driver.initialized.read():
            self.initialize()
        else:
            self.driver.initialized.updated.connect(self.initialize)

    def initialize(self):
        # container widget
        display_container_widget = QtGui.QWidget()
        display_container_widget.setLayout(QtGui.QVBoxLayout())
        display_layout = display_container_widget.layout()
        display_layout.setMargin(0)
        self.layout.addWidget(display_container_widget)
        # plot
        self.plot_widget = pw.Plot1D()
        self.plot_widget.plot_object.setMouseEnabled(False, False)
        self.plot_curve = self.plot_widget.add_scatter()
        self.plot_h_line = self.plot_widget.add_infinite_line(angle=0, hide=False)
        self.plot_v_line = self.plot_widget.add_infinite_line(angle=90, hide=False)
        display_layout.addWidget(self.plot_widget)
        # vertical line
        line = pw.line('V')
        self.layout.addWidget(line)
        # container widget / scroll area
        settings_container_widget = QtGui.QWidget()
        settings_scroll_area = pw.scroll_area()
        settings_scroll_area.setWidget(settings_container_widget)
        settings_scroll_area.setMinimumWidth(300)
        settings_scroll_area.setMaximumWidth(300)
        settings_container_widget.setLayout(QtGui.QVBoxLayout())
        settings_layout = settings_container_widget.layout()
        settings_layout.setMargin(5)
        self.layout.addWidget(settings_scroll_area)
        # opa properties
        input_table = pw.InputTable()
        serial_number_display = pc.Number(initial_value=self.driver.serial_number, decimals=0, display=True)
        input_table.add('Serial Number', serial_number_display)
        settings_layout.addWidget(input_table)
        # plot control
        input_table = pw.InputTable()
        input_table.add('Display', None)
        self.plot_motor = pc.Combo(allowed_values=self.driver.curve.get_motor_names())
        self.plot_motor.updated.connect(self.update_plot)
        input_table.add('Motor', self.plot_motor)
        allowed_values = wt.units.energy.keys()
        allowed_values.remove('kind')
        self.plot_units = pc.Combo(initial_value='nm', allowed_values=allowed_values)
        self.plot_units.updated.connect(self.update_plot)
        input_table.add('Units', self.plot_units)
        settings_layout.addWidget(input_table)
        # curves
        input_table = pw.InputTable()
        input_table.add('Curves', None)
        for name, obj in self.driver.curve_paths.items():
            input_table.add(name, obj)
            obj.updated.connect(self.update_plot)
        input_table.add('Interaction String', self.driver.interaction_string_combo)
        self.low_energy_limit_display = pc.Number(units='nm', display=True)
        input_table.add('Low Energy Limit', self.low_energy_limit_display)
        self.high_energy_limit_display = pc.Number(units='nm', display=True)
        input_table.add('High Energy LImit', self.high_energy_limit_display)
        settings_layout.addWidget(input_table)
        self.driver.limits.updated.connect(self.on_limits_updated)
        # motors
        input_table = pw.InputTable()
        input_table.add('Motors', None)
        settings_layout.addWidget(input_table)
        for motor_name, motor_mutex in self.driver.motor_positions.items():
            settings_layout.addWidget(MotorControlGUI(motor_name, motor_mutex, self.driver))
        self.home_all_button = pw.SetButton('HOME ALL', 'advanced')
        settings_layout.addWidget(self.home_all_button)
        self.home_all_button.clicked.connect(self.on_home_all)
        g.queue_control.disable_when_true(self.home_all_button)
        # stretch
        settings_layout.addStretch(1)
        # signals and slots
        self.driver.interaction_string_combo.updated.connect(self.update_plot)
        self.driver.address.update_ui.connect(self.update)
        # finish
        self.update()
        self.update_plot()
        self.on_limits_updated()
        # autotune
        self.driver.auto_tune.initialize()

    def update(self):
        print 'TOPAS update'
        # set button disable
        if self.driver.address.busy.read():
            self.home_all_button.setDisabled(True)
            for motor_mutex in self.driver.motor_positions.values():
                motor_mutex.set_disabled(True)
        else:
            self.home_all_button.setDisabled(False)
            for motor_mutex in self.driver.motor_positions.values():
                motor_mutex.set_disabled(False)
        # update destination motor positions
        # TODO: 
        # update plot lines
        motor_name = self.plot_motor.read()
        motor_position = self.driver.motor_positions[motor_name].read()
        self.plot_h_line.setValue(motor_position)
        units = self.plot_units.read()
        self.plot_v_line.setValue(self.driver.current_position.read(units))

    def update_plot(self):
        # units
        units = self.plot_units.read()
        # xi
        colors = self.driver.curve.colors
        xi = wt_units.converter(colors, 'nm', units)
        # yi
        self.plot_motor.set_allowed_values(self.driver.curve.get_motor_names())
        motor_name = self.plot_motor.read()
        motor_index = self.driver.curve.get_motor_names().index(motor_name)
        yi = self.driver.curve.get_motor_positions(colors, units)[motor_index]
        self.plot_widget.set_labels(xlabel=units, ylabel=motor_name)
        self.plot_curve.clear()
        self.plot_curve.setData(xi, yi)
        self.plot_widget.graphics_layout.update()
        self.update()

    def update_limits(self):
        if False:
            limits = self.opa.limits.read(self.opa.native_units)
            self.lower_limit.write(limits[0], self.opa.native_units)
            self.upper_limit.write(limits[1], self.opa.native_units)

    def on_home_all(self):
        self.driver.address.hardware.q.push('home_all')
        
    def on_limits_updated(self):
        low_energy_limit, high_energy_limit = self.driver.limits.read('wn')
        self.low_energy_limit_display.write(low_energy_limit, 'wn')
        self.high_energy_limit_display.write(high_energy_limit, 'wn')
        
    def show_advanced(self):
        pass

    def stop(self):
        pass


### autotune ##################################################################


class AutoTune(QtGui.QWidget):
    
    def __init__(self, opa):
        QtGui.QWidget.__init__(self)
        self.opa = opa
        self.setLayout(QtGui.QVBoxLayout())
        self.layout = self.layout()
        self.layout.setMargin(0)
        self.initialized = pc.Bool()
        
    def initialize(self):
        input_table = pw.InputTable()
        self.operation_combo = pc.Combo()
        self.operation_combo.updated.connect(self.on_operation_changed)
        input_table.add('Operation', self.operation_combo)
        self.channel_combos = []
        self.layout.addWidget(input_table)
        # widgets
        self.widgets = collections.OrderedDict()
        # signal preamp -------------------------------------------------------
        w = pw.InputTable()
        # D1
        d1_width = pc.Number(initial_value=0.5)
        w.add('D1', None)
        w.add('Width', d1_width, key='D1 Width')
        d1_number = pc.Number(initial_value=51, decimals=0)
        w.add('Number', d1_number, key='D1 Number')
        channel = pc.Combo()
        self.channel_combos.append(channel)
        w.add('Channel', channel, key='D1 Channel')
        # test
        w.add('Test', None)
        do = pc.Bool(initial_value=True)
        w.add('Do', do)
        channel = pc.Combo()
        self.channel_combos.append(channel)
        w.add('Channel', channel, key='Test Channel')
        self.widgets['signal preamp'] = w
        self.layout.addWidget(w)
        # signal poweramp -----------------------------------------------------
        w = pw.InputTable()
        # D2
        w.add('D2', None)
        d2_width = pc.Number(initial_value=3.)
        w.add('D2 Width', d2_width)
        d2_number = pc.Number(initial_value=51, decimals=0)
        w.add('D2 Number', d2_number)
        channel = pc.Combo()
        self.channel_combos.append(channel)
        w.add('Channel', channel)
        # C2
        w.add('C2', None)
        c2_width = pc.Number(initial_value=2.)
        w.add('C2 Width', c2_width)
        c2_number = pc.Number(initial_value=51, decimals=0)
        w.add('C2 Number', c2_number)
        channel = pc.Combo()
        self.channel_combos.append(channel)
        w.add('Channel', channel)
        self.widgets['signal poweramp'] = w
        self.layout.addWidget(w)
        # SHS -----------------------------------------------------------------
        w = pw.InputTable()
        # M2
        w.add('M2', None)
        m2_width = pc.Number(initial_value=5.)
        w.add('M2 Width', m2_width)
        m2_number = pc.Number(initial_value=21, decimals=0)
        w.add('M2 Number', m2_number)
        channel = pc.Combo()
        self.channel_combos.append(channel)
        w.add('Channel', channel)
        # tune test
        w.add('Test', None)
        width = pc.Number(initial_value=-5000)
        w.add('Width', width)
        number = pc.Number(initial_value=51)
        w.add('Number', number)
        channel = pc.Combo()
        self.channel_combos.append(channel)
        w.add('Channel', channel)        
        self.widgets['SHS'] = w
        self.layout.addWidget(w)
        # finish --------------------------------------------------------------
        self.operation_combo.set_allowed_values(self.widgets.keys())
        # repetitions
        input_table = pw.InputTable()
        input_table.add('Repetitions', None)
        self.repetition_count = pc.Number(initial_value=1, decimals=0)
        input_table.add('Count', self.repetition_count)
        # finish
        self.layout.addWidget(input_table)
        self.initialized.write(True)
        self.on_operation_changed()
        
    def load(self, aqn_path):
        # TODO: channels
        aqn = wt.kit.INI(aqn_path)
        self.do_BBO.write(aqn.read('BBO', 'do'))
        self.BBO_width.write(aqn.read('BBO', 'width'))
        self.BBO_number.write(aqn.read('BBO', 'number'))
        self.do_Mixer.write(aqn.read('Mixer', 'do'))
        self.Mixer_width.write(aqn.read('Mixer', 'width'))
        self.Mixer_number.write(aqn.read('Mixer', 'number'))
        self.do_test.write(aqn.read('Test', 'do'))
        self.wm_width.write(aqn.read('Test', 'width'))
        self.wm_number.write(aqn.read('Test', 'number'))
        self.repetition_count.write(aqn.read('Repetitions', 'count'))
        
    def on_operation_changed(self):
        for w in self.widgets.values():
            w.hide()
        self.widgets[self.operation_combo.read()].show()
        
    def run(self, worker):
        import somatic.acquisition as acquisition
        # BBO -----------------------------------------------------------------
        if worker.aqn.read('BBO', 'do'):
            axes = []
            # tune points
            points = self.opa.curve.colors
            units = self.opa.curve.units
            name = identity = self.opa.address.hardware.friendly_name
            axis = acquisition.Axis(points=points, units=units, name=name, identity=identity)
            axes.append(axis)
            # motor
            name = '_'.join([self.opa.address.hardware.friendly_name, self.opa.curve.motor_names[1]])
            identity = 'D' + name
            width = worker.aqn.read('BBO', 'width') 
            npts = int(worker.aqn.read('BBO', 'number'))
            points = np.linspace(-width/2., width/2., npts)
            motor_positions = self.opa.curve.motors[1].positions
            kwargs = {'centers': motor_positions}
            hardware_dict = {name: [self.opa.address.hardware, 'set_motor', ['BBO', 'destination']]}
            axis = acquisition.Axis(points, None, name, identity, hardware_dict, **kwargs)
            axes.append(axis)
            # do scan
            scan_folder = worker.scan(axes)
            # process
            p = os.path.join(scan_folder, '000.data')
            data = wt.data.from_PyCMDS(p)
            curve = self.opa.curve
            channel = worker.aqn.read('BBO', 'channel')
            old_curve_filepath = self.opa.curve_path.read()
            wt.tuning.workup.intensity(data, curve, channel, save_directory=scan_folder)
            # apply new curve
            p = wt.kit.glob_handler('.curve', folder=scan_folder)[0]
            self.opa.curve_path.write(p)
            # upload
            p = wt.kit.glob_handler('.png', folder=scan_folder)[0]
            worker.upload(scan_folder, reference_image=p)
        # Mixer ---------------------------------------------------------------
        if worker.aqn.read('Mixer', 'do'):
            axes = []
            # tune points
            points = self.opa.curve.colors
            units = self.opa.curve.units
            name = identity = self.opa.address.hardware.friendly_name
            axis = acquisition.Axis(points=points, units=units, name=name, identity=identity)
            axes.append(axis)
            # motor
            name = '_'.join([self.opa.address.hardware.friendly_name, self.opa.curve.motor_names[2]])
            identity = 'D' + name
            width = worker.aqn.read('Mixer', 'width') 
            npts = int(worker.aqn.read('Mixer', 'number'))
            points = np.linspace(-width/2., width/2., npts)
            motor_positions = self.opa.curve.motors[2].positions
            kwargs = {'centers': motor_positions}
            hardware_dict = {name: [self.opa.address.hardware, 'set_motor', ['Mixer', 'destination']]}
            axis = acquisition.Axis(points, None, name, identity, hardware_dict, **kwargs)
            axes.append(axis)
            # do scan
            scan_folder = worker.scan(axes)
            # process
            p = os.path.join(scan_folder, '000.data')
            data = wt.data.from_PyCMDS(p)
            curve = self.opa.curve
            channel = worker.aqn.read('Mixer', 'channel')
            old_curve_filepath = self.opa.curve_path.read()
            wt.tuning.workup.intensity(data, curve, channel, save_directory=scan_folder)
            # apply new curve
            p = wt.kit.glob_handler('.curve', folder=scan_folder)[0]
            self.opa.curve_path.write(p)
            # upload
            p = wt.kit.glob_handler('.png', folder=scan_folder)[0]
            worker.upload(scan_folder, reference_image=p)
        # Tune Test -----------------------------------------------------------
        if worker.aqn.read('Test', 'do'):
            axes = []
            # tune points
            points = self.opa.curve.colors
            units = self.opa.curve.units
            name = identity = self.opa.address.hardware.friendly_name
            axis = acquisition.Axis(points=points, units=units, name=name, identity=identity)
            axes.append(axis)
            # mono
            name = 'wm'
            identity = 'Dwm'
            width = worker.aqn.read('Test', 'width') 
            npts = int(worker.aqn.read('Test', 'number'))
            points = np.linspace(-width/2., width/2., npts)
            kwargs = {'centers': self.opa.curve.colors}
            axis = acquisition.Axis(points, 'wn', name, identity, **kwargs)
            axes.append(axis)
            # do scan
            scan_folder = worker.scan(axes)
            # process
            p = wt.kit.glob_handler('.data', folder=scan_folder)[0]
            data = wt.data.from_PyCMDS(p)
            curve = self.opa.curve
            channel = worker.aqn.read('Test', 'channel')
            wt.tuning.workup.tune_test(data, curve, channel, save_directory=scan_folder)
            # apply new curve
            p = wt.kit.glob_handler('.curve', folder=scan_folder)[0]
            self.opa.curve_path.write(p)
            # upload
            p = wt.kit.glob_handler('.png', folder=scan_folder)[0]
            worker.upload(scan_folder, reference_image=p)
        # finish --------------------------------------------------------------
        # return to old curve
        # TODO:
        if not worker.stopped.read():
            worker.finished.write(True)  # only if acquisition successfull
    
    def save(self, aqn_path):
        aqn = wt.kit.INI(aqn_path)
        operation = self.operation_combo.read()
        description = ' '.join(['OPA%i'%self.opa.index, operation])
        aqn.write('info', 'description', description)
        w = self.widgets[operation]
        if operation == 'signal preamp':
            aqn.add_section('D1')
            aqn.write('D1', 'width', w['D1 Width'].read())
        elif operation == 'signal poweramp':
            # TODO:
            raise NotImplementedError
        elif operation == 'SHS':
            # TODO:
            raise NotImplementedError
        else:
            raise Exception('operation {0} not recognized'.format(operation))


        
    def update_channel_names(self, channel_names):
        for c in self.channel_combos:
            c.set_allowed_values(channel_names)


### testing ###################################################################


if __name__ == '__main__':
    
    if False:
        OPA1 = TOPAS(r'C:\Users\John\Desktop\PyCMDS\opas\TOPAS_C\configuration\10742.ini')
        print OPA1.set_shutter(False)
        print OPA1.get_motor_position(0)
        print OPA1.set_motor_position(0, 3478)
        print OPA1.get_motor_positions_range(0)
        # print OPA1._set_motor_offset
        # print OPA1._set_motor_affix
        # print OPA1._move_motor
        # print OPA1._move_motor_to_position_units
        print OPA1.set_motor_positions_range(0, 0, 9000)
        print OPA1.get_wavelength(0)
        print OPA1._get_motor_affix(0)
        print OPA1._get_device_serial_number()    
        print OPA1._is_wavelength_setting_finished()
        print OPA1.is_motor_still(0)
        print OPA1.get_reference_switch_status(0)
        print OPA1.get_count_of_motors(),
        print OPA1._get_count_of_devices()
        print OPA1.convert_position_to_units(0, 3000)
        print OPA1.convert_position_to_steps(0, -4.)
        print OPA1._get_speed_parameters(0)
        print OPA1.set_speed_parameters(0, 10, 600, 400)
        print OPA1._update_motors_positions()
        print OPA1._stop_motor(0)
        #print OPA1._start_setting_wavelength(1300.)
        #print OPA1._start_setting_wavelength_ex(1300., 0, 0, 0, 0)
        #print OPA1._set_wavelength(1300.)
        print OPA1.start_motor_motion(0, 4000) 
        #print OPA1._set_wavelength_ex(1300., 0, 0, 0, 0)
        #print OPA1.get_interaction(1)
        print OPA1.close()
        
        #log errors and handle them within the OPA object
        #make some convinient methods that are exposed higher up
        
    if False:
        topas = TOPAS(r'C:\Users\John\Desktop\PyCMDS\opas\TOPAS_C\configuration\10742.ini')
        print topas.set_shutter(False)
        with wt.kit.Timer():
            print topas.start_motor_motion(0, 1000)
            print topas.get_reference_switch_status(0)
        n = 0
        while not topas.are_all_motors_still()[1]:
            n += 1
            time.sleep(0.01)
            #topas._update_motors_positions()
            topas.get_motor_position(0)
            #time.sleep(1)
        print 'n =', n
        print topas.get_motor_position(0)
        print topas.are_all_motors_still()
        
        print topas.close()
        
