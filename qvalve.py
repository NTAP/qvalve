#! /usr/bin/env python3

# SPDX-License-Identifier: BSD-2-Clause
#
# Copyright (c) 2018, NetApp, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Based on the following gist of unknown license (inquiry poending):
# https://gist.github.com/vxgmichel/b2cf8536363275e735c231caef35a5df


import argparse
import asyncio

parser = argparse.ArgumentParser(description='Muck with QUIC packet flows.')
parser.add_argument('-fa', '--forward-address', required=True, metavar='IP',
                    dest='fwd_addr', help='IP address to forward to')
parser.add_argument('-fp', '--forward-port', default='4433', metavar='port',
                    type=int, dest='fwd_port', help='UDP port to forward to')
parser.add_argument('-la', '--listen-address', default='0.0.0.0', metavar='IP',
                    dest='ltn_addr', help='IP address to listen on')
parser.add_argument('-lp', '--listen-port', default='4433', metavar='port',
                    type=int, dest='ltn_port', help='UDP port to listen on')
args = parser.parse_args()

pkt_cnt = {}


class ProxyDatagramProtocol(asyncio.DatagramProtocol):

    def __init__(self, remote_address):
        self.remote_address = remote_address
        self.remotes = {}
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if addr in self.remotes:
            pkt_cnt[addr] += 1
            print('RX pkt {} w/{} bytes (type 0x{:02x}) from {}:{}'
                  .format(pkt_cnt[addr], len(data), data[0], *addr))
            self.remotes[addr].transport.sendto(data)
            return
        print('New connection from {}:*'.format(*addr))
        pkt_cnt[addr] = 0
        loop = asyncio.get_event_loop()
        self.remotes[addr] = RemoteDatagramProtocol(self, addr, data)
        coro = loop.create_datagram_endpoint(
            lambda: self.remotes[addr], remote_addr=self.remote_address)
        asyncio.ensure_future(coro)


class RemoteDatagramProtocol(asyncio.DatagramProtocol):

    def __init__(self, proxy, addr, data):
        self.proxy = proxy
        self.addr = addr
        self.data = data
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport
        pkt_cnt[self.addr] += 1
        print('RX pkt {} w/{} bytes (type 0x{:02x}) from {}:{}'.
              format(pkt_cnt[self.addr], len(self.data), self.data[0],
                     *self.addr))
        self.transport.sendto(self.data)

    def datagram_received(self, data, addr):
        pkt_cnt[addr] += 1
        print('RX pkt {} w/{} bytes (type 0x{:02x}) from {}:{}'
              .format(pkt_cnt[addr], len(data), data[0], *addr))
        self.proxy.transport.sendto(data, self.addr)

    def connection_lost(self, exc):
        self.proxy.remotes.pop(self.attr)


async def start_datagram_proxy(bind, port, remote_host, remote_port):
    loop = asyncio.get_event_loop()
    protocol = ProxyDatagramProtocol((remote_host, remote_port))
    return await loop.create_datagram_endpoint(
        lambda: protocol, local_addr=(bind, port))


def main(bind=args.ltn_addr, port=args.ltn_port,
         remote_host=args.fwd_addr, remote_port=args.fwd_port):
    loop = asyncio.get_event_loop()
    coro = start_datagram_proxy(bind, port, remote_host, remote_port)
    transport, _ = loop.run_until_complete(coro)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    transport.close()
    loop.close()


if __name__ == '__main__':
    main()
