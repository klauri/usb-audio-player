import pywinusb.hid as hid
from time import sleep
from threading import Thread, Event
import wx
import wx.media
import pyaudio
import wave

vendor_id = 0x05f3
product_id = 0x00ff
gui_closed = Event()
playback_control = Event()
file_path = None
audio_thread = None
total_frames = 0
screen_size = (1000, 700)

# Constants for button IDs
FT_ALL_ID = 0xFFFF
FT_MID_ID = 1 << 2
FT_LEFT_ID = 1 << 0
FT_RIGHT_ID = 1 << 1
FT_NONE_ID = 0
FT_LR_ID = FT_LEFT_ID | FT_RIGHT_ID
FT_RMID_ID = FT_RIGHT_ID | FT_MID_ID
FT_LMID_ID = FT_LEFT_ID | FT_MID_ID

class Frame(wx.Frame):

    def __init__(self, parent, title):
        super(Frame, self).__init__(parent, title=title, size=screen_size,
                                     style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX)
        self.is_playing = False
        # Initialize UI
        self.InitUI()

        self.Centre()
        self.Show()
        
        # Bind the close event to onExit
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

        usb_thread = UsbHandler(self)
        usb_thread.start()

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

        self.media = wx.media.MediaCtrl(panel, style=wx.NO_BORDER)

        self.play_pause_button = wx.Button(panel, label="Play/Pause")
        self.play_pause_button.Bind(wx.EVT_BUTTON, self.OnPlayPause)

        # Layout the controls on the frame
        virtBox.Add(self.media, 0, wx.ALL | wx.CENTER, 5)
        virtBox.Add(self.play_pause_button, 0, wx.ALL, wx.CENTER, 5)

        # Scrubber for audio position
        self.scrubber = LabeledSlider(panel, value=0, minValue=0, maxValue=100, size=(350,-1), style=wx.SL_HORIZONTAL)
        
        # Add min label, slider, and max label to sizer
        scrubber_sizer = wx.BoxSizer(wx.HORIZONTAL)
        scrubber_sizer.Add(self.scrubber.min_label, 0, wx.ALIGN_CENTER_VERTICAL)
        scrubber_sizer.Add(self.scrubber, 1, wx.EXPAND | wx.ALL, 5)
        scrubber_sizer.Add(self.scrubber.max_label, 0, wx.ALIGN_CENTER_VERTICAL)

        virtBox.Add(scrubber_sizer, 0, wx.ALL | wx.CENTER, 5)

        self.scrubber.Bind(wx.EVT_SLIDER, self.onScrub)

        panel.SetSizer(virtBox)

    def onPickFile(self, event):

        with wx.FileDialog(self, "Open WAV,MP3 file", wildcard="WAV,MP3 files (*.wav;*.mp3;*.mp4)|*.wav;*.mp3;*mp4", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return     # the user changed their mind

            # Proceed loading the file chosen by the user
            global file_path, total_frames, audio_position, wf
            file_path = fileDialog.GetPath()
            self.media.Load(fileName=file_path)
            self.filelabel.SetLabel(f"Selected: {file_path}")

            # Get total frames
            with wave.open(file_path, 'rb') as wf:
                total_frames = wf.getnframes()
                sample_rate = wf.getframerate()

            # Reset the scrubber
            audio_position = 0
            self.scrubber.SetValue(0)
            self.scrubber.SetMax(total_frames) #frames_to_timestamp(total_frames, wf.getframerate()))

            # Set the max value label
            total_timestamp = frames_to_timestamp(total_frames, sample_rate)
            self.scrubber.SetTickFreq(total_frames // 10)
            self.scrubber.SetLineSize(1024)
            self.scrubber.SetMinLabel('00:00')
            self.scrubber.SetMaxLabel(f'{total_timestamp}')

    def onScrub(self, event):
        global audio_position
        audio_position = self.scrubber.GetValue()

        update_scrubber_and_timestamp()

        if wf is not None:
            wf.setpos(audio_position)
        print(f'Scrubbed to frame {audio_position}')

    def OnPlayPause(self, event):
        if not file_path:
            wx.MessageBox("Please select a file first")
            return

        if not self.is_playing:
            self.media.Play()
            self.play_pause_button.SetLabel("Pause")
            self.is_playing = True
        else:
            self.media.Pause()
            self.play_pause_button.SetLabel("Play")
            self.is_playing = False

    def onExit(self, event):
        gui_closed.set()
        playback_control.clear()
        self.Close()

class LabeledSlider(wx.Slider):
    def __init__(self, parent, *args, **kwargs):
        super(LabeledSlider, self).__init__(parent, *args, **kwargs)
        self.min_label = wx.StaticText(parent, label="00:00")
        self.max_label = wx.StaticText(parent, label="00:00")

    def SetMinLabel(self, label):
        self.min_label.SetLabel(label)

    def SetMaxLabel(self, label):
        self.max_label.SetLabel(label)

class UsbHandler(Thread):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.devices = None
        self.gui_closed = Event()
        self.p = None
        self.stream = None
        self.audio_data = bytearray(1024) # Buffer for audio data

    def run(self):
        self.usb_pedal()

    def usb_handler(self, data):
        if data:
            self.audio_data.extend(data)
        # Depending on Button pressed, control playback
        if data[1] == FT_MID_ID:
            if playback_control.is_set():
                playback_control.clear()
            else:
                playback_control.set()
                start_audio_thread()
    
        elif data[1] == FT_RIGHT_ID:
            pass

        elif data[1] == FT_LEFT_ID:
            pass

        return data[1]

    def play_audio(self):
        play_audio()

    def fake(self):
        chunk = 1024
        format = pyaudio.paFloat32
        channels = 2
        rate = 44100
        
        self.p = pyaudio.PyAudio()

        self.stream = self.p.open(
            format=format,
            channels=channels,
            rate=rate,
            output=True
        )

        while not self.gui_closed.is_set():
            if len(self.audio_data) >= chunk:
                audio_frame = self.audio_data[:chunk]
                del self.audio_data[:chunk]
                self.stream.write(audio_frame)

    def usb_pedal(self):
        self.devices = hid.HidDeviceFilter(vendor_id=vendor_id, product_id=product_id).get_devices()
        if not self.devices:
            print('No USB devices found')
            return

        device = self.devices[0]
        print("Found Device", device)

        device.open()
        device.set_raw_data_handler(self.usb_handler)
        
        audio_thread = Thread(target=self.play_audio)
        audio_thread.start()

        while device.is_plugged():
            # just keep the device opened to receive events
            if gui_closed == True:
                break
            sleep(0.1)
        device.close()
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()

    def stop(self):
        self.gui_closed.is_set()

def frames_to_timestamp(frame_count, sample_rate):
    total_seconds = frame_count // sample_rate
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f'{minutes:02}:{seconds:02}'

def play_audio():
    if file_path is None:
        print("No file selected.")
        return

    global audio_position, wf
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
                if data == b'':
                    break
                stream.write(data)
                audio_position += 1024
                update_scrubber_and_timestamp()
            else:
                if gui_closed.is_set():
                    break
                sleep(0.1) # Pause Playback
        
        stream.stop_stream()
        stream.close()
        p.terminate()

def update_scrubber_and_timestamp():
    global audio_position, wf

    #  Convert current and total frame position to timestamp
    current_timestamp = frames_to_timestamp(audio_position, wf.getframerate())
    total_timestamp = frames_to_timestamp(total_frames, wf.getframerate())

    # Update scrubber tooltip and label
    wx.CallAfter(wx.GetApp().GetTopWindow().scrubber.SetToolTip, f'{current_timestamp} / {total_timestamp}')
    wx.CallAfter(wx.GetApp().GetTopWindow().scrubber.SetMinLabel, f'{current_timestamp}')

class AudioPlayerThread(Thread):
    def __init__(self, media, file_path) -> None:
        super().__init__()
        self.media = media
        self.file_path = file_path
        self.is_paused = False
        self.event = Event()

    def run(self):
        self.media.Load(self.file_path)
        while not self.event.is_set():
            if not self.is_paused:
                self.media.Play()
                wx.Yield()
            else:
                self.media.Pause()
                self.event.wait()

    def pause(self):
        self.is_paused = True
        self.media.Pause()

    def resume(self):
        self.is_paused = False
        self.media.Play()

    def stop(self):
        self.event.set()
        self.media.Stop()
        

def start_audio_thread():
    global audio_thread
    if audio_thread is None or not audio_thread.is_alive():
        audio_thread = Thread(target=play_audio)
        audio_thread.start()

def startUI():
    app = wx.App()
    Frame(None, title="USB Foot Pedal Playback Program")
    app.MainLoop()

if __name__ == "__main__":
    startUI()
    if audio_thread is not None:
        audio_thread.join()

