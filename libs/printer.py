# -*- coding: utf-8 -*-
from .brotherprint import *
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



# printer = Printer(0x04f9, 0x203c)
# printer.PrintBarcode('TEST','50052220')
# printer.PrintMachinecode('device','20162001', 'mac','02190a02cb04')
