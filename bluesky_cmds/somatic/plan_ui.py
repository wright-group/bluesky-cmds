from collections import defaultdict
import itertools
import json

import toolz
import numpy as np
from qtpy import QtWidgets
import qtypes
from .comms import RM
from .signals import plans_allowed_updated, devices_allowed_updated
from bluesky_hwproxy import zmq_single_request as hwproxy_request

import WrightTools as wt


def get_all_components(k, v):
    out = {k: v}
    for sk, sv in v.get("components", {}).items():
        out.update(get_all_components(".".join([k, sk]), sv))
    return out

def get_units(device):
    if "." in device:
        base_name = device.split(".")[0]
        key_name = device.replace(".", "_")
    else:
        base_name = key_name = device
    return hwproxy_request("describe", {"device": base_name})[0].get("return", {}).get(key_name, {}).get(
        "units", None
    )

def get_limits(device):
    if "." in device:
        base_name = device.split(".")[0]
        key_name = device.replace(".", "_")
    else:
        base_name = key_name = device
    describe = hwproxy_request("describe", {"device": base_name})[0].get("return", {}).get(key_name, {})
    low = describe.get("lower_ctrl_limit", -np.inf)
    hi = describe.get("upper_ctrl_limit", np.inf)
    return (low, hi)



devices_all = {}
devices_all_json = {}
devices_movable = []
devices_not_movable = []
devices_with_deps = []

def update_devices():
    global devices_all, devices_all_json, devices_movable, devices_not_movable, devices_with_deps
    devices_all_json = RM.devices_allowed()["devices_allowed"]
    devices_all = {}

    for k, v in devices_all_json.items():
        devices_all.update(get_all_components(k, v))

    devices_movable = list(filter(lambda x: devices_all[x]["is_movable"], devices_all))
    devices_not_movable = list(filter(lambda x: not devices_all[x]["is_movable"], devices_all))
    devices_with_deps = list(filter(lambda x: "components" in devices_all[x], devices_all))
    update_plan_ui()



class PlanUI:
    def __init__(self, items=None):
        if items is None:
            self.items = [
                MetadataWidget(),
                ArgsWidget(),
                KwargsWidget(),
            ]
        else:
            self.items = items
        self.frame = [x.frame for x in self.items]

    @property
    def args(self):
        return list(itertools.chain(*[x.args for x in self.items]))

    @args.setter
    def args(self, args):
        for item in self.items:
            if item.nargs < 0:
                item.args = args
                break
            elif item.nargs > 0:
                item.args = args[: item.nargs]
                args = args[item.nargs :]

    @property
    def kwargs(self):
        out = {}
        for x in self.items:
            out.update(x.kwargs)
        return out

    @kwargs.setter
    def kwargs(self, kwargs):
        for item in self.items:
            item.kwargs = kwargs
        if "args" in kwargs:
            for item in self.items:
                if item.nargs < 0:
                    item.args = kwargs["args"]
                    break

    def load(self, *args, **kwargs):
        for x in self.items:
            if args:
                if x.nargs < 0:
                    x.args = args
                    args = []
                elif x.nargs > 0:
                    x.args = args[: x.nargs]
                    args = args[x.nargs :]
            x.kwargs = kwargs


class MetadataWidget:
    def __init__(self):
        self.nargs = 0
        exp_list = ["unspecified"] + list(sorted(["Kyle", "Emily", "Kelson", "Dan", "Kent", "Peter", "Ryan", "Jason", "David", "John", "Chris", "James"]))
        self.fields = [
            qtypes.String("Name"),
            qtypes.String("Info"),
            qtypes.Enum("Experimentor", allowed=exp_list),
        ]

    @property
    def frame(self):
        frame = qtypes.Null("Metadata")
        frame.extend(self.fields)
        return frame

    @property
    def args(self):
        return []

    @args.setter
    def args(self, arg):
        pass

    @property
    def kwargs(self):
        return {"md": {v.get()["label"]: v.get_value() for v in self.fields}}

    @kwargs.setter
    def kwargs(self, kwargs):
        md = kwargs.get("md", {})
        for v in self.fields:
            k = b.get()["label"]
            if k in md:
                v.set_value(md[k])


