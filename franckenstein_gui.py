#!/usr/bin/env python

import Tkinter as tk
import matplotlib
import matplotlib.animation as animation
from matplotlib import style
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure
import serial, serial.tools.list_ports
import logger
import FileDialog
import tkFileDialog
import atexit
import threading, time
from ConfigParser import SafeConfigParser

version_number = '1.0'

# Setup log
log = logger.Logger('log.txt')

# Retrieve config
config = SafeConfigParser()
config.read('settings.cfg')
cal_factor = float(config.get('measurements', 'cal_factor'))
plot_refresh_rate = int(config.get('performance', 'plot_refresh_rate'))
status_update_refresh_rate = int(config.get('performance', 'status_update_refresh_rate'))
thread_refresh_rate = float(config.get('performance', 'thread_refresh_rate'))
serial_timeout = float(config.get('performance', 'serial_timeout'))

# Setup plot
matplotlib.style.use('ggplot')
plot_fig = Figure(figsize=(5,5), dpi=100)
plot_image = plot_fig.add_subplot(111)
plot_image.set_xlabel('$V_{acc}$ [V]')
plot_image.set_ylabel('$I_{cc}$')
plot_image.set_xlim([0.0, 40.0])
plot_image.set_ylim([0.0, 10.0])

# Serial related stuff
serial_init = False
serial_name = ''
recording = False
saving = False
arduino = None

# Plot data
current_x = 0.0
current_y = 0.0
plot_data = ([current_x, current_y],)

scatter_plot = plot_image.scatter([current_x], [current_y], color='blue')


def do_at_exit():
    log.close_file()
    try:
        arduino.close()
    except AttributeError:
        pass

atexit.register(do_at_exit)


def get_serial_ports():
    result = []
    for port in serial.tools.list_ports.comports():
        result.append(str(port[0]))
    return result


def plot_values(i):
    global plot_data
    col = ''
    if recording:
        plot_data = plot_data + ([current_x, current_y],)
        col = 'red'
    elif saving:
        col = 'red'
    else:
        plot_data = ([current_x, current_y],)
        col = 'blue'
    scatter_plot.set_offsets(plot_data)
    scatter_plot.set_color(col)


def file_save():
        f = tkFileDialog.asksaveasfile(mode='w', defaultextension='.csv')
        if f is None:
            log.write('User chose not to save file')
            return
        save_text = ''
        for point in range(0, len(plot_data)):
            save_text += str(plot_data[point][0]) + ',' + str(plot_data[point][1]) + '\n'
        f.write(save_text)
        log.write('Data saved in file ' + f.name)
        f.close()


def update_pairs(i):
    global current_x, current_y
    while True:
        if serial_init:
            arduino.flush()
            if arduino.inWaiting() > 0:
                serial_in = arduino.readline()
                try:
                    if len(serial_in.split(',')) == 2:
                        current_x = float(serial_in.split(',')[0])*cal_factor
                        current_y = float(serial_in.split(',')[1])
                except ValueError:
                    pass
        else:
            current_x = 0.0
            current_y = 0.0
        time.sleep(thread_refresh_rate)


