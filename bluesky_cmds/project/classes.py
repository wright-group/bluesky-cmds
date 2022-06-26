### import ####################################################################


import time

import numpy as np

from qtpy import QtCore

from . import project_globals as g

import WrightTools.units as wt_units


### gui items #################################################################


class Value(QtCore.QMutex):
    def __init__(self, initial_value=None):
        """
        Basic QMutex object to hold a single object in a thread-safe way.
        """
        QtCore.QMutex.__init__(self)
        self.value = initial_value

    def read(self):
        return self.value

    def write(self, value):
        self.lock()
        self.value = value
        self.unlock()


class PyCMDS_Object(QtCore.QObject):
    updated = QtCore.Signal()
    disabled = False

    def __init__(
        self,
        initial_value=None,
        display=False,
        name="",
        label="",
        set_method=None,
        *args,
        **kwargs,
    ):
        QtCore.QObject.__init__(self)
        self.has_widget = False
        self.tool_tip = ""
        self.value = Value(initial_value)
        self.display = display
        self.set_method = set_method
        if self.display:
            self.disabled = True
        else:
            self.disabled = False
        # name
        self.name = name
        if not label == "":
            pass
        else:
            self.label = self.name

    def associate(self, display=None, pre_name=""):
        # display
        if display is None:
            display = self.display
        # name
        name = pre_name + self.name
        # new object
        new_obj = self.__class__(initial_value=self.read(), display=display, name=name)
        return new_obj

    def read(self):
        return self.value.read()

    def write(self, value):
        self.value.write(value)
        self.updated.emit()

    def set_disabled(self, disabled):
        self.disabled = bool(disabled)
        if self.has_widget:
            self.widget.setDisabled(self.disabled)

    def setDisabled(self, disabled):
        self.set_disabled(disabled)

    def set_tool_tip(self, tool_tip):
        self.tool_tip = str(tool_tip)
        if self.has_widget:
            self.widget.setToolTip(self.tool_tip)


class Bool(PyCMDS_Object):
    """
    holds 'value' (bool) - the state of the checkbox

    use read method to access
    """

    def __init__(self, initial_value=False, *args, **kwargs):
        PyCMDS_Object.__init__(self, initial_value=initial_value, *args, **kwargs)
        self.type = "checkbox"

    def give_control(self, control_widget):
        self.widget = control_widget
        # set
        self.widget.setChecked(self.value.read())
        # connect signals and slots
        self.updated.connect(lambda: self.widget.setChecked(self.value.read()))
        self.widget.stateChanged.connect(lambda: self.write(self.widget.isChecked()))
        # finish
        self.widget.setToolTip(self.tool_tip)
        self.widget.setDisabled(self.disabled)
        self.has_widget = True


class Combo(PyCMDS_Object):
    def __init__(self, allowed_values=["None"], initial_value=None, *args, **kwargs):
        PyCMDS_Object.__init__(self, *args, **kwargs)
        self.type = "combo"
        self.allowed_values = list(allowed_values)
        self.data_type = type(self.allowed_values[0])
        if initial_value is None:
            self.write(self.allowed_values[0])
        else:
            self.write(initial_value)

    def associate(self, display=None, pre_name=""):
        # display
        if display is None:
            display = self.display
        # name
        name = pre_name + self.name
        # new object
        new_obj = Combo(
            initial_value=self.read(),
            display=display,
            allowed_values=self.allowed_values,
            name=name,
        )
        return new_obj

    def read_index(self):
        return self.allowed_values.index(self.read())

    def set_allowed_values(self, allowed_values):
        """
        Set the allowed values of the Combo object.

        Parameters
        ----------
        allowed_values : list
            the new allowed values

        Notes
        ----------
        The value of the object is written to the first allowed value if the
        current value is not in the allowed values.
        """
        if allowed_values == self.allowed_values:
            return
        if not allowed_values:  # case of empty list
            return
        self.allowed_values = list(allowed_values)
        # update widget
        if self.has_widget:
            self.widget.currentIndexChanged.disconnect(self.write_from_widget)
            self.widget.clear()
            allowed_values_strings = [str(value) for value in self.allowed_values]
            self.widget.addItems(allowed_values_strings)
            self.widget.currentIndexChanged.connect(self.write_from_widget)
        # write value again
        if self.read() not in self.allowed_values:
            self.write(list(self.allowed_values)[0])
        else:
            self.write(self.read())

    def set_widget(self):
        allowed_values_strings = [str(value) for value in self.allowed_values]
        index = allowed_values_strings.index(str(self.read()))
        self.widget.setCurrentIndex(index)

    def write(self, value):
        # value will be maintained as original data type
        value = self.data_type(value)
        PyCMDS_Object.write(self, value)

    def write_from_widget(self):
        # needs to be defined method so we can connect and disconnect
        self.write(self.widget.currentText())

    def give_control(self, control_widget):
        self.widget = control_widget
        # fill out items
        allowed_values_strings = [str(value) for value in self.allowed_values]
        self.widget.addItems(allowed_values_strings)
        if self.read() is not None:
            self.widget.setCurrentIndex(allowed_values_strings.index(str(self.read())))
        # connect signals and slots
        self.updated.connect(self.set_widget)
        self.widget.currentIndexChanged.connect(self.write_from_widget)
        self.widget.setToolTip(self.tool_tip)
        self.widget.setDisabled(self.disabled)
        self.has_widget = True