class ArgsWidget:
    def __init__(self):
        self.nargs = -1
        self.frame = qtypes.String("Args")

    @property
    def args(self):
        return json.loads(self.frame.get_value() or "[]")

    @args.setter
    def args(self, args):
        self.frame.set_value(json.dumps(args))

    @property
    def kwargs(self):
        return {}

    @kwargs.setter
    def kwargs(self, kwargs):
        pass


class KwargsWidget:
    def __init__(self):
        self.nargs = 0
        self.frame = qtypes.String("Kwargs")

    @property
    def kwargs(self):
        return json.loads(self.frame.get_value() or "{}")

    @kwargs.setter
    def kwargs(self, kwargs):
        self.frame.set_value(json.dumps(kwargs))

    @property
    def args(self):
        return []

    @args.setter
    def args(self, args):
        pass


class SingleWidget:
    def __init__(self, name, kwarg=None, kw_only=False):
        self.nargs = 1
        if kw_only:
            self.nargs = 0
        self.frame = qtypes.Null(name)
        self.kwarg = kwarg

    @property
    def args(self):
        return [self.frame.get_value()] if not self.kwarg else []

    @args.setter
    def args(self, arg):
        if arg:
            self.frame.set_value(arg[0])

    @property
    def kwargs(self):
        return {self.kwarg: self.frame.get_value()} if self.kwarg else {}

    @kwargs.setter
    def kwargs(self, kwargs):
        if self.kwarg in kwargs:
            self.args = [kwargs[self.kwarg]]


class BoolWidget(SingleWidget):
    def __init__(self, name, kwarg=None):
        super().__init__(name, kwarg)
        self.frame = qtypes.Bool(name)


class StrWidget(SingleWidget):
    def __init__(self, name, kwarg=None):
        super().__init__(name, kwarg)
        self.frame = qtypes.String(name)


class IntWidget(SingleWidget):
    def __init__(self, name, kwarg=None, default=0):
        super().__init__(name, kwarg)
        self.frame = qtypes.Integer(name, value=default)

    @property
    def args(self):
        return [int(self.frame.get_value())] if not self.kwarg else []

    @args.setter
    def args(self, arg):
        if arg:
            self.frame.set_value(arg[0])

    @property
    def kwargs(self):
        return {self.kwarg: int(self.frame.get_value())} if self.kwarg else {}

    @kwargs.setter
    def kwargs(self, kwargs):
        if self.kwarg in kwargs:
            self.args = [kwargs[self.kwarg]]


class FloatWidget(SingleWidget):
    def __init__(self, name, kwarg=None, default=0):
        super().__init__(name, kwarg)
        self.frame = qtypes.Float(name, value=default)


class EnumWidget(SingleWidget):
    def __init__(self, name, options: dict, kwarg=None):
        super().__init__(name, kwarg)
        self.frame = qtypes.Enum(name, allowed=list(options.keys()))
        self._options = options

    @property
    def options(self):
        return self._options

    @options.setter
    def options(self, value):
        self.frame.set({"allowed": list(value.keys())})
        self._options = value

    @property
    def args(self):
        return [self.options[self.frame.get_value()]] if not self.kwarg else []

    @args.setter
    def args(self, arg):
        if arg:
            for k, v in self.options.items():
                if arg[0] == v:
                    self.frame.set_value(k)
                    break

    @property
    def kwargs(self):
        return {self.kwarg: self.options[self.frame.get_value()]} if self.kwarg else {}

    @kwargs.setter
    def kwargs(self, kwargs):
        if self.kwarg in kwargs:
            self.args = [kwargs[self.kwarg]]


class DeviceListWidget:
    def __init__(self):
        self.nargs = 1
        self.inputs = [qtypes.Bool(k, value=True) for k in devices_not_movable]
        self.frame = qtypes.Null("Devices")
        self.frame.extend(self.inputs)

    @property
    def kwargs(self):
        return {}

    @kwargs.setter
    def kwargs(self, kwargs):
        pass

    @property
    def args(self):
        return [[v.get()["label"] for v in self.inputs if v.get_value()]]

    @args.setter
    def args(self, args):
        arg = args[0]
        for device in self.inputs:
            self.inputs[device].set_value(device in arg)


