#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import asyncio
from cme.connection import *
from cme.helpers.logger import highlight
from cme.logger import CMEAdapter

from aardwolf import logger
from aardwolf.vncconnection import VNCConnection
from aardwolf.commons.iosettings import RDPIOSettings

from asyauth.common.credentials import UniCredential
from asyauth.common.constants import asyauthSecret, asyauthProtocol

logger.setLevel(logging.CRITICAL)

class vnc(connection):

    def __init__(self, args, db, host):
        self.iosettings = RDPIOSettings()
        self.iosettings.channels = []
        self.iosettings.video_out_format = VIDEO_FORMAT.RAW
        self.iosettings.clipboard_use_pyperclip = False
        self.url = None
        self.target = None
        self.credential = None
        connection.__init__(self, args, db, host)

    @staticmethod
    def proto_args(parser, std_parser, module_parser):
        vnc_parser = parser.add_parser('vnc', help="own stuff using VNC", parents=[std_parser, module_parser])
        vnc_parser.add_argument("--no-bruteforce", action='store_true', help='No spray when using file for username and password (user1 => password1, user2 => password2')
        vnc_parser.add_argument("--continue-on-success", action='store_true', help="continues authentication attempts even after successes")
        vnc_parser.add_argument("--port", type=int, default=5900, help="Custom VNC port")
        vnc_parser.add_argument("--vnc-sleep", type=int, default=5, help="VNC Sleep on socket connection to avoid rate limit")

        egroup = vnc_parser.add_argument_group("Screenshot", "VNC Server")
        egroup.add_argument("--screenshot", action="store_true", help="Screenshot VNC if connection success")
        egroup.add_argument('--screentime', type=int, default=5, help='Time to wait for desktop image')

        return parser

    def proto_flow(self):
        if self.create_conn_obj():
            self.proto_logger()
            self.print_host_info()
            if self.login():
                if hasattr(self.args, 'module') and self.args.module:
                    self.call_modules()
                else:
                    self.call_cmd_args()

    def proto_logger(self):
        self.logger = CMEAdapter(extra={'protocol': 'VNC',
                                        'host': self.host,
                                        'port': self.args.port,
                                        'hostname': self.hostname})

    def print_host_info(self):
        self.logger.info(u"VNC connecting to {}".format(self.hostname))

    def create_conn_obj(self):
        try:
            self.target = RDPTarget(ip=self.host, port=self.args.port)
            credential = UniCredential(protocol=asyauthProtocol.PLAIN, stype=asyauthSecret.NONE)
            self.conn = VNCConnection(target=self.target, credentials=credential, iosettings=self.iosettings)
            asyncio.run(self.connect_vnc(True))
        except Exception as e:
            logging.debug(str(e))
            if "Server supports:" not in str(e):
                return False
        return True

    async def connect_vnc(self, discover=False):
        _, err = await self.conn.connect()
        if err is not None:
            if not discover:
                await asyncio.sleep(self.args.vnc_sleep)
            raise err
        return True

    def plaintext_login(self, username, password):
        try:
            stype=asyauthSecret.PASS
            if password == "":
                stype = stype=asyauthSecret.NONE
            self.credential = UniCredential(secret=password, protocol=asyauthProtocol.PLAIN, stype=stype)
            self.conn = VNCConnection(target=self.target, credentials=self.credential, iosettings=self.iosettings)
            asyncio.run(self.connect_vnc())

            self.admin_privs = True
            self.logger.success(u'{} {}'.format(password,
                                                    highlight('({})'.format(self.config.get('CME', 'pwn3d_label')) if self.admin_privs else '')))
            if not self.args.continue_on_success:
                return True

        except Exception as e:
            logging.debug(str(e))
            if "Server supports: 1" in str(e):
                self.logger.success(u'{} {}'.format("No password seems to be accepted by the server",
                                                    highlight('({})'.format(self.config.get('CME', 'pwn3d_label')) if self.admin_privs else '')))                
            else:
                self.logger.error(u'{} {}'.format(password,
                                                "Authentication failed"))
            return False

    async def screen(self):
        self.conn = VNCConnection(target=self.target, credentials=self.credential, iosettings=self.iosettings)
        await self.connect_vnc()
        await asyncio.sleep(int(self.args.screentime))
        if self.conn is not None and self.conn.desktop_buffer_has_data is True:
            buffer = self.conn.get_desktop_buffer(VIDEO_FORMAT.PIL)
            filename = os.path.expanduser('~/.cme/screenshots/{}_{}_{}.png'.format(self.hostname, self.host, datetime.now().strftime("%Y-%m-%d_%H%M%S")))
            buffer.save(filename,'png')
            self.logger.highlight("Screenshot saved {}".format(filename))

    def screenshot(self):
        asyncio.run(self.screen())