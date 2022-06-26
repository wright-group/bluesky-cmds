import time

### global classes ############################################################


class SimpleGlobal:
    def __init__(self, initial_value=None):
        self.value = initial_value

    def read(self):
        return self.value

    def write(self, value):
        self.value = value


### other globals #############################################################
# alphabetical

class progress_bar:
    def __init__(self):
        self.value = None

    def write(self, value):
        self.value = value

    def give_time_display_elements(self, time_elapsed, time_remaining):
        self.time_elapsed = time_elapsed
        self.time_remaining = time_remaining

    def begin_new_scan_timer(self):
        self.start_time = time.time()
        self.set_fraction(0)

    def set_fraction(self, fraction):
        self.value.setValue(int(round(fraction * 100)))
        # time elapsed
        time_elapsed = time.time() - self.start_time
        m, s = divmod(time_elapsed, 60)
        h, m = divmod(m, 60)
        self.time_elapsed.setText("%02d:%02d:%02d" % (h, m, s))
        # time remaining
        if fraction == 0:
            self.time_remaining.setText("??:??:??")
        else:
            time_remaining = (time_elapsed / fraction) - time_elapsed
            m, s = divmod(time_remaining, 60)
            h, m = divmod(m, 60)
            self.time_remaining.setText("%02d:%02d:%02d" % (h, m, s))

    def set_color(self, color):
        from .colors import colors
        self.value.setStyleSheet(f"""
        QProgressBar:horizontal{{border: 0px solid gray; border-radius: 0px; background: {colors["background"]}; padding: 0px; height: 30px;}}
        QProgressBar:chunk{{background:{colors[color]} }}
        """)


progress_bar = progress_bar()


class shutdown(SimpleGlobal):
    """
    holds the reference of MainWindow.shutdown Qt signal

    during startup, add your shutdown method to this object using the 'add_method' method it will be called upon shutdown.
    your method must not have any arguments
    """

    def __init__(self, initial_value=None):
        super().__init__(initial_value)
        self.methods = []

    def add_method(self, method):
        self.methods.append(method)

    def fire(self):
        for method in self.methods:
            method()

shutdown = shutdown()