class ConstantWidget:
    def __init__(self):
        self.nargs = 0
        self.frame = QtWidgets.QWidget()
        self.frame.setLayout(QtWidgets.QVBoxLayout())
        self.frame.layout().setContentsMargins(0, 0, 0, 0)
        label = pw.InputTable()
        label.add("Constants", None)
        self.frame.layout().addWidget(label)
        self.constants_container_widget = QtWidgets.QWidget()
        self.constants_container_widget.setLayout(QtWidgets.QVBoxLayout())
        self.constants_container_widget.layout().setContentsMargins(0, 0, 0, 0)
        self.constants = []
        self.frame.layout().addWidget(self.constants_container_widget)
        add_button = pw.SetButton("ADD")
        remove_button = pw.SetButton("REMOVE", "stop")
        add_button.clicked.connect(self.add_constant)
        remove_button.clicked.connect(self.remove_constant)
        self.frame.layout().addWidget(add_button)
        self.frame.layout().addWidget(remove_button)

    def add_constant(self, hardware=None, units="ps", terms=None):
        # TODO better default
        if not hardware:
            hardware = devices_movable[0]
        if terms is None:
            terms = [[1, "d1"]]
        const = Constant(hardware, units, terms)
        self.constants.append(const)
        self.constants_container_widget.layout().addWidget(const)

    def remove_constant(self):
        if not self.constants:
            return
        const = self.constants[-1]
        self.constants = self.constants[:-1]
        self.constants_container_widget.layout().removeWidget(const)

    @property
    def args(self):
        return []

    @args.setter
    def args(self, args):
        pass

    @property
    def kwargs(self):
        return {"constants": [c.args for c in self.constants]}

    @kwargs.setter
    def kwargs(self, kwargs):
        while self.constants:
            self.remove_constant()
        for c in kwargs.get("constants", []):
            self.add_constant(*c)


class Constant(qtypes.Null):
    def __init__(self, hardware, units, terms):
        super().__init__()
        self.add("Constant", None)
        self.hardware = pc.Combo(devices_movable)
        self.hardware.set_value(hardware)
        self.hardware.updated.connect(self.on_hardware_updated)
        self.add("Hardware", self.hardware)
        self.units = pc.Combo(wt.units.blessed_units)
        self.units.set_value(units)
        self.add("Units", self.units)
        self.expression = pc.String()
        self.expression.set_value(
            " + ".join(f"{coeff}*{hw}" if hw else f"{coeff}" for coeff, hw in terms)
        )
        self.add("Expression", self.expression)
        self.on_hardware_updated()

    @property
    def args(self):
        units = self.units.get_value()
        if units == "None":
            units = None
        return [self.hardware.get_value(), units, self.terms]

    @property
    def terms(self):
        import sympy

        expr = sympy.parse_expr(self.expression.get_value())
        coeffs = expr.as_coefficients_dict()

        for k, v in list(coeffs.items()):
            del coeffs[k]
            if isinstance(k, sympy.Number):
                coeffs[None] = float(k * v)
            elif isinstance(k, str):
                coeffs[k] = float(v)
            else:
                coeffs[k.name] = float(v)
        return [(v, k) for k, v in coeffs.items()]

    def on_hardware_updated(self):
        hw_name = self.hardware.get_value()
        native = get_units(hw_name)
        units_list = [
            i for i in (native,) + wt.units.get_valid_conversions(native) if i != "mm_delay"
        ]
        self.units.set_allowed_values(units_list)


class GenericScanArgsWidget:
    def __init__(self, partition):
        self.nargs = -1
        self.partition = partition
        self.frame = QtWidgets.QWidget()
        self.frame.setLayout(QtWidgets.QVBoxLayout())
        self.frame.layout().setContentsMargins(0, 0, 0, 0)
        label = pw.InputTable()
        label.add("Axes", None)
        self.frame.layout().addWidget(label)
        self.axis_container_widget = QtWidgets.QWidget()
        self.axis_container_widget.setLayout(QtWidgets.QVBoxLayout())
        self.axis_container_widget.layout().setContentsMargins(0, 0, 0, 0)
        self.axes = []
        self.frame.layout().addWidget(self.axis_container_widget)
        add_button = pw.SetButton("ADD")
        remove_button = pw.SetButton("REMOVE", "stop")
        add_button.clicked.connect(self.add_axis)
        remove_button.clicked.connect(self.remove_axis)
        self.frame.layout().addWidget(add_button)
        self.frame.layout().addWidget(remove_button)
        self.add_axis()

    def add_axis(self, *args):
        raise NotImplementedError

    def remove_axis(self):
        if not self.axes:
            return
        ax = self.axes[-1]
        self.axes = self.axes[:-1]
        self.axis_container_widget.layout().removeWidget(ax)

    @property
    def args(self):
        return list(itertools.chain(*[a.args for a in self.axes]))

    @args.setter
    def args(self, args):
        while self.axes:
            self.remove_axis()
        for c in toolz.partition(self.partition, args):
            self.add_axis(*c)
