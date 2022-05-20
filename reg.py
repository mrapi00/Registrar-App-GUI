#!/usr/bin/env python

#-----------------------------------------------------------------------
# reg.py
#-----------------------------------------------------------------------

import argparse
from sys import argv, exit
from socket import socket
from queue import Queue, Empty
from threading import Thread
from PyQt5.QtWidgets import QApplication, QMainWindow, QFrame
from PyQt5.QtWidgets import QGridLayout, QDesktopWidget
from PyQt5.QtWidgets import QLineEdit, QLabel, QListWidget
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QFont
#-----------------------------------------------------------------------
# Command line
parser = argparse.ArgumentParser(description='Client for the registrar'
+ ' application', allow_abbrev=False)
parser.add_argument('host', help='the host on which the server is ' +
'running',)
parser.add_argument('port', help='the port at which the server is ' +
'listening' , type =int)
args = parser.parse_args()
#----------------------------------------------------------------------
# GLOBALS
SYS_ERROR = 'A server error occurred. Please contact the system '
SYS_ERROR += 'administrator.'
# ---------------------------------------------------------------------
# create all labels needed for the GUI
def all_labels() :
     # Label widgets
    label_dept = QLabel('Dept: ')
    label_dept.setAlignment(Qt.AlignRight)
    label_num = QLabel('Number: ')
    label_num.setAlignment(Qt.AlignRight)
    label_area = QLabel('Area: ')
    label_area.setAlignment(Qt.AlignRight)
    label_title= QLabel('Title: ')
    label_title.setAlignment(Qt.AlignRight)
    return [label_dept, label_num, label_area, label_title]

# create all line edits needed for the GUI
def all_line_edits() :
    # Line edit widgets
    line_edit_dept = QLineEdit('')
    line_edit_num = QLineEdit('')
    line_edit_area = QLineEdit('')
    line_edit_title = QLineEdit('')
    return [line_edit_dept, line_edit_num, line_edit_area,
     line_edit_title]

# create top frame (line-edits and labels)
# needed for the GUI
def top_frame(labels, line_edits) :
    layout = QGridLayout()

    # add labels and lineedits
    layout.addWidget(labels[0], 0, 0)
    layout.addWidget(line_edits[0], 0, 1)
    layout.addWidget(labels[1], 1, 0)
    layout.addWidget(line_edits[1], 1, 1)
    layout.addWidget(labels[2], 2, 0)
    layout.addWidget(line_edits[2], 2, 1)
    layout.addWidget(labels[3], 3, 0)
    layout.addWidget(line_edits[3], 3, 1)

    topframe = QFrame()
    topframe.setLayout(layout)
    return topframe

# creates the bottom half frame, namely the list widget
def bottom_list_frame(listwidget):
    layout = QGridLayout()
    layout.setSpacing(0)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(listwidget)
    list_frame = QFrame()
    list_frame.setLayout(layout)
    return list_frame

# returns a central frame that combines top and bottom
def create_combined_frame(top_frame, bottom_frame):
    layout = QGridLayout()
    layout.setSpacing(0)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(top_frame, 0, 0)
    layout.addWidget(bottom_frame, 1, 0)
    central_frame = QFrame()
    central_frame.setLayout(layout)
    return central_frame

#----------------------------------------------------------------------
class RegThread (Thread):

    def __init__(self, host, port, dept, num, area, title, queue):
        Thread.__init__(self)
        self._host = host
        self._port = port
        self._dept = dept
        self._num = num
        self._area = area
        self._title = title
        self._queue = queue
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        try:
            with socket() as sock:
                sock.connect((args.host, args.port))
                print("Sent command: get_overviews")
                out_flo = sock.makefile(mode='w', encoding='utf-8')
                out_flo.write('submit\n')

                out_flo.write(self._dept + '\n')
                out_flo.write(self._num + '\n')
                out_flo.write(self._area + '\n')
                out_flo.write(self._title + '\n')
                out_flo.flush()

                # read in resulting classes from server (based on query)
                in_flo = sock.makefile(mode = 'r', encoding='utf-8')
                ind = 0
                entries = []
                for line in in_flo :
                    entries.insert(ind, line)
                    ind += 1
                if not self._should_stop:
                    self._queue.put((True, entries))
        except Exception as ex:
            if not self._should_stop:
                self._queue.put((False, ex))

