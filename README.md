# qvalve

`qvalve` can predictably impair QUIC flows, by dropping or duplicating
individual packets and sequences of packets. It is a non-transparent UDP proxy
that should be interposed between a QUIC client and a QUIC server.

The behavior of `qvalve` is configured with rules specified in a simple
language. Examples:

```
# drop the first three client initial packets
> i1..3 drop

# drop the first server version-negotiation packet
< v1 drop

# duplicate the second server version-negotiation packet three times
< v2 dup 3

# nop does nothing
< h1 nop
```

More examples are in the `tests` directory.