@property
    def kwargs(self):
        return {}

    @kwargs.setter
    def kwargs(self, kwargs):
        pass

class MvAxis(qtypes.Null):
    def __init__(self, hardware, position):
        super().__init__()
        self.add("Axis", None)
        self.hardware = pc.Combo(devices_movable)
        self.hardware.set_value(hardware)
        self.add("Hardware", self.hardware)
        self.native = get_units(hardware)
        self.position = pc.Number(units=self.native)
        self.position.limits.set_value(*get_limits(self.hardware.get_value()), self.native)
        self.position.set_value(position)
        self.add("Position", self.position)
        self.hardware.updated.connect(self.set_unit)

    @property
    def args(self):
        return [
            self.hardware.get_value(),
            self.position.get_value(self.native),
        ]

    def set_unit(self):
        self.native = get_units(self.hardware.get_value())
        self.position.set_units(self.native)
        self.position.limits.units = self.native
        self.position.limits.set_value(*get_limits(self.hardware.get_value()), self.native)
        

class MvArgsWidget(GenericScanArgsWidget):
    def __init__(self):
        super().__init__(2)

    def add_axis(self, hardware=None, position=0):
        if not hardware:
            hardware = devices_movable[0]
        axis = MvAxis(hardware, position)
        self.axes.append(axis)
        self.axis_container_widget.layout().addWidget(axis)

class GridscanAxis(qtypes.Null):
    def __init__(self, hardware, start, stop, npts, units):
        super().__init__()
        self.add("Axis", None)
        self.hardware = pc.Combo(devices_movable)
        self.hardware.set_value(hardware)
        self.hardware.updated.connect(self.on_hardware_updated)
        self.add("Hardware", self.hardware)
        self.start = pc.Number(start)
        self.add("Start", self.start)
        self.stop = pc.Number(stop)
        self.add("Stop", self.stop)
        self.npts = pc.Number(npts, decimals=0)
        self.add("Npts", self.npts)
        self.units = pc.Combo(wt.units.blessed_units)
        self.units.set_value(units)
        self.add("Units", self.units)
        self.on_hardware_updated()

    @property
    def args(self):
        units = self.units.get_value()
        if units == "None":
            units = None
        return [
            self.hardware.get_value(),
            self.start.get_value(),
            self.stop.get_value(),
            int(self.npts.get_value()),
            units,
        ]

    def on_hardware_updated(self):
        hw_name = self.hardware.get_value()
        base_name = hw_name.split(".")[0]
        key_name = hw_name.replace(".", "_")
        native = hwproxy_request("describe", {"device": base_name})[0]["return"][key_name].get(
            "units", None
        )
        units_list = [
            i for i in (native,) + wt.units.get_valid_conversions(native) if i != "mm_delay"
        ]
        self.units.set_allowed_values(units_list)


class GridscanArgsWidget(GenericScanArgsWidget):
    def __init__(self):
        super().__init__(5)

    def add_axis(self, hardware=None, start=0, stop=1, npts=11, units="ps"):
        if not hardware:
            hardware = devices_movable[0]
        axis = GridscanAxis(hardware, start, stop, npts, units)
        self.axes.append(axis)
        self.axis_container_widget.layout().addWidget(axis)


