#! /usr/bin/env python3

# https://gist.github.com/vxgmichel/b2cf8536363275e735c231caef35a5df

"""UDP proxy server."""

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


class ProxyDatagramProtocol(asyncio.DatagramProtocol):

    def __init__(self, remote_address):
        self.remote_address = remote_address
        self.remotes = {}
        super().__init__()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if addr in self.remotes:
            print('RX {} bytes (type {:02x}) from {}'.format(len(data),
                                                             data[0], addr))
            self.remotes[addr].transport.sendto(data)
            return
        print('New connection from {}'.format(addr))
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
        print('RX {} bytes (type {:02x}) from {}'.format(len(self.data),
                                                         self.data[0],
                                                         self.addr))
        self.transport.sendto(self.data)

    def datagram_received(self, data, addr):
        print('RX {} bytes (type {:02x}) from {}'.format(len(data), data[0],
                                                         addr))
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
