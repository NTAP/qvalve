# qvalve

`qvalve` can predictably impair QUIC flows, by dropping, reordering or
duplicating individual packets and sequences of packets. It is a non-transparent
UDP proxy that should be interposed between a QUIC client and a QUIC server.

The behavior of `qvalve` is configured with rules specified in a simple
language. Examples:

```
# drop the first three client initial pkts
> i1..3 drop

# drop the first server vneg pkt
< v1 drop

# duplicate the second server vneg pkt three times (= four copies sent)
< v2 dup 3

# reorder the first server handshake pkt (default: by one pkt)
< h1 reor

# nop does nothing
< h2 nop
```

More examples are in the `tests` directory.