class ScanAxis(qtypes.Null):
    def __init__(self, hardware, start, stop, units):
        super().__init__()
        self.add("Axis", None)
        self.hardware = pc.Combo(devices_movable)
        self.hardware.set_value(hardware)
        self.add("Hardware", self.hardware)
        self.hardware.updated.connect(self.on_hardware_updated)
        self.start = pc.Number(start)
        self.add("Start", self.start)
        self.stop = pc.Number(stop)
        self.add("Stop", self.stop)
        self.units = pc.Combo(wt.units.blessed_units)
        self.units.set_value(units)
        self.add("Units", self.units)
        self.on_hardware_updated()

    @property
    def args(self):
        units = self.units.get_value()
        if units == "None":
            units = None
        return [
            self.hardware.get_value(),
            self.start.get_value(),
            self.stop.get_value(),
            units,
        ]

    def on_hardware_updated(self):
        hw_name = self.hardware.get_value()
        native = get_units(hw_name)
        units_list = [
            i for i in (native,) + wt.units.get_valid_conversions(native) if i != "mm_delay"
        ]
        self.units.set_allowed_values(units_list)


class ScanArgsWidget(GenericScanArgsWidget):
    def __init__(self):
        super().__init__(4)

    def add_axis(self, hardware=None, start=0, stop=1, units="ps"):
        if not hardware:
            hardware = devices_movable[0]
        axis = ScanAxis(hardware, start, stop, units)
        self.axes.append(axis)
        self.axis_container_widget.layout().addWidget(axis)


class ListAxis(qtypes.Null):
    def __init__(self, hardware, list, units):
        super().__init__()
        self.add("Axis", None)
        self.hardware = pc.Combo(devices_movable)
        self.hardware.set_value(hardware)
        self.add("Hardware", self.hardware)
        self.hardware.updated.connect(self.on_hardware_updated)
        self.list = pc.String()
        self.list.set_value(json.dumps(list) or "[]")
        self.add("List", self.list)
        self.units = pc.Combo(wt.units.blessed_units)
        self.units.set_value(units)
        self.add("Units", self.units)
        self.on_hardware_updated()

    @property
    def args(self):
        units = self.units.get_value()
        if units == "None":
            units = None
        return [
            self.hardware.get_value(),
            json.loads(self.list.get_value()) or [],
            units,
        ]

    def on_hardware_updated(self):
        hw_name = self.hardware.get_value()
        native = get_units(hw_name)
        units_list = [
            i for i in (native,) + wt.units.get_valid_conversions(native) if i != "mm_delay"
        ]
        self.units.set_allowed_values(units_list)


class ListscanArgsWidget(GenericScanArgsWidget):
    def __init__(self):
        super().__init__(3)

    def add_axis(self, hardware=None, list=[], units="ps"):
        if not hardware:
            hardware = devices_movable[0]
        axis = ListAxis(hardware, list, units)
        self.axes.append(axis)
        self.axis_container_widget.layout().addWidget(axis)


class OpaSelectorWidget(EnumWidget):
    def __init__(self, name="opa"):
        super().__init__(name, options={x:x for x in devices_with_deps if len(devices_all_json.get(x, {}).get("components", {})) > 1})


class OpaMotorSelectorWidget(EnumWidget):
    def __init__(self, name="motor", opa_selector=None):
        if opa_selector is None:
            raise ValueError("Must specify associated opa selector")
        self.opa_selector = opa_selector
        super().__init__(name, options={"None": None})
        self.on_opa_selected()
        self.opa_selector.input.updated.connect(self.on_opa_selected)
        # TODO mutual exclusion


    def on_opa_selected(self):
        motors = {
            x: x
            for x in devices_all_json[self.opa_selector.args[0]]["components"]
        }
        if not motors:
            motors = {"None": None}
        self.options = motors

class OpaMotorAxis(qtypes.Null):
    def __init__(self, motor, method, center, width, npts, opa_selector):
        super().__init__()
        self.opa_selector = opa_selector
        if motor is None:
            motor = list(devices_all_json[self.opa_selector.args[0]]["components"].keys())[0]
        self.add("Motor Axis", None)
        self.motor = pc.Combo(devices_all_json[self.opa_selector.args[0]]["components"].keys())
        self.motor.set_value(motor)
        self.add("Motor", self.motor)
        self.center = pc.Number(center)
        self.add("Center", self.center)
        self.width = pc.Number(width)
        self.add("Width", self.width)
        self.npts = pc.Number(npts, decimals=0)
        self.add("npts", self.npts)
        self.opa_selector.input.updated.connect(self.on_opa_updated)

    @property
    def kwargs(self):
        # TODO 'static' method does not work so I don't give it a gui element yet -- 2022-05-16 KFS
        return {"method": "scan", "center": self.center.get_value(), "width": self.width.get_value(), "npts": int(self.npts.get_value())}

    def on_opa_updated(self):
        self.motor.set_allowed_values(devices_all_json[self.opa_selector.args[0]]["components"].keys())



