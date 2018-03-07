import pywinusb.hid as hid
from time import sleep
from threading import Thread
import wx
import sys
vendor_id = 0x05f3
product_id = 0x00ff
gui_closed = False

class dialog(wx.Frame):

    def __init__(self, parent, title):
        super(dialog, self).__init__(parent, title=title, size=(390, 475),
                                     style=wx.SYSTEM_MENU | wx.CAPTION | wx.CLOSE_BOX)

        self.InitUI()
        self.Centre()
        self.Show()


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


        panel.SetSizer(virtBox)

    def onExit(self, event):
        global gui_closed
        gui_closed = True
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

    print("\nRaw data: {0}".format(data[1]),"GUI Closed:", gui_closed)

    if data[1] == FT_ALL:
        print("ALL Depressed")
        return FT_ALL
    else:
        if data[1] == FT_LR_ID:
            print("Left + Right Depressed")
            return FT_LR_ID
        else:
            if data[1] == FT_RMID_ID:
                print("Right + Middle Depressed")
                return FT_RMID_ID
            else:
                if data[1] == FT_RIGHT_ID:
                    print("Right Depressed")
                    return  FT_RIGHT_ID
                else:
                    if data[1] == FT_LMID_ID:
                        print("Left + Middle Depressed")
                        return FT_LMID_ID
                    else:
                        if data[1] == FT_MID_ID:
                            print("Middle Depressed")
                            return FT_MID_ID
                        else:
                            if data[1] == FT_LEFT_ID:
                                print("Left Depressed")
                                return FT_LEFT_ID
                            else:
                                print("None Depressed")
                                return FT_NONE_ID


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

def startUI():
    app = wx.App()
    dialog(None, title="USB Foot Pedal Playback Program")
    if gui_closed == True:
        app.ExitMainLoop()
    app.MainLoop()

if __name__ == "__main__":
    usb_thread = Thread(target=usb_pedal)
    gui_thread = Thread(target=startUI)
    #gui_thread.start()
    usb_thread.start()
    startUI()

