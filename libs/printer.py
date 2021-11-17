# -*- coding: utf-8 -*-
from brotherprint import *
import usb.core
import usb.util


class USBPrinter(object):
    """ Define USB printer """

    def __init__(self, idVendor, idProduct, interface=0, in_ep=0x82, out_ep=0x01):
        """
        @param idVendor  : Vendor ID
        @param idProduct : Product ID
        @param interface : USB device interface
        @param in_ep     : Input end point
        @param out_ep    : Output end point
        """
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.interface = interface
        self.in_ep = in_ep
        self.out_ep = out_ep
        self.open()

    def open(self):
        """ Search device on USB tree and set is as escpos device """
        self.device = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if self.device is None:
            print
            "Cable isn't plugged in"
            return
        check_driver = True
        try:
            check_driver = self.device.is_kernel_driver_active(self.interface)
        except NotImplementedError:
            pass
        if check_driver is None or check_driver:
            try:
                self.device.detach_kernel_driver(self.interface)
                self.device.set_configuration()
            except usb.core.USBError as e:
                if check_driver is not None:
                    print
                    "Could not detatch kernel driver: %s" % str(e)
        cfg = self.device.get_active_configuration()
        intf = cfg[(0, 0)]
        self.out_ep = usb.util.find_descriptor(
            intf,
            custom_match=(
                lambda e: \
                    usb.util.endpoint_direction(e.bEndpointAddress) == \
                    usb.util.ENDPOINT_OUT)
        )
        self.in_ep = usb.util.find_descriptor(
            intf,
            custom_match=(
                lambda e: \
                    usb.util.endpoint_direction(e.bEndpointAddress) == \
                    usb.util.ENDPOINT_IN)
        )
        if self.out_ep is None:
            print
            "no  out end point"
        if self.in_ep is None:
            print
            "no in end point"
        self.printer = BrotherPrint(
            self.device, self.out_ep, 'usb')

    def close(self):
        i = 0
        while True:
            try:
                if not self.device.is_kernel_driver_active(self.interface):
                    usb.util.release_interface(self.device, self.interface)
                    self.device.attach_kernel_driver(self.interface)
                    usb.util.dispose_resources(self.device)
                else:
                    self.device = None
                    self.printer = None
                    return True
            except usb.core.USBError as e:
                i += 1
                if i > 10:
                    return False

    def __extract_status(self):
        maxiterate = 0
        rep = None
        while rep == None:
            maxiterate += 1
            if maxiterate > 10000:
                raise NoStatusError()
            r = self.device.read(self.in_ep, 20, self.interface).tolist()
            while len(r):
                rep = r.pop()
        return rep

    def get_printer_status(self):
        status = {
            'printer': {},
            'offline': {},
            'error': {},
            'paper': {},
        }

        self.device.write(self.out_ep, DLE_EOT_PRINTER, self.interface)
        printer = self.__extract_status()
        self.device.write(self.out_ep, DLE_EOT_OFFLINE, self.interface)
        offline = self.__extract_status()
        self.device.write(self.out_ep, DLE_EOT_ERROR, self.interface)
        error = self.__extract_status()
        self.device.write(self.out_ep, DLE_EOT_PAPER, self.interface)
        paper = self.__extract_status()

        status['printer']['status_code'] = printer
        status['printer']['status_error'] = not ((printer & 147) == 18)
        status['printer']['online'] = not bool(printer & 8)
        status['printer']['recovery'] = bool(printer & 32)
        status['printer']['paper_feed_on'] = bool(printer & 64)
        status['printer']['drawer_pin_high'] = bool(printer & 4)
        status['offline']['status_code'] = offline
        status['offline']['status_error'] = not ((offline & 147) == 18)
        status['offline']['cover_open'] = bool(offline & 4)
        status['offline']['paper_feed_on'] = bool(offline & 8)
        status['offline']['paper'] = not bool(offline & 32)
        status['offline']['error'] = bool(offline & 64)
        status['error']['status_code'] = error
        status['error']['status_error'] = not ((error & 147) == 18)
        status['error']['recoverable'] = bool(error & 4)
        status['error']['autocutter'] = bool(error & 8)
        status['error']['unrecoverable'] = bool(error & 32)
        status['error']['auto_recoverable'] = not bool(error & 64)
        status['paper']['status_code'] = paper
        status['paper']['status_error'] = not ((paper & 147) == 18)
        status['paper']['near_end'] = bool(paper & 12)
        status['paper']['present'] = not bool(paper & 96)

        return status

    def __del__(self):
        """ Release USB interface """
        if self.device:
            self.close()
        self.device = None


class NetworkPrinter(object):
    """ Define Network printer """

    def __init__(self, host, port=9100):
        """
        @param host : Printer's hostname or IP address
        @param port : Port to write to
        """
        self.host = host
        self.port = port
        self.open()

    def open(self):
        """ Open TCP socket and set it as escpos device """
        self.device = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.device.connect((self.host, self.port))
        self.printer = brotherprint.BrotherPrint(
            self.device, None, 'wifi')
        if self.device is None:
            print
            "Could not open socket for %s" % self.host

    def __del__(self):
        """ Close TCP connection """
        self.printer = None
        self.device.close()


class LabelPrinter(object):

    def connectUsb(
            self, idVendor, idProduct, interface=0,
            in_ep=0x82, out_ep=0x01
    ):
        self.obj = USBPrinter(0x04f9, 0x203c)
        self.printer = self.obj.printer

    def connectNet(
            self, host, port=9100
    ):
        self.obj = NetworkPrinter(host, port=9100)
        self.printer = self.obj.printer

    def PrintBarcode(self, label, data):
        try:
            print
            " Test printing"

            print
            self.printer
            self.printer.command_mode()
            self.printer.initialize()
            self.printer.compressed_char('on')
            self.printer.alignment('center')
            self.printer.send(label)
            self.printer.line_feed()
            self.printer.barcode(
                data, "code39", characters='on', height=250,
                equalize='on', width='xsmall', rss_symbol='rss14trun'
            )
            self.printer.print_page('full')
        except:
            print("Error in printing")

    def PrintMachinecode(self, label, data, label2, data2):
        try:
            self.printer = brotherprint.BrotherPrint(self.device, self.ep, 'usb')
            self.printer.command_mode()
            self.printer.initialize()
            self.printer.compressed_char('on')
            self.printer.alignment('center')

            self.printer.send(label)
            self.printer.line_feed()
            self.printer.barcode(
                data, "code39", characters='on', height=250,
                equalize='on', width='xsmall', rss_symbol='rss14trun'
            )
            self.printer.line_feed()
            self.printer.send(label2)
            self.printer.line_feed()
            self.printer.barcode(
                data2, "code39", characters='on', height=250,
                equalize='on', width='xsmall', rss_symbol='rss14trun'
            )

            self.printer.print_page('full')
        except:
            print("Error in printing")

# printer = Printer(0x04f9, 0x203c)
# printer.PrintBarcode('TEST','50052220')
# printer.PrintMachinecode('device','20162001', 'mac','02190a02cb04')
