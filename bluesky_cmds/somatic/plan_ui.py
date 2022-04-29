from collections import defaultdict
import itertools
import json

import toolz
from qtpy import QtWidgets
from bluesky_queueserver.manager.comms import zmq_single_request
from bluesky_hwproxy import zmq_single_request as hwproxy_request

import WrightTools as wt
from bluesky_cmds.project import widgets as pw
from bluesky_cmds.project import classes as pc

devices_all_json = zmq_single_request("devices_allowed", {"user_group": "admin"})[0]["devices_allowed"]
devices_all = {}


def get_all_components(k, v):
    out = {k: v}
    for sk, sv in v.get("components", {}).items():
        out.update(get_all_components(".".join([k, sk]), sv))
    return out


for k, v in devices_all_json.items():
    devices_all.update(get_all_components(k, v))


devices_movable = list(filter(lambda x: devices_all[x]["is_movable"], devices_all))
devices_not_movable = list(filter(lambda x: not devices_all[x]["is_movable"], devices_all))


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
        self.frame = QtWidgets.QWidget()
        self.frame.setLayout(QtWidgets.QVBoxLayout())
        layout = self.frame.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        for x in self.items:
            layout.addWidget(x.frame)

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
        self.fields = {
            "Name": pc.String(),
            "Info": pc.String(),
            "Experimentor": pc.Combo(["Kyle", "Emily", "Kelson", "Dan"]),
        }

    @property
    def frame(self):
        frame = pw.InputTable()
        frame.add("Metadata", None)
        for k, v in self.fields.items():
            frame.add(k, v)
        return frame

    @property
    def args(self):
        return []

    @args.setter
    def args(self, arg):
        pass

    @property
    def kwargs(self):
        return {"md": {k: v.read() for k, v in self.fields.items()}}

    @kwargs.setter
    def kwargs(self, kwargs):
        md = kwargs.get("md", {})
        for k, v in self.fields.items():
            if k in md:
                v.write(md[k])


class ArgsWidget:
    def __init__(self):
        self.nargs = -1
        self.frame = pw.InputTable()
        self.args_input = pc.String()
        self.frame.add("Args", self.args_input)

    @property
    def args(self):
        return json.loads(self.args_input.read() or "[]")

    @args.setter
    def args(self, args):
        self.args_input.write(json.dumps(args))

    @property
    def kwargs(self):
        return {}

    @kwargs.setter
    def kwargs(self, kwargs):
        pass


class KwargsWidget:
    def __init__(self):
        self.nargs = 0
        self.frame = pw.InputTable()
        self.kwargs_input = pc.String()
        self.frame.add("Kwargs", self.kwargs_input)

    @property
    def kwargs(self):
        return json.loads(self.kwargs_input.read() or "{}")

    @kwargs.setter
    def kwargs(self, kwargs):
        self.kwargs_input.write(json.dumps(kwargs))

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
        self.frame = pw.InputTable()
        self.frame.add(name, self.input)
        self.kwarg = kwarg

    @property
    def args(self):
        return [self.input.read()] if not self.kwarg else []

    @args.setter
    def args(self, arg):
        if arg:
            self.input.write(arg[0])

    @property
    def kwargs(self):
        return {self.kwarg: self.input.read()} if self.kwarg else {}

    @kwargs.setter
    def kwargs(self, kwargs):
        if self.kwarg in kwargs:
            self.args = [kwargs[self.kwarg]]


class BoolWidget(SingleWidget):
    def __init__(self, name, kwarg=None):
        self.input = pc.Bool()
        super().__init__(name, kwarg)


class StrWidget(SingleWidget):
    def __init__(self, name, kwarg=None):
        self.input = pc.String()
        super().__init__(name, kwarg)


class IntWidget(SingleWidget):
    def __init__(self, name, kwarg=None, default=0):
        self.input = pc.Number(decimals=0, initial_value=default)
        super().__init__(name, kwarg)

    @property
    def args(self):
        return [int(self.input.read())] if not self.kwarg else []
    
    @args.setter
    def args(self, arg):
        if arg:
            self.input.write(arg[0])

    @property
    def kwargs(self):
        return {self.kwarg: int(self.input.read())} if self.kwarg else {}

    @kwargs.setter
    def kwargs(self, kwargs):
        if self.kwarg in kwargs:
            self.args = [kwargs[self.kwarg]]


class FloatWidget(SingleWidget):
    def __init__(self, name, kwarg=None, default=0):
        self.input = pc.Number(initial_value=default)
        super().__init__(name, kwarg)


class EnumWidget(SingleWidget):
    def __init__(self, name, options: dict, kwarg=None):
        self.input = pc.Combo(options.keys())
        super().__init__(name, kwarg)
        self.options = options

    @property
    def args(self):
        return [self.options[self.input.read()]] if not self.kwarg else []

    @args.setter
    def args(self, arg):
        if arg:
            for k, v in self.options.items():
                if arg == v:
                    self.input.write(k)
                    break

    @property
    def kwargs(self):
        return {self.kwarg: self.options[self.input.read()]} if self.kwarg else {}

    @kwargs.setter
    def kwargs(self, kwargs):
        if self.kwarg in kwargs:
            self.args = [kwargs[self.kwarg]]