class OpaMotorFullWidget(GenericScanArgsWidget):
    def __init__(self, opa_selector):
        self.opa_selector = opa_selector
        super().__init__(None)
        self.nargs = 0
        self.kwarg = "motors"

    def add_axis(self, motor=None, method="scan", center=0, width=1, npts=11):
        axis = OpaMotorAxis(motor, method, center, width, npts, opa_selector=self.opa_selector)
        self.axes.append(axis)
        self.axis_container_widget.layout().addWidget(axis)

    @property
    def args(self):
        return []

    @property
    def kwargs(self):
        return {"motors":{a.motor.get_value(): a.kwargs for a in self.axes}}

    @kwargs.setter
    def kwargs(self, value):
        while self.axes:
            self.remove_axis()
        if "motors" in value:
            for mot, params in value["motors"].items():
                self.add_axis(motor=mot, **params)


class SpectrometerWidget(qtypes.Null):
    def __init__(self, name="spectrometer", include_center=True):
        super().__init__()
        self.nargs = 0
        self.name = name
        self.frame = self
        self.add("Spectrometer", None)
        spec_devices = []
        for dev in devices_all_json:
            if dev not in devices_with_deps and wt.units.is_valid_conversion(get_units(dev), "nm"):
                spec_devices.append(dev)
        self.device = pc.Combo(["None"] + spec_devices)
        self.add("Device", self.device)
        self.method = pc.Combo(["none", "static", "zero", "track", "scan"])
        self.add("Method", self.method)
        self.center = pc.Number()
        self.add("Center", self.center)
        self.width = pc.Number(-250)
        self.add("Width", self.width)
        self.units = pc.Combo(("wn",) + wt.units.get_valid_conversions("wn"))
        self.add("Units", self.units)
        self.npts = pc.Number(11, decimals=0)
        self.add("Npts", self.npts)

        self.used = {
            "none": (),
            "static": ("device", "center", "units"),
            "zero": ("device"),
            "track": ("device"),
            "scan": ("device", "center", "width", "units", "npts"),
        }

        if not include_center:
            self.used["scan"] = ("device", "width", "units", "npts")

        self.device.updated.connect(self.on_device_selected)
        self.method.updated.connect(self.on_method_selected)
        self.on_device_selected()

    @property
    def kwargs(self):
        device = self.device.get_value()
        method = self.method.get_value()
        if device == "None" or method == "none":
            return {self.name: None}
        out = {
            k: v
            for k, v in {
                "device": device,
                "method": method,
                "center": self.center.get_value(),
                "width": self.width.get_value(),
                "units": self.units.get_value(),
                "npts": int(self.npts.get_value()),
            }.items()
            if k in self.used[method] or k == "method"
        }
        return {self.name: out}

    @kwargs.setter
    def kwargs(self, value):
        if value[self.name]:
            if "device" in value[self.name]:
                self.device.set_value(value[self.name]["device"])
            if "method" in value[self.name]:
                self.method.set_value([value[self.name]["method"]])
            if "center" in value[self.name]:
                self.center.set_value(value[self.name]["center"])
            if "width" in value[self.name]:
                self.width.set_value(value[self.name]["width"])
            if "units" in value[self.name]:
                self.units.set_value(value[self.name]["units"])
            if "npts" in value[self.name]:
                self.npts.set_value(value[self.name]["npts"])

    @property
    def args(self):
        return []

    def on_device_selected(self):
        if self.device.get_value() == "None":
            for var in ("center", "width", "units", "npts"):
                getattr(self, var).set_disabled(True)
        else:
            self.on_method_selected()

    def on_method_selected(self):
        method = self.method.get_value()
        for var in ("device", "center", "width", "units", "npts"):
            getattr(self, var).set_disabled(not var in self.used[method])


plan_ui_lookup = defaultdict(PlanUI)

