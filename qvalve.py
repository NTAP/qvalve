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

# Based on the following gist of unknown license (inquiry pending):
# https://gist.github.com/vxgmichel/b2cf8536363275e735c231caef35a5df


import argparse
import asyncio
from collections import defaultdict
from textx import metamodel_from_str
from test import Test

parser = argparse.ArgumentParser(description='Muck with QUIC packet flows.')
parser.add_argument('-ra', '--remote-address', required=True, metavar='IP',
                    dest='fwd_addr', help='IP address to forward to')
parser.add_argument('-rp', '--remote-port', default='4433', metavar='port',
                    type=int, dest='fwd_port', help='UDP port to forward to')
parser.add_argument('-la', '--listen-address', default='0.0.0.0', metavar='IP',
                    dest='ltn_addr', help='IP address to listen on')
parser.add_argument('-lp', '--listen-port', default='4433', metavar='port',
                    type=int, dest='ltn_port', help='UDP port to listen on')
parser.add_argument('-t', '--test', metavar='file',
                    type=str, dest='test_file', help='Test case definition')
args = parser.parse_args()

pkt_cnt = defaultdict(int)
test = Test()


def fwd_pkt(addr, peername, data, dir):
    t = ''
    if data[0] == (0x80 | 0x7f):
        t = 'i'
    elif data[0] == (0x80 | 0x7e):
        t = 'r'
    elif data[0] == (0x80 | 0x7d):
        t = 'h'
    elif data[0] == (0x80 | 0x7c):
        t = 'z'
    elif data[0] & 0x80:
        t = 'v'
    elif (data[0] & 0x80) == 0 and (data[0] & 0b00110000) == 0b00110000:
        t = 's'
    assert t != ''

    pkt_cnt[t, addr, peername] += 1
    n = pkt_cnt[t, addr, peername]

    print('{} {} {}{} '.format(dir, len(data), t, n), end='')

    rules = test.rules_clnt if dir == '>' else test.rules_serv
    if (t in rules) and (n in rules[t]):
        r = rules[t][n]
        if (t == r.type):
            print(r.op)
            if r.op == 'drop':
                return False
            elif r.op == 'nop':
                return True
            assert False, "unknown op {}".format(r.op)

    print()
    return True



class ProxyDatagramProtocol(asyncio.DatagramProtocol):

    def __init__(self, remote_addr):
        self.remote_addr = remote_addr
        self.remotes = {}
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if addr in self.remotes:
            peername = self.remotes[addr].transport.get_extra_info('peername')
            if fwd_pkt(addr, peername, data, '>') == True:
                self.remotes[addr].transport.sendto(data)
            return
        loop = asyncio.get_event_loop()
        self.remotes[addr] = RemoteDatagramProtocol(self, addr, data)
        coro = loop.create_datagram_endpoint(
            lambda: self.remotes[addr], remote_addr=self.remote_addr)
        asyncio.ensure_future(coro)


class RemoteDatagramProtocol(asyncio.DatagramProtocol):

    def __init__(self, proxy, addr, data):
        self.proxy = proxy
        self.addr = addr
        self.data = data
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport
        peername = transport.get_extra_info('peername')
        if fwd_pkt(self.addr, peername, self.data, '>') == True:
            self.transport.sendto(self.data)

    def datagram_received(self, data, addr):
        if fwd_pkt(addr, self.addr, data, '<') == True:
            self.proxy.transport.sendto(data, self.addr)

    def connection_lost(self, exc):
        print('LOST')
        self.proxy.remotes.pop(self.attr)


async def start_datagram_proxy(bind, port, remote_addr, remote_port):
    loop = asyncio.get_event_loop()
    protocol = ProxyDatagramProtocol((remote_addr, remote_port))
    return await loop.create_datagram_endpoint(
        lambda: protocol, local_addr=(bind, port))


metamodel = r"""
    Script: statements*=Statement;
    Statement: dir=Direction type=PacketType range=Range op=Operation;
    Direction: '<' | '>';
    PacketType: 'i' | 'r' | 'h' | 'z' | 'v' | 's';
    Range: PacketRange | SinglePacket;
    SinglePacket: start=INT;
    PacketRange: start=INT '..' end=INT;
    Operation: 'drop' | 'nop' | 'dup';
    Comment: /#.*$/;
"""


def main(bind=args.ltn_addr, port=args.ltn_port,
         remote_addr=args.fwd_addr, remote_port=args.fwd_port):
    if args.test_file:
        qvalve_mm = metamodel_from_str(metamodel)
        qvalve_model = qvalve_mm.model_from_file(args.test_file)
        print('Parsing test:')
        test.interpret(qvalve_model)

    print('\nApplying rules:')
    loop = asyncio.get_event_loop()
    coro = start_datagram_proxy(bind, port, remote_addr, remote_port)
    transport, _ = loop.run_until_complete(coro)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    transport.close()
    loop.close()


if __name__ == '__main__':
    main()
