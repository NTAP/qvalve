class Test(object):

    def __init__(self):
        self.drop_client = {}
        self.drop_server = {}

    def interpret(self, model):
        for s in model.statements:

            if s.range.__class__.__name__ == "SinglePacket":
                print("{} op on {}-type {} pkt {}"
                      .format(s.op, s.type, s.dir, s.range.start))
            else:
                print("{} op on {}-type {} pkts {}..{}"
                      .format(s.op, s.type, s.dir, s.range.start, s.range.end))