def update_plan_ui():
    plan_ui_lookup["sleep"] = PlanUI(
        [
            FloatWidget("time", "time", 1.0),
        ]
    )
    plan_ui_lookup["mv"] = PlanUI(
        [
            MvArgsWidget(),
        ]
    )
    """
    plan_ui_lookup["grid_scan_wp"] = PlanUI(
        [
            MetadataWidget(),
            DeviceListWidget(),
            GridscanArgsWidget(),
            ConstantWidget(),
        ]
    )
    plan_ui_lookup["rel_grid_scan_wp"] = PlanUI(
        [
            MetadataWidget(),
            DeviceListWidget(),
            GridscanArgsWidget(),
            ConstantWidget(),
        ]
    )
    plan_ui_lookup["scan_wp"] = PlanUI(
        [
            MetadataWidget(),
            DeviceListWidget(),
            ScanArgsWidget(),
            IntWidget("Npts", "num", 11),
            ConstantWidget(),
        ]
    )
    plan_ui_lookup["rel_scan_wp"] = PlanUI(
        [
            MetadataWidget(),
            DeviceListWidget(),
            ScanArgsWidget(),
            IntWidget("Npts", "num", 11),
            ConstantWidget(),
        ]
    )
    plan_ui_lookup["list_scan_wp"] = PlanUI(
        [
            MetadataWidget(),
            DeviceListWidget(),
            ListscanArgsWidget(),
            ConstantWidget(),
        ]
    )
    plan_ui_lookup["rel_list_scan_wp"] = PlanUI(
        [
            MetadataWidget(),
            DeviceListWidget(),
            ListscanArgsWidget(),
            ConstantWidget(),
        ]
    )
    plan_ui_lookup["list_grid_scan_wp"] = PlanUI(
        [
            MetadataWidget(),
            DeviceListWidget(),
            ListscanArgsWidget(),
            ConstantWidget(),
        ]
    )
    plan_ui_lookup["rel_list_grid_scan_wp"] = PlanUI(
        [
            MetadataWidget(),
            DeviceListWidget(),
            ListscanArgsWidget(),
            ConstantWidget(),
        ]
    )
    """
    plan_ui_lookup["count"] = PlanUI(
        [
            MetadataWidget(),
            DeviceListWidget(),
            IntWidget("Npts", "num", 1),
            FloatWidget("Delay", "delay", 0),
        ]
    )

    if False and devices_with_deps:
        plan_ui_lookup["run_tune_test"] = PlanUI(
            [
                MetadataWidget(),
                DeviceListWidget(),
                OpaSelectorWidget(),
                SpectrometerWidget(include_center=False),
            ]
        )
        opa=OpaSelectorWidget()
        plan_ui_lookup["run_setpoint"] = PlanUI(
            [
                MetadataWidget(),
                DeviceListWidget(),
                opa,
                OpaMotorSelectorWidget(opa_selector=opa),
                FloatWidget("Width", "width", 1),
                IntWidget("Npts", "npts", 11),
                SpectrometerWidget(include_center=False),
            ]
        )
        opa=OpaSelectorWidget()
        plan_ui_lookup["run_intensity"] = PlanUI(
            [
                MetadataWidget(),
                DeviceListWidget(),
                opa,
                OpaMotorSelectorWidget(opa_selector=opa),
                FloatWidget("Width", "width", 1),
                IntWidget("Npts", "npts", 11),
                SpectrometerWidget(include_center=False),
            ]
        )
        opa=OpaSelectorWidget()
        plan_ui_lookup["run_holistic"] = PlanUI(
            [
                MetadataWidget(),
                DeviceListWidget(),
                opa,
                OpaMotorSelectorWidget(opa_selector=opa),
                OpaMotorSelectorWidget(opa_selector=opa),
                FloatWidget("Width", "width", 1),
                IntWidget("Npts", "npts", 11),
                SpectrometerWidget(include_center=False),
            ]
        )
        opa=OpaSelectorWidget()
        plan_ui_lookup["motortune"] = PlanUI(
            [
                MetadataWidget(),
                DeviceListWidget(),
                opa,
                BoolWidget("Use Tune Points", "use_tune_points"),
                OpaMotorFullWidget(opa_selector=opa),
                SpectrometerWidget(),
            ]
        )

    # TODO: Reload current UI state
plans_allowed_updated.connect(update_plan_ui)
devices_allowed_updated.connect(update_devices)
