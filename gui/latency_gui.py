#
# usage: pipe comma seperated values into this program:
# current iteration, max iterations, last time (in ms)
#

import sys
import time
from PyQt4.QtCore import *
from PyQt4.QtGui import *

#app
application = QApplication(sys.argv)
window = QWidget()
layout = QVBoxLayout()
timer = QTimer()

#widgets
progressbar = QProgressBar()
label_iteration = QLabel()
label_time = QLabel()

def initLabels():
    label_iteration.setFont(QFont("SansSerif", 64))
    label_iteration.setAlignment(Qt.AlignRight)

    label_time.setFont(QFont("SansSerif", 128))
    label_time.setAlignment(Qt.AlignRight)

    progressbar.setTextVisible(False)

    layout.addWidget(progressbar)
    layout.addWidget(label_iteration)
    layout.addWidget(label_time)

def showWindow():
    window.setWindowTitle("LagBox")
    window.setLayout(layout)
    window.showMaximized()
    
def updateLabels(iteration, max_iterations, time):
    pval = (float(iteration) / float(max_iterations)) * 100.0
    progressbar.setValue(pval)
    label_iteration.setText(str(iteration) + "/" + str(max_iterations))
    label_time.setText(str(time).rstrip() + "ms")

def getValues():
    try:
        line = sys.stdin.readline()
        print line
        if not line:
            return
    except:
        return
    iteration, max_iterations, time = line.split(",")
    updateLabels(iteration, max_iterations, time)


initLabels()

#updateLabels(0, 100, 0)

timer.timeout.connect(getValues)
timer.start(200)

showWindow()

sys.exit(application.exec_())
