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

# Portions of this code are adapted from
# https://gist.github.com/vxgmichel/b2cf8536363275e735c231caef35a5df by Vincent
# Michel.

# SPDX-License-Identifier: MIT
#
# Copyright (c) 2017, Vincent Michel
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import argparse
import asyncio
from struct import *
from collections import defaultdict
from textx import metamodel_from_str
from rules import Rules

parser = argparse.ArgumentParser(description='Predictably impair QUIC flows.')
parser.add_argument('-ra', '--remote-address', required=True, metavar='IP',
                    dest='fwd_addr', help='IP address to forward to')
parser.add_argument('-rp', '--remote-port', default='4433', metavar='port',
                    type=int, dest='fwd_port', help='UDP port to forward to')
parser.add_argument('-la', '--listen-address', default='0.0.0.0', metavar='IP',
                    dest='ltn_addr', help='IP address to listen on')
parser.add_argument('-lp', '--listen-port', default='4433', metavar='port',
                    type=int, dest='ltn_port', help='UDP port to listen on')
parser.add_argument('-r', '--rules', metavar='file',
                    type=str, dest='rules_file', help='Impairment rules')
args = parser.parse_args()

cnt_type = defaultdict(int)
cnt_all = defaultdict(int)

rules = Rules()

reor_q = defaultdict(list)


def print_pkt(dir, len, t, ctype, op=''):
    print('{} {} {}{} {}'.format(dir, len, t, ctype, op))


def fwd_pkt(addr, peer, data, dir, tp, dst=None):
    # now handle the current packet
    t = ''
    if data[0] == (0x80 | 0x7f):
        t = 'i'
    elif data[0] == (0x80 | 0x7e):
        t = 'r'
    elif data[0] == (0x80 | 0x7d):
        t = 'h'
    elif data[0] == (0x80 | 0x7c):
        t = 'z'
    elif data[0] & 0x80 and unpack('!L', data[1:5])[0] == 0:
        t = 'v'
    elif (data[0] & 0x80) == 0 and (data[0] & 0b00110000) == 0b00110000:
        t = 's'
    assert t != ''

    cnt_all[addr, peer] += 1
    cnt_type[t, addr, peer] += 1

    r = rules.clnt if dir == '>' else rules.serv
    if (t in r) and (cnt_type[t, addr, peer] in r[t]):
        rule = r[t][cnt_type[t, addr, peer]]
        if (t == rule.type):
            if rule.op.str == 'drop':
                print_pkt(dir, len(data), t, cnt_type[t, addr, peer],
                          rule.op.str)
                # don't send

            elif rule.op.str == 'dup':
                for i in range(rule.op.copies + 1):
                    if i > 0:
                        cnt_all[addr, peer] += 1
                        print_pkt(dir, len(data), t, cnt_type[t, addr, peer],
                                  '({})'.format(rule.op.str))
                    else:
                        print_pkt(dir, len(data), t, cnt_type[t, addr, peer],
                                  '{} {}'.format(rule.op.str, rule.op.copies))
                    tp.sendto(data, dst)

            elif rule.op.str == 'reor':
                cnt_all[addr, peer] -= 1
                print_pkt(dir, len(data), t, cnt_type[t, addr, peer],
                          '{} {} (enq)'.format(rule.op.str, rule.op.count))
                # enqueue the packet
                q = reor_q[addr, peer, cnt_all[addr, peer] + rule.op.count]
                q.append({'transport': tp, 'data': data, 'dst': dst,
                          't': t, 'ctype': cnt_type[t, addr, peer]})

            elif rule.op.str == 'nop':
                print_pkt(dir, len(data), t, cnt_type[t, addr, peer])
                tp.sendto(data, dst)

            else:
                # what op is this?
                assert False, 'unknown op {}'.format(rule.op.str)
    else:
        print_pkt(dir, len(data), t, cnt_type[t, addr, peer])
        tp.sendto(data, dst)

    # check if we need to dequeue and tx prior reordered packets
    if reor_q[addr, peer, cnt_all[addr, peer]]:
        for p in reor_q[addr, peer, cnt_all[addr, peer]]:
            p['transport'].sendto(p['data'], p['dst'])
            cnt_all[addr, peer] += 1
            print_pkt(dir, len(p['data']), p['t'], p['ctype'], '(reor deq)')
        reor_q[addr, peer, cnt_all[addr, peer]].clear()


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
            fwd_pkt(addr, peername, data, '>', self.remotes[addr].transport)
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
        fwd_pkt(self.addr, peername, self.data, '>', self.transport)

    def datagram_received(self, data, addr):
        fwd_pkt(addr, self.addr, data, '<', self.proxy.transport, self.addr)

    def connection_lost(self, exc):
        print('LOST')
        self.proxy.remotes.pop(self.attr)


async def start_datagram_proxy(bind, port, remote_addr, remote_port):
    loop = asyncio.get_event_loop()
    protocol = ProxyDatagramProtocol((remote_addr, remote_port))
    return await loop.create_datagram_endpoint(
        lambda: protocol, local_addr=(bind, port))


metamodel = r"""
    Rules: rules*=Rule;
    Rule: dir=Direction type=PacketType range=Range op=Operation;
    Direction: '<' | '>';
    PacketType: 'i' | 'r' | 'h' | 'z' | 'v' | 's';
    Range: PacketRange | SinglePacket;
    SinglePacket: start=INT;
    PacketRange: start=INT '..' end=INT;
    Operation: str='drop' | str='nop' | str='dup' (copies=INT)? |
               str='reor' (count=INT)?;
    Comment: /#.*$/;
"""


def op_processor(op):
    # if copies is not given for a dup op, set it to 1
    if op.str == 'dup' and op.copies == 0:
        op.copies = 1
    elif op.str == 'reor' and op.count == 0:
        op.count = 1


def main(bind=args.ltn_addr, port=args.ltn_port,
         remote_addr=args.fwd_addr, remote_port=args.fwd_port):
    if args.rules_file:
        qvalve_mm = metamodel_from_str(metamodel, ignore_case=True)
        qvalve_mm.register_obj_processors({'Operation': op_processor})
        qvalve_model = qvalve_mm.model_from_file(args.rules_file)
        print('Parsing {}:'.format(args.rules_file))
        rules.interpret(qvalve_model)

    print('\nListening on {}:{} and applying rules:'.format(bind, port))
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
