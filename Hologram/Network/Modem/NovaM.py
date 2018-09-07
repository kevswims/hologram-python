# NovaM.py - Hologram Python SDK Hologram Nova R404/R410 modem interface
#
# Author: Hologram <support@hologram.io>
#
# Copyright 2016-2018 - Hologram, Inc
#
#
# LICENSE: Distributed under the terms of the MIT License
#

from Nova import Nova
from Hologram.Event import Event
from Exceptions.HologramError import NetworkError
from UtilClasses import Location
from UtilClasses import ModemResult

DEFAULT_NOVAM_TIMEOUT = 200

class NovaM(Nova):

    usb_ids = [('05c6', '90b2')]
    module = 'option'
    syspath = '/sys/bus/usb-serial/drivers/option1/new_id'

    def __init__(self, device_name=None, baud_rate='9600',
                 chatscript_file=None, event=Event()):
        super(NovaM, self).__init__(device_name=device_name, baud_rate=baud_rate,
                                         chatscript_file=chatscript_file, event=event)
        self._at_sockets_available = True
        modem_id = self.modem_id
        if("R404" in modem_id):
            self.is_r410 = False
        else:
            self.is_r410 = True
        self.last_location = None
        self._gnss_enabled = False


    def init_serial_commands(self):
        self.command("E0") #echo off
        self.command("+CMEE", "2") #set verbose error codes
        self.command("+CPIN?")
        self.command("+CPMS", "\"ME\",\"ME\",\"ME\"")
        self.set_sms_configs()
        self.set_network_registration_status()

    def set_network_registration_status(self):
        self.command("+CEREG", "2")

    def is_registered(self):
        return self.check_registered('+CEREG')

    def close_socket(self, socket_identifier=None):

        if socket_identifier is None:
            socket_identifier = self.socket_identifier

        ok, r = self.set('+USOCL', "%s" % socket_identifier, timeout=40)
        if ok != ModemResult.OK:
            self.logger.error('Failed to close socket')

    @property
    def description(self):
        modemtype = '(R410)' if self.is_r410 else '(R404)'
        return 'Hologram Nova US 4G LTE Cat-M1 Cellular USB Modem ' + modemtype

    def population_location_obj(self, response):
        response_list = response.split(',')
        self.last_location = Location(*response_list)
        return self.last_location

    def _handle_location_urc(self, urc):
        self.population_location_obj(urc.lstrip('+UULOC: '))
        self.event.broadcast('location.received')

    @property
    def location(self):
        temp_loc = self.last_location
        if not self._gnss_enabled:
            ok, _ = self.set('+UGPIOC', '23,3')
            if ok != ModemResult.OK:
                self.logger.error('Failed to enable GNSS module')
                return None
            ok, _ = self.set('+UGPIOC', '24,4')
            if ok != ModemResult.OK:
                self.logger.error('Failed to enable GNSS module')
                return None
            self._gnss_enabled = True

        if self._set_up_pdp_context():
            self.last_location = None
            ok, r = self.set('+ULOC', '2,3,0,10,10')
            if ok != ModemResult.OK:
                self.logger.error('Location request failed')
                return None
            while self.last_location is None and self._is_pdp_context_active():
                self.checkURC()
        if self.last_location is None:
            self.last_location = temp_loc
        return self.last_location

    @property
    def operator(self):
        # R4 series doesn't have UDOPN so need to override
        ret = self._basic_command('+COPS?')
        parts = ret.split(',')
        if len(parts) >= 3:
            return parts[2].strip('"')
        return None


    # same as Modem::connect_socket except with longer timeout
    def connect_socket(self, host, port):
        at_command_val = "%d,\"%s\",%s" % (self.socket_identifier, host, port)
        ok, _ = self.set('+USOCO', at_command_val, timeout=122)
        if ok != ModemResult.OK:
            self.logger.error('Failed to connect socket')
            raise NetworkError('Failed to connect socket')
        else:
            self.logger.info('Connect socket is successful')
