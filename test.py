from collections import defaultdict


class Rule(object):

    def __init__(self, seqno, op, type):
        self.seqno = seqno;
        self.op = op;
        self.type = type;


class Test(object):

    def __init__(self):
        self.rules_clnt = defaultdict(dict)
        self.rules_serv = defaultdict(dict)

    def add_rule(self, seqno, statement):
        r = Rule(seqno, statement.op, statement.type)
        rules = self.rules_clnt if statement.dir == '>' else self.rules_serv
        assert seqno not in rules[statement.type]
        rules[statement.type][seqno] = r

    def interpret(self, model):
        for s in model.statements:
            print("{} {}{}".format(s.dir, s.type, s.range.start), end='')
            if s.range.__class__.__name__ == "SinglePacket":
                print(" {}".format(s.op))
                self.add_rule(s.range.start, s)
            else:
                print("..{} {}".format(s.range.end, s.op))
                for i in range(s.range.start, s.range.end + 1):
                    self.add_rule(i, s)
