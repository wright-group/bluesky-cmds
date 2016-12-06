### import ####################################################################


from __future__ import absolute_import, division, print_function, unicode_literals

import os
import imp
import collections

from PyQt4 import QtCore

import project.project_globals as g
main_dir = g.main_dir.read()
app = g.app.read()
import project.widgets as pw
import project.ini_handler as ini
ini = ini.filters
import project.classes as pc


### address ###################################################################


class ND(pc.Address):

    def dummy(self):
        print('hello world im a dummy method')


# list module path, module name, class name, initialization arguments, friendly name
hardware_dict = collections.OrderedDict()
hardware_dict['ND0 homebuilt'] = [os.path.join(main_dir, 'hardware', 'filters', 'homebuilt', 'homebuilt.py'), 'homebuilt_NDs', 'Driver', [0], 'nd0']
hardware_dict['ND1 homebuilt'] = [os.path.join(main_dir, 'hardware', 'filters', 'homebuilt', 'homebuilt.py'), 'homebuilt_NDs', 'Driver', [1], 'nd1']
hardware_dict['ND2 homebuilt'] = [os.path.join(main_dir, 'hardware', 'filters', 'homebuilt', 'homebuilt.py'), 'homebuilt_NDs', 'Driver', [2], 'nd2']

hardwares = []
for key in hardware_dict.keys():
    if ini.read('hardware', key):
        lis = hardware_dict[key]
        hardware_module = imp.load_source(lis[1], lis[0])
        hardware_class = getattr(hardware_module, lis[2])
        hardware_obj = pc.Hardware(hardware_class, lis[3], ND, key, True, lis[4])
        hardwares.append(hardware_obj)


### gui #######################################################################


gui = pw.HardwareFrontPanel(hardwares, name='NDs')
advanced_gui = pw.HardwareAdvancedPanel(hardwares, gui.advanced_button)