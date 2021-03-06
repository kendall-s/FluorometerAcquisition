"""
This PyQt5 GUI app is used to acquire data from a Sens-Tech P25/P30 USB photodetector. In the use case this
application was developed to display and capture data from a detector configured to measure fluorescence for the 
purposes of measuring Ammonium in seawater. 

If needing reference for the serial commands used, search 'Sens Tech P25USB manual', this will contain a good
chunk of information

"""
from PyQt5 import QtCore
from PyQt5.QtWidgets import (QMainWindow, QGridLayout, QWidget, QApplication, QLabel, 
                            QComboBox, QPushButton, QLineEdit, QFrame, QCheckBox, QFileDialog)
from PyQt5.QtCore import QThread, QObject, pyqtSignal
from PyQt5.QtGui import QFont
import pyqtgraph as pg
import sys 
import os
from pyqtgraph import colormap
import serial
import serial.tools.list_ports
import time
import random
import statistics

# Convert the time to a value to send to the detector
PERIOD_CONVERTER = {'100ms': 10, '200ms': 20, '250ms': 25, '500ms': 50, '1000ms': 100}

class MainWindow(QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Init these as NANs
        self.folder_path = None
        self.ser = None
        self.measuring = False
        
        # Lists for the raw data
        self.plot_x = []
        self.plot_y = []

        # These are used for creating the 1 second median smoothed chart
        self.st = None
        self.count_back = 0
        self.smooth_plot_x = []
        self.smooth_plot_y = []

        # Startup functions
        self.init_ui()
        self.init_ports()
    
    def init_ui(self):
        """
        This function contains all of the UI setup, including the initialising of every
        widget and then placing them in the relevant locations of the grid layout
        """
        # Set the app wide font as Segoe UI (the windows 10 system font)
        self.setFont(QFont('Segoe UI'))
        self.setStyleSheet(""" QLabel { font: 14px; } QLineEdit { font: 14px } QComboBox { font: 14px } QPushButton { font: 14px } QCheckBox { font: 14px }""")
        # Create the grid layout and set the gutter spacing to 10px
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        # The following 6 lines are used to set the window size and then place it
        # in the center of the 'active' screen (user could be using a multi monitor setup)
        self.setGeometry(0, 0, 1400, 550)
        qtRectangle = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        qtRectangle.moveCenter(centerPoint)
        self.move(qtRectangle.topLeft())
        
        self.setWindowTitle('Fluorometer Logger')
    

        # Start of the widgets initialisation

        ports_label = QLabel('<b>Select Port:</b>')
        self.ports_combo = QComboBox()

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_port)
        self.connection_status = QLineEdit(" No Connection ")
        self.connection_status.setReadOnly(True)
        self.connection_status.setAlignment(QtCore.Qt.AlignCenter)
        self.connection_status.setStyleSheet("QLineEdit { background: rgb(224, 20, 0); color: rgb(250, 250, 250);}")
        self.connection_status.setFont(QFont('Segoe UI'))

        linesep_1 = QFrame()
        linesep_1.setFrameShape(QFrame.HLine)
        linesep_1.setFrameShadow(QFrame.Sunken)

        files_control_label = QLabel('<b>File Writing</b>')

        file_path_label = QLabel('File Path:')
        self.folder_path_lineedit = QLineEdit()
        self.folder_path_lineedit.setReadOnly(True)

        self.browse_path_button = QPushButton("Browse Path")
        self.browse_path_button.clicked.connect(self.browse_file_folder)

        files_name_label = QLabel('Files will be saved into the selected directory')
        files_name_label.setWordWrap(True)

        linesep_2 = QFrame()
        linesep_2.setFrameShape(QFrame.HLine)
        linesep_2.setFrameShadow(QFrame.Sunken)

        controls_label = QLabel('<b>Fluorometer Controls</b>')

        self.high_voltage_checkbox = QCheckBox("High Voltage On?")

        measure_freq_label = QLabel('Measure Frequency:')
        self.measure_freq_combo = QComboBox()
        self.measure_freq_combo.addItems(['100ms', '200ms', '250ms', '500ms', '1000ms'])    
        self.measure_freq_combo.setEditable(True)
        self.measure_freq_combo.setEditable(False)
        
        self.start_acquire = QPushButton("Acquire Data")
        self.start_acquire.clicked.connect(self.acquire_data)

        self.autoscale_chart = QCheckBox("Auto Track")
        self.autoscale_chart.setToolTip('Track new data along X axis')

        self.signal_value = QLineEdit()
        self.signal_value.setReadOnly(True)
        self.signal_value.setFixedWidth(120)

        pg.setConfigOptions(antialias=True)
        self.graphWidget = pg.PlotWidget()
        self.graphWidget.setLabel('left', 'Raw Count')
        self.graphWidget.setLabel('bottom', 'Time')
        self.graphWidget.showGrid(x=True, y=True)
        self.graphWidget.setBackground('w')
        self.graphWidget.sizePolicy().setHorizontalStretch(3)

        graph_pen = pg.mkPen(color=(10, 10, 180))
        smooth_graph_pen = pg.mkPen(color=(10, 180, 10))
        

        # Add everything to our grid layout
        # Column 1
        grid_layout.addWidget(ports_label, 0, 0, 1, 2)
        grid_layout.addWidget(self.ports_combo, 1, 0, 1, 1)
        grid_layout.addWidget(self.connect_button, 1, 1, 1, 1)
        grid_layout.addWidget(self.connection_status, 2, 0, 1, 2)
        grid_layout.addWidget(linesep_1, 3, 0, 1, 2)

        grid_layout.addWidget(files_control_label, 4, 0, 1, 2)
        grid_layout.addWidget(file_path_label, 5, 0, 1, 1)
        grid_layout.addWidget(self.folder_path_lineedit, 6, 0, 1, 2)
        grid_layout.addWidget(self.browse_path_button, 7, 0, 1, 2)
        grid_layout.addWidget(files_name_label, 8, 0, 1, 2)


        grid_layout.addWidget(linesep_2, 9, 0, 1, 2)
        grid_layout.addWidget(controls_label, 10, 0, 1, 2)
        grid_layout.addWidget(self.high_voltage_checkbox, 11, 0, 1, 2)
        grid_layout.addWidget(measure_freq_label, 12, 0, 1, 1)
        grid_layout.addWidget(self.measure_freq_combo, 12, 1, 1, 1)   

        grid_layout.addWidget(self.start_acquire, 14, 0, 1, 2)    
        
        grid_layout.addWidget(self.autoscale_chart, 16, 0, 1, 1)
        grid_layout.addWidget(self.signal_value, 16, 1, 1, 1)

        # Column 2
        grid_layout.addWidget(self.graphWidget, 0, 2, 18, 12)

        # Set up our pyqtgraph widget with the 2 plottable lines
        self.plotted_data = self.graphWidget.plot(self.plot_x, self.plot_y, pen=graph_pen)
        self.smoothed_plotted_data = self.graphWidget.plot(self.smooth_plot_x, self.smooth_plot_y, pen=smooth_graph_pen)
        
        # Use open Gl for slightly better performance
        self.graphWidget.useOpenGL(True)
        
        # Set the layout of the application window widget to the grid layout which is holding everything
        self.centralWidget().setLayout(grid_layout)



    def init_ports(self):
        """
        Finds all the available com ports on the system, lists them in the combobox
        """
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.ports_combo.addItem(str(port)[:15] + "...")
        
    def toggle_port(self):
        """
        This function is responsible for opening and closing the serial port 
        """
        port = self.ports_combo.currentText().split(" ")[0]
        print(port)

        if self.ser:
            print("Closing port")

            self.ser.close()
            self.ser = None

            self.connect_button.setText("Connect")
            self.connection_status.setText("No Connection")
            self.connection_status.setStyleSheet("QLineEdit { background: rgb(224, 20, 0); color: rgb(250, 250, 250);}")
        
        else:
            print("Opening port")
            #self.ser = 1
            try:
                self.ser = serial.Serial(timeout=1, baudrate=9600, stopbits=1, parity=serial.PARITY_NONE)
                self.ser.port = port
                self.ser.open()

                self.connect_button.setText("Disconnect")
                self.connection_status.setText("CONNECTED")
                self.connection_status.setStyleSheet("QLineEdit { background: rgb(15, 200, 53); color: rgb(250, 250, 250);}")
            except Exception:
                print(Exception)    

    def browse_file_folder(self):
        """
        Allows the user to navigate to a folder so the file can be saved
        """
        folder_path = QFileDialog.getExistingDirectory(self, 'Select Folder')

        if os.path.exists(folder_path):
            self.folder_path = folder_path
            self.folder_path_lineedit.setText(folder_path)

    def acquire_data(self):
        """
        The majority of this function is just getting the input values and then checking if 
        the app is ready to capture data from the fluorometer. It then sets up the new thread
        with the DataAcquirer object and primes it for data capture.
        """
        # Get all of the required values from the fields
        folder_path = self.folder_path_lineedit.text()
        current_period = self.measure_freq_combo.currentText()
        converted_period = PERIOD_CONVERTER[current_period]
        high_voltage = self.high_voltage_checkbox.isChecked()

        if not self.measuring:
            if self.ser:
                if len(folder_path) > 0:
                    self.start_acquire.setText("Stop Acquire")
                    self.ser.flushOutput()

                    #Turn on high voltage if ticked
                    if high_voltage:
                        self.ser.write(b"D\r")
                        print(self.ser.read(2))
                    
                    #Set the gating period
                    ascii_period = chr(converted_period)
                    writable_string = f"P{ascii_period}\r".encode('utf-8')
                    #self.ser.write(b"P\r")
                    self.ser.write(writable_string)
                    print(self.ser.read(2))
                    print(self.ser.inWaiting())
                    
                    # Initiate the data acquisition object and start the loop
                    self.measuring = True
                    self.thread = QThread()
                    self.data_thread = DataAcquirer(self.ser, folder_path)
                    self.data_thread.moveToThread(self.thread)
                    self.thread.started.connect(self.data_thread.data_acquire_loop)
                    self.data_thread.finished.connect(self.thread.quit)
                    self.data_thread.new_data.connect(self.update_chart)

                    # Disable all of the buttons so that I don't have to add checking to their functions
                    self.connect_button.setEnabled(False)
                    self.browse_path_button.setEnabled(False)
                    self.high_voltage_checkbox.setEnabled(False)
                    self.measure_freq_combo.setEnabled(False)

                    self.thread.start()
                else:
                    print('Please browse to a folder first')
            else:
                print('There is not a current serial connection!')
        else:
            # This will stop the data acquisition loop
            self.measuring = False
            self.data_thread.measuring = False
            
            # Renable everything when acquisition has stopped
            self.connect_button.setEnabled(True)
            self.browse_path_button.setEnabled(True)
            self.high_voltage_checkbox.setEnabled(True)
            self.measure_freq_combo.setEnabled(True)
            
            self.start_acquire.setText("Start Acquire")

    def update_chart(self, new_data):
        """
        Class method that will add the newly collected data to the plot,
        this will also create a median smoothed dataset every 1 second and add it to the chart
        """
        # Once we have a lot of data in the lists, start removing points so that the 
        # app stays performant
        if len(self.plot_x) == 20000:
            self.plot_x.pop(0)
            self.plot_y.pop(0)

        # Add the latest raw data to the raw plot lists
        self.plot_x.append(new_data[1])
        self.plot_y.append(new_data[0])

        # st is start time, this is used to create a median smoothed chart
        if not self.st:
            self.st = new_data[1]

        # Set the current time to the latest data time point
        ct = new_data[1]

        # ct is current time, the value 1 represents 1 second. If 1 second has passed
        # then create a median of the past second worth of data and pass it to the smooth lists
        if (ct - self.st) > 1:
            
            # Pull subset from the raw data with count back var, calc median
            subset = self.plot_y[-self.count_back:]
            median = statistics.median(subset)

            # I am making this median value slightly smaller than the raw data so that is 
            # is offset from the raw data line - improving ledgibility on the chart
            median = median * 0.99
            
            # Add the median smoothed data
            self.smooth_plot_x.append(ct)
            self.smooth_plot_y.append(median)

            # Update the chart with the new data
            self.smoothed_plotted_data.setData(self.smooth_plot_x, self.smooth_plot_y)

            # Reset the start time and the count back index
            self.count_back = 0
            self.st = None
        else:
            # count_back is used to get the index of the raw data
            self.count_back = self.count_back + 1
        
        # Update the raw chart and display the latest signal value
        self.plotted_data.setData(self.plot_x, self.plot_y)
        self.signal_value.setText(f'Signal: {new_data[0]}')

        if self.autoscale_chart.isChecked():
            # This will pan the chart along when there is enough data to do so
            if len(self.plot_x) > 3000:
                self.graphWidget.setXRange(self.plot_x[-3000], self.plot_x[-1])