#-----------------------------------------------------------------------
def poll_queue_helper(queue, listwidget, window):

    while True:
        try:
            item = queue.get(block=False)
        except Empty:
            break
        listwidget.clear()
        successful, data = item
        if successful:
            entries = data
            ind = 0
            for entry in entries:
                if entry.strip() == 'System Error' :
                    QMessageBox.information(window, 'Error',
                    SYS_ERROR)
                    return
                listwidget.insertItem(ind, entry.replace('\n', ''))
                ind += 1
            listwidget.setCurrentRow(0)
        else:
            err = data
            QMessageBox.information(window, 'Error',
            str(err))

#-----------------------------------------------------------------------

def main() :
    app = QApplication(argv)

    # obtain labels
    labels = all_labels()

    # decompose lineedits from list
    line_edits = all_line_edits()
    line_edit_dept = line_edits[0]
    line_edit_num = line_edits[1]
    line_edit_area = line_edits[2]
    line_edit_title = line_edits[3]

    # create list widget
    listwidget = QListWidget()
    listwidget.setFont(QFont('Courier', 10))

    # set up frames and merge
    topframe = top_frame(labels, line_edits)
    bottom_listframe = bottom_list_frame(listwidget)
    central_frame = create_combined_frame(topframe, bottom_listframe)

    # set up window
    window = QMainWindow()
    window.setWindowTitle('Princeton University Class Search')
    window.setCentralWidget(central_frame)
    screen_size = QDesktopWidget().screenGeometry()
    window.resize(screen_size.width() // 2, screen_size.height() // 2)

    # Create a queue and a timer that polls it.
    queue = Queue()
    def poll_queue():
        poll_queue_helper(queue, listwidget, window)
    timer = QTimer()
    timer.timeout.connect(poll_queue)
    timer.setInterval(100) # milliseconds
    timer.start()

    # Handle signals.

    reg_thread = None

    # trigger a query when user submits
    def submit_slot() :
        nonlocal reg_thread
        # extract dept, num, area and title and write it out
        dept = line_edit_dept.text()
        num = line_edit_num.text()
        area = line_edit_area.text()
        title = line_edit_title.text()
        if reg_thread is not None:
            reg_thread.stop()
        reg_thread = RegThread(args.host, args.port, dept, num, area, 
        title, queue)
        reg_thread.start()

    # retreve class details
    def item_activate_slot() :
        try :
            with socket() as sock:
                sock.connect((args.host, args.port))
                print("Sent command: get_detail")
                line = listwidget.currentItem().text().split(' ')
                if line[0] == '':
                    classid = line[1]
                else :
                    classid = line[0]
                out_flo = sock.makefile(mode='w', encoding='utf-8')
                out_flo.write('details\n')
                out_flo.write(classid + '\n')
                out_flo.flush()

                details_message = ''
                in_flo = sock.makefile(mode = 'r', encoding='utf-8')
                read_status = in_flo.readline().strip()
                # print(read_status)
                # checks for database error
                if read_status == 'System Error' or read_status == '':
                    QMessageBox.information(window, 'Error',
                    SYS_ERROR)
                    return

                # for non-existing classid error handling
                # from client side
                if read_status == 'NO CLASSID' :
                    details_message += "Error: ClassID " + classid
                    details_message += " does not exist"
                    QMessageBox.information(window, 'Error',
                    details_message.strip())
                    return
                
                for line in in_flo :
                    details_message += line
                QMessageBox.information(window, 'Class Details',
                details_message.strip())
        except Exception as ex:
            QMessageBox.information(window, 'Error', str(ex))

    # run an initial automatic query of all classes on startup only
    startup = True
    if startup :
        submit_slot()
        startup = False
    
    # triggers query search
    listwidget.itemActivated.connect(item_activate_slot)

    # allow "Enter" key to submit too
    line_edit_dept.textChanged.connect(submit_slot)
    line_edit_area.textChanged.connect(submit_slot)
    line_edit_num.textChanged.connect(submit_slot)
    line_edit_title.textChanged.connect(submit_slot)

    window.show()
    exit(app.exec_())

if __name__ == '__main__':
    main()
    