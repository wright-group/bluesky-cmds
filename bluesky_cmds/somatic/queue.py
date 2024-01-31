### import ####################################################################

import collections
import functools
import pprint

from qtpy import QtCore, QtGui, QtWidgets
import qtypes

from .comms import RM
from bluesky_queueserver_api import BInst, BPlan

import bluesky_cmds.project.project_globals as g
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
        self.env_close_choice_window = pw.ChoiceWindow(
            "ENVIRONMENT CLOSE", button_labels=["no", "YES"]
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
        self.settings_layout = qtypes.Null()
        # adjust queue label
        control_queue = qtypes.Null("Control Queue")
        self.settings_layout.append(control_queue)
        # go button
        self.queue_start = qtypes.Button("START QUEUE")
        self.queue_start.updated_connect(self.on_queue_start_clicked)
        control_queue.append(self.queue_start)
        #somatic.signals.queue_relinquishing_control.connect(self.queue_start.show)
        #somatic.signals.queue_taking_control.connect(self.queue_start.hide)
        self.interrupt = qtypes.Button("INTERRUPT")
        self.interrupt.updated_connect(self.on_interrupt_clicked)
        control_queue.append(self.interrupt)
        #somatic.signals.queue_relinquishing_control.connect(self.interrupt.hide)
        #somatic.signals.queue_taking_control.connect(self.interrupt.show)
        self.env_close = qtypes.Button("CLOSE ENVIRONMENT")
        self.env_close.updated_connect(self.on_env_close_clicked)
        control_queue.append(self.env_close)
        self.clear = qtypes.Button("CLEAR QUEUE")
        self.clear.updated_connect(self.on_clear_clicked)
        control_queue.append(self.clear)
        self.clear_history = qtypes.Button("CLEAR HISTORY")
        self.clear_history.updated_connect(self.on_clear_history_clicked)
        control_queue.append(self.clear_history)
        # type combobox
        select_type = qtypes.Null("Add to Queue")
        allowed_values = ["plan", "instruction", "preset"]
        self.type_combo = qtypes.Enum("Type", allowed=allowed_values)
        self.settings_layout.append(select_type)
        # frames
        self.type_frames = {
            "plan": self.create_plan_frame(),
            "instruction": self.create_instruction_frame(),
            "preset": self.create_preset_frame(),
        }
        self.type_combo.updated_connect(self.update_type)
        select_type.append(self.type_combo)
        self.update_type()
        # line ----------------------------------------------------------------
        tree_widget = qtypes.TreeWidget(self.settings_layout)
        tree_widget.setMinimumWidth(300)
        tree_widget.setMaximumWidth(300)
        tree_widget[0].expand()
        self.layout.addWidget(tree_widget)
        line = pw.Line("V")
        self.layout.addWidget(line)
        self.layout.addWidget(display_container_widget)
        display_layout.addWidget(self.table)

    def create_instruction_frame(self):
        button = qtypes.Button("Append Queue Stop")
        button.updated_connect(lambda _: RM.item_add(BInst("queue_stop")))
        return [button]
    
    def update_presets(self, _=None):
        vals = presets.get_preset_names()
        self.append_preset_button.setDisabled(False)
        if not vals:
            vals = ["No Presets"]
            self.append_preset_button.setDisabled(True)
        self.preset.set({"allowed": vals})

    def create_preset_frame(self):
        vals = presets.get_preset_names()
        if not vals:
            vals = ["No Presets"]
        self.preset = qtypes.Enum("Preset", allowed=vals)
        self.append_preset_button = qtypes.Button("Append Preset Plans")
        self.append_preset_button.updated_connect(self.on_append_preset)
        self.edit_preset_button = qtypes.Button("Edit Preset Plans")
        self.edit_preset_button.updated_connect(self.on_edit_preset)
        return [self.preset, self.edit_preset_button, self.append_preset_button]

    def on_append_preset(self, _=None):
        preset = self.preset.get_value()
        for item in presets.get_preset_items(preset):
            # TODO add metadata here
            RM.item_add(item)

    def on_edit_preset(self, _=None):
        preset = self.preset.get_value()
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
        try:
            allowed_plans = RM.plans_allowed()
        except:
            allowed_plans = {"plans_allowed": {"connecting...": None}}
        allowed_values = list(allowed_plans["plans_allowed"].keys())
        self.plan_combo = qtypes.Enum("Plan", allowed=allowed_values)
        self.plan_combo.updated_connect(self.on_plan_selected)
        self.plan_widgets = {x: plan_ui.plan_ui_lookup[x] for x in allowed_values}
        self.on_plan_selected()
        append_button = qtypes.Button("APPEND TO QUEUE")
        append_button.updated_connect(self.on_append_to_queue)
        return [self.plan_combo, append_button]

    def rebuild_plan_ui(self):
        self.type_frames["plan"] = self.create_plan_frame()
        self.on_load_item(self.get_plan().to_dict())
        self.update_type()

    def get_plan(self):
        plan_name = self.plan_combo.get_value()
        if not plan_name:
            # Happens during startup
            return BPlan("sleep", 0)
        widget = self.plan_widgets[plan_name]
        kwargs = widget.kwargs
        meta = kwargs.pop("md", {})
        plan = BPlan(plan_name, *widget.args, **kwargs)
        plan.meta = meta
        return plan

    def on_append_to_queue(self, _=None):
        plan = self.get_plan()
        RM.item_add(plan)

    def on_queue_start_clicked(self, _=None):
        RM.queue_start()

    def on_interrupt_clicked(self, _=None):
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

    def on_clear_clicked(self, _=None):
        self.clear_choice_window.set_text("Do you want to clear the queue?")
        index = self.clear_choice_window.show()
        if index == 1:
            RM.queue_clear()

    def on_clear_history_clicked(self, _=None):
        self.clear_choice_window.set_text("Do you want to clear the history?")
        index = self.clear_choice_window.show()
        if index == 1:
            RM.history_clear()

    def on_env_close_clicked(self, _=None):
        self.env_close_choice_window.set_text("Do you wish to close the worker environment?")
        if RM.status().get("manager_state") == "idle":
            index = self.env_close_choice_window.show()
            if index == 1:
                RM.environment_close()
        else:
            input_dia = QtWidgets.QInputDialog()
            response, ok = input_dia.getText(self.parent_widget, "Environment Destroy", "The queue is not idle, and so a graceful environment close is not possible.\nIf you would like to destroy the environment anyway, type 'destroy':\n")
            if response.lower() == "destroy":
                RM.environment_destroy()

    def on_index_changed(self, row, new_index):
        item = self.queue[row]
        RM.item_move(uid=item["item_uid"], pos_dest=new_index)

    def on_remove_item(self, row):
        item = self.queue[row]
        RM.item_remove(uid=item["item_uid"])

    def on_load_item(self, item):
        self.plan_combo.set_value(item["name"])
        kwargs = item.get("kwargs", {})
        kwargs["md"] = item.get("meta", {})
        self.plan_widgets[item["name"]].args = item.get("args", [])
        self.plan_widgets[item["name"]].kwargs = kwargs

    def update_type(self, _=None):
        self.type_combo.clear()
        if self.type_combo.get_value() in self.type_frames:
            self.type_combo.extend(self.type_frames[self.type_combo.get_value()])

    def on_plan_selected(self, _=None):
        self.plan_combo.clear()
        if self.plan_combo.get_value() in self.plan_widgets:
            self.plan_combo.extend(self.plan_widgets[self.plan_combo.get_value()].frame)

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