class DeviceListWidget:
    def __init__(self):
        self.nargs = 1
        self.inputs = {k: pc.Bool(True) for k in devices_not_movable}
        self.frame = pw.InputTable()
        self.frame.add("Devices", None)
        for k, v in self.inputs.items():
            self.frame.add(k, v)

    @property
    def kwargs(self):
        return {}

    @kwargs.setter
    def kwargs(self, kwargs):
        pass

    @property
    def args(self):
        return [[k for k, v in self.inputs.items() if v.read()]]

    @args.setter
    def args(self, args):
        arg = args[0]
        for device in self.inputs:
            if device in arg:
                self.inputs[device].write(True)
            else:
                self.inputs[device].write(False)


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


class Constant(pw.InputTable):
    def __init__(self, hardware, units, terms):
        super().__init__()
        self.add("Constant", None)
        self.hardware = pc.Combo(devices_movable)
        self.hardware.write(hardware)
        self.hardware.updated.connect(self.on_hardware_updated)
        self.add("Hardware", self.hardware)
        self.units = pc.Combo(wt.units.blessed_units)
        self.units.write(units)
        self.add("Units", self.units)
        self.expression = pc.String()
        self.expression.write(
            " + ".join(f"{coeff}*{hw}" if hw else f"{coeff}" for coeff, hw in terms)
        )
        self.add("Expression", self.expression)
        self.on_hardware_updated()

    @property
    def args(self):
        units = self.units.read()
        if units == "None":
            units = None
        return [self.hardware.read(), units, self.terms]

    @property
    def terms(self):
        import sympy

        expr = sympy.parse_expr(self.expression.read())
        coeffs = expr.as_coefficients_dict()

        for k, v in list(coeffs.items()):
            del coeffs[k]
            if isinstance(k, sympy.Number):
                coeffs[None] = float(k*v)
            else:
                coeffs[k.name] = float(v)
        return [(v, k) for k, v in coeffs.items()]

    def on_hardware_updated(self):
        hw_name = self.hardware.read()
        base_name = hw_name.split(".")[0]
        key_name = hw_name.replace(".", "_")
        native = hwproxy_request("describe", {"device": base_name})[0]["return"][key_name].get("units", None)
        units_list = [i for i in (native,) + wt.units.get_valid_conversions(native) if i != "mm_delay"]
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


class GridscanAxis(pw.InputTable):
    def __init__(self, hardware, start, stop, npts, units):
        super().__init__()
        self.add("Axis", None)
        self.hardware = pc.Combo(devices_movable)
        self.hardware.write(hardware)
        self.hardware.updated.connect(self.on_hardware_updated)
        self.add("Hardware", self.hardware)
        self.start = pc.Number(start)
        self.add("Start", self.start)
        self.stop = pc.Number(stop)
        self.add("Stop", self.stop)
        self.npts = pc.Number(npts, decimals=0)
        self.add("Npts", self.npts)
        self.units = pc.Combo(wt.units.blessed_units)
        self.units.write(units)
        self.add("Units", self.units)
        self.on_hardware_updated()

    @property
    def args(self):
        units = self.units.read()
        if units == "None":
            units = None
        return [
            self.hardware.read(),
            self.start.read(),
            self.stop.read(),
            int(self.npts.read()),
            units,
        ]

    def on_hardware_updated(self):
        hw_name = self.hardware.read()
        base_name = hw_name.split(".")[0]
        key_name = hw_name.replace(".", "_")
        native = hwproxy_request("describe", {"device": base_name})[0]["return"][key_name].get("units", None)
        units_list = [i for i in (native,) + wt.units.get_valid_conversions(native) if i != "mm_delay"]
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


class ScanAxis(pw.InputTable):
    def __init__(self, hardware, start, stop, units):
        super().__init__()
        self.add("Axis", None)
        self.hardware = pc.Combo(devices_movable)
        self.hardware.write(hardware)
        self.add("Hardware", self.hardware)
        self.hardware.updated.connect(self.on_hardware_updated)
        self.start = pc.Number(start)
        self.add("Start", self.start)
        self.stop = pc.Number(stop)
        self.add("Stop", self.stop)
        self.units = pc.Combo(wt.units.blessed_units)
        self.units.write(units)
        self.add("Units", self.units)
        self.on_hardware_updated()

    @property
    def args(self):
        units = self.units.read()
        if units == "None":
            units = None
        return [
            self.hardware.read(),
            self.start.read(),
            self.stop.read(),
            units,
        ]


    def on_hardware_updated(self):
        hw_name = self.hardware.read()
        base_name = hw_name.split(".")[0]
        key_name = hw_name.replace(".", "_")
        native = hwproxy_request("describe", {"device": base_name})[0]["return"][key_name].get("units", None)
        units_list = [i for i in (native,) + wt.units.get_valid_conversions(native) if i != "mm_delay"]
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