class DataAcquirer(QObject):
    """
    The DataAcquirer class is created and used in a separate thread to capture data continually 
    from the serial device, it uses the PyQt signals and slots to communicate data back to the main UI thread
    """
    new_data = pyqtSignal(list)
    finished = pyqtSignal()
    
    def __init__(self, serial_object, folder_path):
        super().__init__()
        self.measuring = True
        self.serial_object = serial_object
        self.folder_path = folder_path

        self.file_path = folder_path + f"/FluoroAcq_{time.time()}.csv"
        self.raw_data = []
        self.raw_time_data = []
        
    def data_acquire_loop(self):
        """ This is the main data acquisition loop - this will run while the class variable measuring is True"""
        self.serial_object.write(b"C\r")
        clear = self.serial_object.inWaiting()
        read = self.serial_object.read(size=4)
        #clear = self.ser.inWaiting()
        while self.measuring:
            f = open(self.file_path, "a")
            print('Data acquire')
                        
            string_sent = self.serial_object.read(size=4)
            #print(string_sent)
            number = self.parse_byte_string(string_sent)

            # If there is a decimal value from the payload (sometimes receive nothing)
            if len(number) > 0:
                
                # Chop off the very last number - it doesn't seem relevant
                number = float(str(number)[1:7])
                print(number)

                time_now = time.time()
                # Append into the holder variables
                self.raw_data.append(number)
                self.raw_time_data.append(time_now)
                results = [number, time_now]
                self.new_data.emit(results)
                # Write to the save file 
                f.write(f'{number}, {time_now}\n')

        f.close()
        self.finished.emit()

    def parse_byte_string(self, byte_string):
        """
        This looks a little bit like some sort of black magic - I'm sorry - but it 
        is essentially just cleaning up the 4 byte payload and converting it to a decimal
        value. It is this way because there is leading zeros and the trailing length changes 
        """
        number = ''
        for i, bit in enumerate(byte_string):
            if i == 2:
                if len(str(bit)) == 2:
                    bit = '0' + str(bit)
            if i == 3:
                if len(str(bit)) == 2:
                    bit = str(bit) + '0'
                if len(str(bit)) == 1:
                    bit = str(bit) + '00'
            number = number + str(bit)
        return number

def main():
    app = QApplication(sys.argv)
    main = MainWindow()
    main.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()