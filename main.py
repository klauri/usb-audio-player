import pywinusb.hid as hid
from time import sleep
from threading import Thread, Event
import wx
import pyaudio
import wave

vendor_id = 0x05f3
product_id = 0x00ff
gui_closed = Event()
playback_control = Event()
file_path = None
audio_thread = None
screen_size = (1200, 900)

class Dialog(wx.Frame):

    def __init__(self, parent, title):
        super(Dialog, self).__init__(parent, title=title, size=screen_size,
                                     style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX)

        self.InitUI()
        self.Centre()
        self.Show()

        self.Bind(wx.EVT_CLOSE, self.onExit)


    def InitUI(self):

        #icon = wx.IconLocation(
        #    os.path.join(
        #        os.getcwd(),
        #        "assets",
        #        'icon.ico'),
        #    0)

        #self.SetIcon(wx.Icon(icon))

        menuBar = wx.MenuBar()
        fileMenu = wx.Menu()
        helpMenu = wx.Menu()

        menuBar.Append(fileMenu, '&File')
        exitMenuItem = fileMenu.Append(wx.NewId(), "E&xit", "Exit the application.")
        menuBar.Append(helpMenu, "&Help")
        aboutMenuItem = helpMenu.Append(wx.NewId(), "&About", "About this program")
        helpMenuItem = helpMenu.Append(wx.NewId(), "How &To", "Get Help using this program.")

        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.onExit, exitMenuItem)
        #self.Bind(wx.EVT_MENU, self.onHelp, helpMenuItem)

        panel = wx.Panel(self)
        virtBox = wx.BoxSizer(wx.VERTICAL)
        
        # Button to pick file(s)
        pickFileButton = wx.Button(panel, label="Pick audio file")
        virtBox.Add(pickFileButton, 0, wx.ALL | wx.CENTER, 5)
        pickFileButton.Bind(wx.EVT_BUTTON, self.onPickFile)

        self.filelabel = wx.StaticText(panel, label="No file selected")
        virtBox.Add(self.filelabel, 0, wx.ALL | wx.CENTER, 5)

        panel.SetSizer(virtBox)

    def onPickFile(self, event):

        with wx.FileDialog(self, "Open WAV,MP3 file", wildcard="WAV,MP3 files (*.wav;*.mp3;*.mp4)|*.wav;*.mp3;*mp4", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return     # the user changed their mind

            # Proceed loading the file chosen by the user
            global file_path
            file_path = fileDialog.GetPath()
            self.filelabel.SetLabel(f"Selected: {file_path}")

    def onExit(self, event):
        gui_closed.set()
        playback_control.clear()
        self.Close()

def usb_handler(data):

    FT_NONE_ID = 0
    FT_LEFT_ID = 1
    FT_MID_ID  = 2
    FT_RIGHT_ID= 4
    FT_LMID_ID = FT_LEFT_ID + FT_MID_ID
    FT_RMID_ID = FT_RIGHT_ID + FT_MID_ID
    FT_LR_ID = FT_LEFT_ID + FT_RIGHT_ID
    FT_ALL = FT_LEFT_ID + FT_RIGHT_ID + FT_MID_ID

    button_map = {
        FT_ALL: "ALL Depressed",
        FT_LR_ID: "Left + Right Depressed",
        FT_RMID_ID: "Right + Middle Depressed",
        FT_RIGHT_ID: "Right Depressed",
        FT_LMID_ID: "Left + Middle Depressed",
        FT_MID_ID: "Middle Depressed",
        FT_LEFT_ID: "Left Depressed",
        FT_NONE_ID: "None Depressed"
    }

    button_status = button_map.get(data[1], "Unknown State")
    print("\nRaw data: {0}, GUI Closed: {1}, Status: {2}".format(data[1], gui_closed.is_set(), button_status))


    # Depending on Button pressed, control playback
    if data[1] == FT_MID_ID:
        if playback_control.is_set():
            playback_control.clear()
        else:
            playback_control.set()
            start_audio_thread()
    
    elif data[1] == FT_RIGHT_ID:
        fast_forward()
    
    elif data[1] == FT_LEFT_ID:
        rewind()

    return data[1]

def fast_forward():
    global audio_position
    audio_position += 5 * 1024 # Skip 5 chunks ahead

def rewind():
    global audio_position
    audio_position -= 5 * 1024 # Go back 5 chunks
    if audio_position < 0:
        audio_position = 0
    

def usb_pedal():
    devices = hid.HidDeviceFilter(vendor_id=vendor_id, product_id=product_id).get_devices()
    if devices:
        device = devices[0]
        print("Found Device", device)

        device.open()
        device.set_raw_data_handler(usb_handler)
        while device.is_plugged():
            # just keep the device opened to receive events
            if gui_closed == True:
                break
            sleep(0.5)
        device.close()

def play_audio():
    if file_path is None:
        print("No file selected.")
        return

    global audio_position
    audio_position = 0

    with wave.open(file_path, 'rb') as wf:
        p = pyaudio.PyAudio()
        stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True)
        data = wf.readframes(1024)
        while not gui_closed.is_set() and data != b'':
            if playback_control.is_set():
                wf.setpos(audio_position)
                data = wf.readframes(1024)
                audio_position += 1024
                stream.write(data)
            else:
                if gui_closed.is_set():
                    break
                sleep(0.1) # Pause Playback
        
        stream.stop_stream()
        stream.close()
        p.terminate()

def start_audio_thread():
    global audio_thread
    if audio_thread is None or not audio_thread.is_alive():
        audio_thread = Thread(target=play_audio)
        audio_thread.start()

def startUI():
    app = wx.App()
    Dialog(None, title="USB Foot Pedal Playback Program")
    app.MainLoop()

if __name__ == "__main__":
    usb_thread = Thread(target=usb_pedal)
    usb_thread.start()
    startUI()
    usb_thread.join()
    if audio_thread is not None:
        audio_thread.join()