class NumberLimits(PyCMDS_Object):
    def __init__(self, min_value=-1e6, max_value=1e6, units=None):
        """
        not appropriate for use as a gui element - only for backend use
        units must never change for this kind of object
        """
        PyCMDS_Object.__init__(self)
        PyCMDS_Object.write(self, [min_value, max_value])
        self.units = units

    def read(self, output_units="same"):
        min_value, max_value = PyCMDS_Object.read(self)
        if output_units == "same":
            pass
        else:
            min_value = wt_units.converter(min_value, self.units, output_units)
            max_value = wt_units.converter(max_value, self.units, output_units)
        # ensure order
        min_value, max_value = [
            min([min_value, max_value]),
            max([min_value, max_value]),
        ]
        return [min_value, max_value]

    def write(self, min_value, max_value, input_units="same"):
        if input_units == "same":
            pass
        else:
            min_value = wt_units.converter(min_value, input_units, self.units)
            max_value = wt_units.converter(max_value, input_units, self.units)
        # ensure order
        min_value, max_value = [
            min([min_value, max_value]),
            max([min_value, max_value]),
        ]
        PyCMDS_Object.write(self, [min_value, max_value])
        self.updated.emit()


class Number(PyCMDS_Object):
    units_updated = QtCore.Signal()

    def __init__(
        self,
        initial_value=np.nan,
        single_step=1.0,
        decimals=3,
        limits=None,
        units=None,
        *args,
        **kwargs,
    ):
        PyCMDS_Object.__init__(self, initial_value=initial_value, *args, **kwargs)
        self.type = "number"
        self.disabled_units = False
        self.single_step = single_step
        self.decimals = decimals
        self.set_control_steps(single_step, decimals)
        # units
        self.units = units
        # limits
        self.limits = limits
        if self.limits is None:
            self.limits = NumberLimits()
        if self.units is None:
            self.limits.units = None
        if self.units is not None and self.limits.units is None:
            self.limits.units = self.units
        self._set_limits()
        self.limits.updated.connect(self._set_limits)

    def _set_limits(self):
        min_value, max_value = self.limits.read()
        limits_units = self.limits.units
        try:
            min_value = wt_units.converter(min_value, limits_units, self.units)
        except ZeroDivisionError:
            min_value = np.inf
        try:
            max_value = wt_units.converter(max_value, limits_units, self.units)
        except ZeroDivisionError:
            max_value = np.inf
        # ensure order
        min_value, max_value = [
            min([min_value, max_value]),
            max([min_value, max_value]),
        ]
        if self.has_widget:
            self.widget.setMinimum(min_value)
            self.widget.setMaximum(max_value)
            if not self.display:
                self.set_tool_tip("min: " + str(min_value) + "\n" + "max: " + str(max_value))

    def associate(self, display=None, pre_name=""):
        # display
        if display is None:
            display = self.display
        # name
        name = pre_name + self.name
        # new object
        new_obj = Number(
            initial_value=self.read(),
            display=display,
            units=self.units,
            limits=self.limits,
            single_step=self.single_step,
            decimals=self.decimals,
            name=name,
        )
        return new_obj

    def convert(self, destination_units):
        # value
        self.value.lock()
        old_val = self.value.read()
        new_val = wt_units.converter(old_val, self.units, str(destination_units))
        self.value.unlock()
        self.value.write(new_val)
        # commit and signal
        self.units = str(destination_units)
        self._set_limits()
        self.units_updated.emit()
        self.updated.emit()

    def read(self, output_units="same"):
        value = PyCMDS_Object.read(self)
        if output_units == "same":
            pass
        else:
            value = wt_units.converter(value, self.units, output_units)
        return value

    def set_control_steps(self, single_step=None, decimals=None):
        limits = [self.single_step, self.decimals]
        inputs = [single_step, decimals]
        widget_methods = ["setSingleStep", "setDecimals"]
        for i in range(len(limits)):
            if not inputs[i] is None:
                limits[i] = inputs[i]
            if self.has_widget:
                getattr(self.widget, widget_methods[i])(limits[i])

    def set_disabled_units(self, disabled):
        self.disabled_units = bool(disabled)
        if self.has_widget:
            self.units_widget.setDisabled(self.disabled_units)

    def set_units(self, units):
        if self.has_widget:
            allowed = [self.units_widget.itemText(i) for i in range(self.units_widget.count())]
            index = allowed.index(units)
            self.units_widget.setCurrentIndex(index)
        else:
            self.convert(units)

    def set_widget(self):
        # special value text is displayed when widget is at minimum
        if np.isnan(self.value.read()):
            self.widget.setSpecialValueText("nan")
            self.widget.setValue(self.widget.minimum())
        else:
            self.widget.setSpecialValueText("")
            self.widget.setValue(self.value.read())

    def give_control(self, control_widget):
        self.widget = control_widget
        # set values
        min_value, max_value = self.limits.read()
        self.widget.setMinimum(min_value)
        self.widget.setMaximum(max_value)
        self.widget.setDecimals(self.decimals)
        self.widget.setSingleStep(self.single_step)
        self.set_widget()
        # connect signals and slots
        self.updated.connect(self.set_widget)
        self.widget.editingFinished.connect(lambda: self.write(self.widget.value()))
        # finish
        self.widget.setToolTip(self.tool_tip)
        self.widget.setDisabled(self.disabled)
        self.has_widget = True
        self._set_limits()

    def give_units_combo(self, units_combo_widget):
        self.units_widget = units_combo_widget
        # add items
        unit_types = [self.units] + list(wt_units.get_valid_conversions(self.units))
        self.units_widget.addItems(unit_types)
        # set current item
        self.units_widget.setCurrentIndex(unit_types.index(self.units))
        # associate update with conversion
        self.units_widget.currentIndexChanged.connect(
            lambda: self.convert(self.units_widget.currentText())
        )
        # finish
        self.units_widget.setDisabled(self.disabled_units)

    def write(self, value, input_units="same"):
        if input_units == "same":
            pass
        else:
            value = wt_units.converter(value, input_units, self.units)
        PyCMDS_Object.write(self, value)


class String(PyCMDS_Object):
    def __init__(self, initial_value="", max_length=None, *args, **kwargs):
        PyCMDS_Object.__init__(self, initial_value=initial_value, *args, **kwargs)
        self.type = "string"
        self.max_length = max_length

    def give_control(self, control_widget):
        self.widget = control_widget
        if self.max_length is not None:
            self.widget.setMaxLength(self.max_length)
        # fill out items
        self.widget.setText(str(self.value.read()))
        # connect signals and slots
        self.updated.connect(lambda: self.widget.setText(self.value.read()))
        self.widget.editingFinished.connect(lambda: self.write(str(self.widget.text())))
        self.widget.setToolTip(self.tool_tip)
        self.has_widget = True

    def read(self):
        return str(PyCMDS_Object.read(self))

    def write(self, value):
        if self.max_length is not None:
            value = value[: self.max_length]
        self.value.write(value)
        self.updated.emit()
