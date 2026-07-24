import sys
import os

sys.frozen = True
sys._MEIPASS = os.path.abspath('.')
sys.executable = os.path.abspath('fake.exe')

import gui_app
app = gui_app.YoutubeDownloaderApp()

# Patch _on_updater_finished to close app after running
original_on_finished = app._on_updater_finished
def new_on_finished():
    original_on_finished()
    app.after(500, app.destroy)

app._on_updater_finished = new_on_finished

app.mainloop()
