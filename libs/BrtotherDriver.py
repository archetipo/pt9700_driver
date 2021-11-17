# -*- coding: utf-8 -*-
import logging
import subprocess
from threading import Thread, Lock
from queue import Queue, Empty
from datetime import datetime
import json
import time
from .printer import USBPrinter


try:
    import usb.core
except ImportError:
    usb = None

BANNED_DEVICES = [
    "0424:9514",  # Standard Microsystem Corp. Builtin Ethernet module
    "1d6b:0002",  # Linux Foundation 2.0 root hub
    "1d6b:0001",  # Linux Foundation 1.0 root hub
    "0424:ec00",  # Standard Microsystem Corp. Other Builtin Ethernet module
]
drivers = {}

_logger = logging.getLogger(__name__)


class BrotherDriver(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.queue = Queue()
        self.lock = Lock()
        self.status = {'status': 'connecting', 'messages': []}
        self.isstarted = False

    def connected_usb_devices(self):
        connected = []

        # printers can either define bDeviceClass=7, or they can define one of
        # their interfaces with bInterfaceClass=7. This class checks for both.
        class FindUsbClass(object):
            def __init__(self, usb_class):
                self._class = usb_class

            def __call__(self, device):
                # first, let's check the device
                if device.bDeviceClass == self._class:
                    return True
                # transverse all devices and look through their interfaces to
                # find a matching class
                for cfg in device:
                    intf = usb.util.find_descriptor(cfg, bInterfaceClass=self._class)

                    if intf is not None:
                        return True

                return False

        printers = usb.core.find(
            find_all=True, custom_match=FindUsbClass(7))

        # if no printers are found after this step we will take the
        # first epson or star device we can find.

        # brother
        if not printers:
            printers = usb.core.find(find_all=True, idVendor=0x04f9)
        # epson
        if not printers:
            printers = usb.core.find(find_all=True, idVendor=0x04b8)
        # star
        if not printers:
            printers = usb.core.find(find_all=True, idVendor=0x0519)
        for device in printers:
            try:
                # device.set_configuration()
                connected.append({
                    'vendor': device.idVendor,
                    'product': device.idProduct,
                    'name': usb.util.get_string(
                        device, device.iManufacturer) + " " + usb.util.get_string(
                        device, device.iProduct)
                })
            except usb.core.USBError as usb_error:
                print
                "resource Busy" + str(usb_error)
                if 'Resource busy' in str(usb_error):
                    if device.is_kernel_driver_active(0):
                        device.detach_kernel_driver(0)
                        device.set_configuration()
            device._langids = (1033,)

        return connected

    def lockedstart(self):
        if not self.isstarted:
            self.daemon = False
            self.start()

    def get_usb_printer(self):
        printers = self.connected_usb_devices()
        if len(printers) > 0:
            self.set_status('connected', 'Connected to ' + printers[0]['name'])
            return USBPrinter(printers[0]['vendor'], printers[0]['product'])
        else:
            self.set_status('disconnected', 'Printer Not Found')
            return None

    def get_status(self):
        self.get_usb_printer()
        return self.status

    def set_status(self, status, message=None):
        _logger.info(status + ' : ' + (message or 'no message'))
        if status == self.status['status']:
            if message != None and (len(self.status['messages']) == 0 or message != self.status['messages'][-1]):
                self.status['messages'].append(message)
        else:
            self.status['status'] = status
            if message:
                self.status['messages'] = [message]
            else:
                self.status['messages'] = []

        if status == 'error' and message:
            _logger.error('ESC/POS Error: ' + message)
        elif status == 'disconnected' and message:
            _logger.warning('ESC/POS Device Disconnected: ' + message)

    def run(self):
        printer = None
        if not escpos:
            _logger.error('Printer cannot initialize, please verify system dependencies.')
            return
        while True:
            try:
                error = True
                self.isstarted = True
                timestamp, task, data = self.queue.get(True)
                printer = self.get_usb_printer()
                _logger.info(task)

                if printer == None:
                    if task != 'status':
                        self.queue.put((timestamp, task, data))
                    error = False
                    time.sleep(5)
                    continue
                elif task == 'barcode':
                    error = False
                    _logger.info("exec task barcode")
                    self.printBarcode(printer, data)
                elif task == 'qrcode':
                    error = False
                    _logger.info("exec task barcode")
                    self.printQrCode(printer, data)
                elif task == 'status':
                    pass
                error = False
            except Exception as e:
                self.set_status('error', str(e))
                self.isstarted = False
                errmsg = str(e) + '\n' + '-' * 60 + '\n' + traceback.format_exc() + '-' * 60 + '\n'
                self.daemon = True
                _logger.error(errmsg);
            finally:
                # self.isstarted =False
                if error:
                    self.queue.put((timestamp, task, data))
                if printer:
                    printer.close()

    def push_task(self, task, data=None):
        self.lockedstart()
        self.queue.put((time.time(), task, data))

    def printBarcode(self, eprint, label):
        _logger.info("try to print task barcode")
        _logger.info(label)
        printer = eprint.printer
        printer.command_mode()
        printer.initialize()
        printer.compressed_char('on')
        printer.alignment('center')
        printer.send(label['label'])
        printer.line_feed()
        pHeight = 125
        if ('labelh' in label and label['labelh'] == 36):
            pHeight = 250
        printer.barcode(
            label['data'].encode('utf8'), "code39", characters='on', height=pHeight,
            equalize='on', width='xsmall', rss_symbol='rss14trun'
        )
        printer.line_feed()
        printer.send(label['company'])
        printer.print_page('full')

    def printQrCode(self, eprint, label):
        _logger.info("try to print taskQrCode")
        _logger.info(label)
        printer = eprint.printer
        printer.command_mode()
        printer.initialize()
        printer.compressed_char('on')
        printer.alignment('center')
        printer.send(label['label'])
        printer.line_feed()
        printer.qrcode(
            label['data'].encode('utf8')
        )
        printer.print_page('full')

