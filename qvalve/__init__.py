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

from collections import defaultdict


class Rule(object):

    def __init__(self, seqno, op, type):
        self.seqno = seqno
        self.op = op
        self.type = type


class Rules(object):

    def __init__(self):
        self.clnt = defaultdict(dict)
        self.serv = defaultdict(dict)

    def add_rule(self, seqno, rule):
        r = Rule(seqno, rule.op, rule.type)
        rules = self.clnt if rule.dir == '>' else self.serv
        assert seqno not in rules[rule.type], \
            'Already have a rule for {}{}'.format(rule.type, seqno)
        rules[rule.type][seqno] = r

    def interpret(self, model):
        for s in model.rules:
            print('{} {}{}'.format(s.dir, s.type, s.range.start), end='')

            if s.range.__class__.__name__ == 'SinglePacket':
                self.add_rule(s.range.start, s)
            else:
                print('..{}'.format(s.range.end), end='')
                for i in range(s.range.start, s.range.end + 1):
                    self.add_rule(i, s)

            if s.op.str == 'dup':
                assert s.op.copies > 0, \
                    '{} copies cannot be {}'.format(s.op.str, s.op.copies)
                print(' {} {}'.format(s.op.str, s.op.copies))
            elif s.op.str == 'reor':
                assert s.op.count > 0, \
                    '{} count cannot be {}'.format(s.op.str, s.op.count)
                print(' {} {}'.format(s.op.str, s.op.count))
            else:
                print(' {}'.format(s.op.str))