class MainScreen(tk.Tk):
    def __init__(self, parent):
        tk.Tk.__init__(self, parent)
        self.parent = parent
        self.initialize()

    def initialize(self):
        self.grid()

        info_frame = tk.Frame(self,padx=5,pady=5)
        info_frame.grid(column=0,row=0)
        serial_frame = tk.LabelFrame(info_frame, text='Serial setup', padx=5, pady=5)
        serial_frame.pack(side=tk.TOP,fill='x', expand=True)
        recording_frame = tk.LabelFrame(info_frame, text='Recording', padx=5, pady=5)
        recording_frame.pack(side=tk.TOP,fill='x', expand=True)
        measurement_frame = tk.LabelFrame(info_frame, text='Measurements', padx=5, pady=5)
        measurement_frame.pack(side=tk.BOTTOM,fill='x', expand=True)
        plot_frame = tk.LabelFrame(self, text='Plotter', padx=5, pady=5)
        plot_frame.grid(column=1,row=0)
        self.status_current = tk.StringVar()
        status_label = tk.Label(self, textvariable=self.status_current, bg='gainsboro', fg='black', anchor='w')
        status_label.grid(column=0,row=1,columnspan=2,sticky='EW')

        self.selected_serial = tk.StringVar()
        serial_options = []
        if len(get_serial_ports()) > 0:
            self.selected_serial.set(get_serial_ports()[0])
            serial_options = get_serial_ports()
        else:
            self.selected_serial.set('No serial ports found')
            serial_options = ['No serial ports found']
        serial_menu = apply(tk.OptionMenu, (serial_frame, self.selected_serial) + tuple(serial_options))
        serial_menu.pack(expand=True, side=tk.TOP)
        serial_button = tk.Button(serial_frame, text='Initialise serial', command=self.serial_setup)
        serial_button.pack(expand=True, side=tk.TOP)
        self.serial_label_text = tk.StringVar()
        self.serial_label_text.set('Serial not initialised')
        self.serial_label = tk.Label(serial_frame, textvariable=self.serial_label_text)
        self.serial_label.pack(expand=True, side=tk.BOTTOM)

        self.record_status = tk.StringVar()
        self.record_status.set('Idle')
        self.record_status_label = tk.Label(recording_frame, textvariable=self.record_status)
        self.record_status_label.pack(expand=True, side=tk.RIGHT)
        self.record_start_button = tk.Button(recording_frame, text='Start', state=tk.DISABLED, command=self.record_start_pressed)
        self.record_stop_button = tk.Button(recording_frame, text='Stop',state=tk.DISABLED, command=self.record_stop_pressed)
        self.record_start_button.pack(expand=True, side=tk.LEFT)
        self.record_stop_button.pack(expand=True, side=tk.RIGHT)

        self.measurement_vacc_text = tk.StringVar()
        self.measurement_vacc_text.set('0.0')
        self.measurement_icc_text = tk.StringVar()
        self.measurement_icc_text.set('0.0')
        measurement_vacc_label = tk.Label(measurement_frame, anchor='c', text='Accelerating voltage [V]')
        measurement_vacc_label.pack(side=tk.TOP, fill='x')
        measurement_vacc_value = tk.Label(measurement_frame, bg='gainsboro', anchor='c', textvariable=self.measurement_vacc_text)
        measurement_vacc_value.pack(side=tk.TOP, fill='x')
        measurement_icc_label = tk.Label(measurement_frame, anchor='c', text='Collector current')
        measurement_icc_label.pack(side=tk.TOP, fill='x')
        measurement_icc_value = tk.Label(measurement_frame, bg='gainsboro', anchor='c', textvariable=self.measurement_icc_text)
        measurement_icc_value.pack(side=tk.TOP, fill='x')
        measurement_cal_button = tk.Button(measurement_frame, text='Calibrate to 5V', command=self.measurement_calibrate)
        measurement_cal_button.pack(side=tk.BOTTOM)

        plot_canvas = FigureCanvasTkAgg(plot_fig, plot_frame)
        plot_canvas.show()
        plot_canvas.get_tk_widget().pack(expand=True,side=tk.LEFT,fill=tk.BOTH)
        toolbar = NavigationToolbar2TkAgg(plot_canvas, plot_frame)
        toolbar.update()
        plot_canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.resizable(True, True)

    def serial_setup(self):
        global serial_name, serial_init, arduino
        try:
            if arduino.is_open:
                arduino.close()
        except AttributeError:
            pass
        serial_name = self.selected_serial.get()
        log.write('Attempting to connect to serial ' + serial_name)
        try:
            arduino = serial.Serial(serial_name, baudrate=9600, timeout=serial_timeout)
            serial_init = True
            self.record_start_button.config(state=tk.ACTIVE)
            log.write('Connection successful')
        except:
            log.write('Error finding serial')
            serial_init = False
            self.record_start_button.config(state=tk.DISABLED)
        if serial_init:
            self.serial_label_text.set('Serial initialised')
            self.serial_label.config(fg='medium sea green')
        else:
            self.serial_label_text.set('Initialisation failed')
            self.serial_label.config(fg='red')

    def record_start_pressed(self):
        global recording
        recording = True
        log.write('Recording started')
        self.record_status.set('Recording')
        self.record_status_label.config(fg='red')
        self.record_stop_button.config(state=tk.ACTIVE)
        self.record_start_button.config(state=tk.DISABLED)

    def record_stop_pressed(self):
        global recording, saving
        log.write('Recording stopped')
        self.record_status.set('Idle')
        self.record_status_label.config(fg='black')
        self.record_start_button.config(state=tk.ACTIVE)
        self.record_stop_button.config(state=tk.DISABLED)
        recording = False
        saving = True
        file_save()
        saving = False

    def update_status(self):
        self.status_current.set(log.get_most_recent())
        self.measurement_vacc_text.set(str(round(current_x, 2)))
        self.measurement_icc_text.set(str(round(current_y, 2)))
        self.after(status_update_refresh_rate, self.update_status)

    def measurement_calibrate(self):
        global cal_factor
        log.write('Calibration requested')
        try:
            cal_factor = cal_factor*5.0/current_x
            log.write('Accelerating voltage calibrated with factor: ' + str(round(cal_factor, 2)))
        except ZeroDivisionError:
            log.write('Calibration failed: division by 0')

if __name__ == '__main__':
    log.write('Franckenstein v' + version_number + ' started')
    screen = MainScreen(None)
    screen.title('Franckenstein')
    screen.lift()
    ani = animation.FuncAnimation(plot_fig, plot_values, interval=plot_refresh_rate)
    serial_thread = threading.Thread(target=update_pairs, args=(1,))
    serial_thread.daemon = True
    serial_thread.start()
    screen.after(status_update_refresh_rate, screen.update_status)
    screen.mainloop()