class ListAxis(pw.InputTable):
    def __init__(self, hardware, list, units):
        super().__init__()
        self.add("Axis", None)
        self.hardware = pc.Combo(devices_movable)
        self.hardware.write(hardware)
        self.add("Hardware", self.hardware)
        self.hardware.updated.connect(self.on_hardware_updated)
        self.list = pc.String()
        self.list.write(json.dumps(list) or "[]")
        self.add("List", self.list)
        self.units = pc.Combo(wt.units.blessed_units)
        self.units.write(units)
        self.add("Units", self.units)
        self.on_hardware_updated()

    @property
    def args(self):
        units = self.units.read()
        if units == "None":
            units = None
        return [
            self.hardware.read(),
            json.loads(self.list.read()) or [],
            units,
        ]


    def on_hardware_updated(self):
        hw_name = self.hardware.read()
        base_name = hw_name.split(".")[0]
        key_name = hw_name.replace(".", "_")
        native = hwproxy_request("describe", {"device": base_name})[0]["return"][key_name].get("units", None)
        units_list = [i for i in (native,) + wt.units.get_valid_conversions(native) if i != "mm_delay"]
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
        super().__init__(name, options={"w1": "w1", "w2": "w2"})
        # TODO dynamically fill out options


class OpaMotorSelectorWidget(EnumWidget):
    def __init__(self, name="motor"):
        motors = {
            x: x
            for x in filter(lambda x: x.startswith("w1.") or x.startswith("w2."), devices_movable)
        }
        if not motors:
            motors = {"None": None}
        super().__init__(name, options=motors)
        # TODO dynamically fill out options, mutual exclusion


class OpaMotorFullWidget:
    def __init__(self):
        self.frame = QtWidgets.QWidget()
        self.frame.setLayout(QtWidgets.QVBoxLayout())

    @property
    def args(self):
        return []

    @property
    def kwargs(self):
        return {}


class SpectrometerWidget(pw.InputTable):
    def __init__(self):
        super().__init__()
        self.nargs = 1
        self.frame = self
        self.device = pc.Combo(["None"] + devices_movable)
        self.add("Device", self.device)
        self.method = pc.Combo(["none", "static", "zero", "track", "set", "scan"])
        self.add("Method", self.method)
        self.center = pc.Number()
        self.add("Center", self.center)
        self.width = pc.Number(-250)
        self.add("Width", self.width)
        self.npts = pc.Number(11, decimals=0)
        self.add("Npts", self.npts)

    @property
    def args(self):
        device = self.device.read()
        if device == "None":
            device = None
        return [
            {
                "device": device,
                "method": self.method.read(),
                "center": self.center.read(),
                "width": self.width.read(),
                "npts": int(self.npts.read()),
            }
        ]

    @property
    def kwargs(self):
        return {}


plan_ui_lookup = defaultdict(PlanUI)
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
plan_ui_lookup["count"] = PlanUI(
    [
        MetadataWidget(),
        DeviceListWidget(),
        IntWidget("Npts", "num", 1),
        FloatWidget("Delay", "delay", 0),
    ]
)
plan_ui_lookup["run_tune_test"] = PlanUI(
    [
        MetadataWidget(),
        DeviceListWidget(),
        OpaSelectorWidget(),
        SpectrometerWidget(),
    ]
)
plan_ui_lookup["run_setpoint"] = PlanUI(
    [
        MetadataWidget(),
        DeviceListWidget(),
        OpaSelectorWidget(),
        OpaMotorSelectorWidget(),
        FloatWidget("Width", "width", 1),
        IntWidget("Npts", "npts", 11),
        SpectrometerWidget(),
    ]
)
plan_ui_lookup["run_intensity"] = PlanUI(
    [
        MetadataWidget(),
        DeviceListWidget(),
        OpaSelectorWidget(),
        OpaMotorSelectorWidget(),
        FloatWidget("Width", "width", 1),
        IntWidget("Npts", "npts", 11),
        SpectrometerWidget(),
    ]
)
plan_ui_lookup["run_holistic"] = PlanUI(
    [
        MetadataWidget(),
        DeviceListWidget(),
        OpaSelectorWidget(),
        OpaMotorSelectorWidget(),
        OpaMotorSelectorWidget(),
        FloatWidget("Width", "width", 1),
        IntWidget("Npts", "npts", 11),
        SpectrometerWidget(),
    ]
)
plan_ui_lookup["motortune"] = PlanUI(
    [
        MetadataWidget(),
        DeviceListWidget(),
        OpaSelectorWidget(),
        OpaMotorFullWidget(),
        SpectrometerWidget(),
    ]
)
