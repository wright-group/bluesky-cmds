### import ####################################################################

import collections
import functools
import pprint

from qtpy import QtCore, QtGui, QtWidgets

from .comms import RM
from bluesky_queueserver_api import BInst, BPlan

import bluesky_cmds.project.project_globals as g
import bluesky_cmds.project.classes as pc
import bluesky_cmds.project.widgets as pw
from bluesky_cmds.project.colors import colors

import bluesky_cmds.somatic as somatic

from . import plan_ui
from . import presets

### GUI #######################################################################


class GUI(QtCore.QObject):
    def __init__(self, parent_widget, message_widget):
        QtCore.QObject.__init__(self)
        self.progress_bar = g.progress_bar
        # frame, widgets
        self.message_widget = message_widget
        self.parent_widget = parent_widget
        parent_widget.setLayout(QtWidgets.QHBoxLayout())
        parent_widget.layout().setContentsMargins(0, 10, 0, 0)
        self.layout = parent_widget.layout()
        self.create_frame()
        self.interrupt_choice_window = pw.ChoiceWindow(
            "QUEUE INTERRUPTED", button_labels=["RESUME", "STOP AFTER PLAN", "SKIP", "STOP NOW"]
        )
        self.clear_choice_window = pw.ChoiceWindow(
            "QUEUE CLEAR", button_labels=["no", "YES"]
        )
        # queue
        self.queue = []
        self.history = []
        self.running = {}
        self.update_ui()
        somatic.signals.queue_updated.connect(self.update_queue)
        somatic.signals.history_updated.connect(self.update_history)
        somatic.signals.plans_allowed_updated.connect(self.rebuild_plan_ui)
        somatic.signals.devices_allowed_updated.connect(self.rebuild_plan_ui)

    def add_button_to_table(self, i, j, text, color):
        button = pw.SetButton(text, color=color)
        button.setProperty("TableRowIndex", i)
        self.table.setCellWidget(i, j, button)
        return button

    def add_index_to_table(self, table_index, queue_index, max_value):
        # for some reason, my lambda function does not work when called outside
        # of a dedicated method - Blaise 2016-09-14
        index = QtWidgets.QSpinBox()
        StyleSheet = f"QSpinBox{{color: {colors['text_light']}; font: 14px;}}"
        StyleSheet += f"QScrollArea, QWidget{{background: {colors['background']};  border-color: black; border-radius: 0px;}}"
        StyleSheet += f"QWidget:disabled{{color: {colors['text_disabled']}; font: 14px; border: 0px solid black; border-radius: 0px;}}"
        index.setStyleSheet(StyleSheet)
        # index.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        index.setMaximum(max_value)
        index.setAlignment(QtCore.Qt.AlignCenter)
        index.setValue(queue_index)
        index.setProperty("TableRowIndex", table_index)
        index.editingFinished.connect(
            lambda: self.on_index_changed(queue_index, int(index.value()))
        )
        self.table.setCellWidget(table_index, 0, index)
        return index

    def create_frame(self):
        # queue display -------------------------------------------------------
        # container widget
        display_container_widget = pw.ExpandingWidget()
        display_layout = display_container_widget.layout()
        display_layout.setContentsMargins(0, 0, 0, 0)
        # table
        self.table = pw.TableWidget()
        self.table.verticalHeader().hide()
        self.table_cols = collections.OrderedDict()
        self.table_cols["Index"] = 50
        self.table_cols["Type"] = 150
        self.table_cols["Status"] = 85
        self.table_cols["Description"] = 200  # expanding
        self.table_cols["Remove"] = 75
        self.table_cols["Load"] = 75
        for i in range(len(self.table_cols.keys())):
            self.table.insertColumn(i)
        labels = list(self.table_cols.keys())
        labels[-1] = ""
        labels[-2] = ""
        self.table.setHorizontalHeaderLabels(labels)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        self.table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        for i, width in enumerate(self.table_cols.values()):
            self.table.setColumnWidth(i, width)
        # controls ------------------------------------------------------------
        settings_container_widget = QtWidgets.QWidget()
        settings_scroll_area = pw.scroll_area()
        settings_scroll_area.setWidget(settings_container_widget)
        settings_scroll_area.setMinimumWidth(300)
        settings_scroll_area.setMaximumWidth(300)
        settings_container_widget.setLayout(QtWidgets.QVBoxLayout())
        settings_layout = settings_container_widget.layout()
        self.settings_layout = settings_layout
        settings_layout.setContentsMargins(5, 5, 5, 5)
        # adjust queue label
        input_table = pw.InputTable()
        input_table.add("Control Queue", None)
        settings_layout.addWidget(input_table)
        # go button
        self.queue_start = pw.SetButton("START QUEUE")
        self.queue_start.clicked.connect(self.on_queue_start_clicked)
        settings_layout.addWidget(self.queue_start)
        somatic.signals.queue_relinquishing_control.connect(self.queue_start.show)
        somatic.signals.queue_taking_control.connect(self.queue_start.hide)
        self.interrupt = pw.SetButton("INTERRUPT", "stop")
        self.interrupt.clicked.connect(self.on_interrupt_clicked)
        settings_layout.addWidget(self.interrupt)
        somatic.signals.queue_relinquishing_control.connect(self.interrupt.hide)
        somatic.signals.queue_taking_control.connect(self.interrupt.show)
        line = pw.Line("H")
        settings_layout.addWidget(line)
        self.clear = pw.SetButton("CLEAR QUEUE", "stop")
        self.clear.clicked.connect(self.on_clear_clicked)
        settings_layout.addWidget(self.clear)
        self.clear_history = pw.SetButton("CLEAR HISTORY", "stop")
        self.clear_history.clicked.connect(self.on_clear_history_clicked)
        settings_layout.addWidget(self.clear_history)
        # horizontal line
        line = pw.Line("H")
        settings_layout.addWidget(line)
        # type combobox
        input_table = pw.InputTable()
        allowed_values = ["plan", "instruction", "preset"]
        self.type_combo = pc.Combo(allowed_values=allowed_values)
        self.type_combo.updated.connect(self.update_type)
        input_table.add("Add to Queue", None)
        input_table.add("Type", self.type_combo)
        settings_layout.addWidget(input_table)
        # frames
        self.type_frames = {
            "plan": self.create_plan_frame(),
            "instruction": self.create_instruction_frame(),
            "preset": self.create_preset_frame(),
        }
        for frame in self.type_frames.values():
            settings_layout.addWidget(frame)
            frame.hide()
        self.update_type()
        # finish --------------------------------------------------------------
        settings_layout.addStretch(1)
        # line ----------------------------------------------------------------
        self.layout.addWidget(settings_scroll_area)
        line = pw.Line("V")
        self.layout.addWidget(line)
        self.layout.addWidget(display_container_widget)
        display_layout.addWidget(self.table)

    def create_instruction_frame(self):
        button = pw.SetButton("Append Queue Stop")
        button.clicked.connect(lambda: RM.item_add(BInst("queue_stop")))
        return button
    
    def update_presets(self):
        vals = presets.get_preset_names()
        self.append_preset_button.setDisabled(False)
        if not vals:
            vals = ["No Presets"]
            self.append_preset_button.setDisabled(True)
        self.preset.set_allowed_values(vals)

    def create_preset_frame(self):
        frame = QtWidgets.QWidget()
        frame.setLayout(QtWidgets.QVBoxLayout())
        layout = frame.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        input_table = pw.InputTable()
        vals = presets.get_preset_names()
        if not vals:
            vals = ["No Presets"]
        self.preset = pc.Combo(allowed_values = vals)
        input_table.add("Preset", self.preset)
        self.append_preset_button = pw.SetButton("Append Preset Plans")
        self.append_preset_button.clicked.connect(self.on_append_preset)
        layout.addWidget(input_table)
        self.edit_preset_button = pw.SetButton("Edit Preset Plans", color="advanced")
        self.edit_preset_button.clicked.connect(self.on_edit_preset)
        layout.addWidget(self.edit_preset_button)
        layout.addWidget(self.append_preset_button)
        return frame

    def on_append_preset(self):
        preset = self.preset.read()
        for item in presets.get_preset_items(preset):
            # TODO add metadata here
            RM.item_add(item)

    def on_edit_preset(self):
        preset = self.preset.read()
        presets.open_preset_file(preset)

    def show_preset_dialog(self, item):
        input_dia = QtWidgets.QInputDialog()
        new = "New Preset..."
        vals = presets.get_preset_names() + [new]
        name, ok = input_dia.getItem(self.parent_widget, "Preset", "Select a preset", vals)
        if ok and name == new:
            name, ok = input_dia.getText(self.parent_widget, "Preset", "Name of new preset")

        if ok:
            presets.append_preset_item(name, item)
        self.update_presets()


    def create_plan_frame(self):
        frame = QtWidgets.QWidget()
        frame.setLayout(QtWidgets.QVBoxLayout())
        layout = frame.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        input_table = pw.InputTable()
        try:
            allowed_plans = RM.plans_allowed()
        except:
            allowed_plans = {"plans_allowed": {"count": None}}
        allowed_values = allowed_plans["plans_allowed"].keys()
        self.plan_combo = pc.Combo(allowed_values=allowed_values)
        self.plan_combo.updated.connect(self.on_plan_selected)
        input_table.add("Plan", self.plan_combo)
        layout.addWidget(input_table)
        self.plan_widgets = {x: plan_ui.plan_ui_lookup[x] for x in allowed_values}
        self.on_plan_selected()
        for widget in self.plan_widgets.values():
            layout.addWidget(widget.frame)
        append_button = pw.SetButton("APPEND TO QUEUE")
        append_button.clicked.connect(self.on_append_to_queue)
        layout.addWidget(append_button)
        return frame

    def rebuild_plan_ui(self):
        for frame in self.type_frames.values():
            self.settings_layout.removeWidget(frame)
            frame.hide()
            frame.close()
        self.type_frames["plan"] = self.create_plan_frame()
        for frame in self.type_frames.values():
            self.settings_layout.insertWidget(8, frame)
            frame.hide()
        self.on_load_item(self.get_plan().to_dict())
        self.update_type()

    def get_plan(self):
        plan_name = self.plan_combo.read()
        widget = self.plan_widgets[plan_name]
        kwargs = widget.kwargs
        meta = kwargs.pop("md", {})
        plan = BPlan(plan_name, *widget.args, **kwargs)
        plan.meta = meta
        return plan

    def on_append_to_queue(self):
        plan = self.get_plan()
        RM.item_add(plan)

    def on_queue_start_clicked(self):
        RM.queue_start()

    def on_interrupt_clicked(self):
        RM.re_pause("immediate")
        self.interrupt_choice_window.set_text("Please choose how to proceed.")
        index = self.interrupt_choice_window.show()
        if index == 0:  # RESUME
            RM.re_resume()
        elif index == 1:  # STOP AFTER PLAN
            RM.re_resume()
            RM.queue_stop()
        elif index == 2:  # HALT
            RM.re_stop()
        elif index == 3:  # HALT
            RM.re_abort()
        # TODO Recover skip behavior... may require upstream change to be sane

    def on_clear_clicked(self):
        self.clear_choice_window.set_text("Do you want to clear the queue?")
        index = self.clear_choice_window.show()
        if index == 1:
            RM.queue_clear()

    def on_clear_history_clicked(self):
        self.clear_choice_window.set_text("Do you want to clear the history?")
        index = self.clear_choice_window.show()
        if index == 1:
            RM.history_clear()

    def on_index_changed(self, row, new_index):
        item = self.queue[row]
        RM.item_move(uid=item["item_uid"], pos_dest=new_index)

    def on_remove_item(self, row):
        item = self.queue[row]
        RM.item_remove(uid=item["item_uid"])

    def on_load_item(self, item):
        self.plan_combo.write(item["name"])
        kwargs = item.get("kwargs", {})
        kwargs["md"] = item.get("meta", {})
        self.plan_widgets[item["name"]].args = item.get("args", [])
        self.plan_widgets[item["name"]].kwargs = kwargs

    def update_type(self):
        for frame in self.type_frames.values():
            frame.hide()
        self.type_frames[self.type_combo.read()].show()

    def on_plan_selected(self):
        for frame in self.plan_widgets.values():
            frame.frame.hide()
        self.plan_widgets[self.plan_combo.read()].frame.show()

    def update_queue(self):
        queue_get = RM.queue_get()
        self.queue = queue_get.get("items", [])
        self.running = queue_get.get("running_item", {})
        self.update_ui()

    def update_history(self):
        history_get = RM.history_get()
        self.history = history_get.get("items", [])
        self.update_ui()

    def update_ui(self):
        # clear table
        for _ in range(self.table.rowCount()):
            self.table.removeRow(0)

        def copy_info(_, info):
            QtGui.QGuiApplication.clipboard().setText(info)

        def add_item(item, status=None, queue_index=None, append=False):
            table_index = self.table.rowCount() if append else 0
            self.table.insertRow(table_index)
            if queue_index is not None:
                self.add_index_to_table(table_index, queue_index, len(self.queue) - 1)
            # type
            label = pw.Label(item["name"])
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setContentsMargins(3, 3, 3, 3)
            self.table.setCellWidget(table_index, 1, label)
            # status
            label = pw.Label(status or item.get("result", {}).get("exit_status"))
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setContentsMargins(3, 3, 3, 3)
            self.table.setCellWidget(table_index, 2, label)
            # description
            container = QtWidgets.QWidget()
            label = pw.Label(repr(item.get("args", [])) + repr(item.get("kwargs", {})))
            label.setContentsMargins(3, 3, 3, 3)
            label.setToolTip(pprint.pformat(item))
            label.setDisabled(True)
            container.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
            copyJsonAction = QtWidgets.QAction("Copy JSON", container)
            copyJsonAction.triggered.connect(functools.partial(copy_info, info=pprint.pformat(item)))
            container.addAction(copyJsonAction)
            copyItemUidAction = QtWidgets.QAction("Copy Item UID", container)
            copyItemUidAction.triggered.connect(functools.partial(copy_info, info=item["item_uid"]))
            container.addAction(copyItemUidAction)
            label.setParent(container)
            self.table.setCellWidget(table_index, 3, container)

            if "result" in item and item["result"]["run_uids"]:
                # TODO: account for multiple runs, currently nothing we use actually does multiple runs
                # So I'm ignoring the possibility (wasn't trivial to get it to work -- KFS 2022-06-16
                copyRunIdAction = QtWidgets.QAction("Copy Run UID", container)
                copyRunIdAction.triggered.connect(functools.partial(copy_info, info=item["result"]["run_uids"][0]))
                container.addAction(copyRunIdAction)

            appendPresetAction = QtWidgets.QAction("Append to preset...", container)
            appendPresetAction.triggered.connect(functools.partial(self.show_preset_dialog, item=item))
            container.addAction(appendPresetAction)

            # remove
            if status == "enqueued":
                button = self.add_button_to_table(table_index, 4, "REMOVE", "stop")

                def rem():
                    self.on_remove_item(queue_index)

                button.clicked.connect(rem)
            if status in ("enqueued", "RUNNING"):
                label.setDisabled(False)

            def load():
                self.on_load_item(item)

            button = self.add_button_to_table(table_index, 5, "LOAD", "go")
            button.clicked.connect(load)

        # add elements from history
        for i, item in enumerate(self.history):
            if item == {}:
                continue
            add_item(item)

        if self.running:
            add_item(self.running, "RUNNING")

        # add elements from queue
        for i, item in enumerate(self.queue):
            if item == {}:
                continue
            add_item(item, "enqueued", i)
