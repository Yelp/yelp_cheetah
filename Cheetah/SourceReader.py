"""SourceReader class for Cheetah's LegacyParser and CodeGenerator"""
from __future__ import unicode_literals

import re

EOLre = re.compile(r'[ \f\t]*(?:\r\n|\r|\n)')
EOLZre = re.compile(r'(?:\r\n|\r|\n|\Z)')


WS_CHARS = ' \t'


class SourceReader(object):  # pylint:disable=too-many-public-methods
    def __init__(self, src):
        self._src = src
        self._srcLines = src.splitlines()
        self._breakPoint = len(self._src)
        self._pos = 0

        # collect some meta-information
        self._EOLs = []
        pos = 0
        while pos < len(self):
            EOLmatch = EOLZre.search(src, pos)
            self._EOLs.append(EOLmatch.start())
            pos = EOLmatch.end()

        self._BOLs = []
        for pos in self._EOLs:
            BOLpos = self.findBOL(pos)
            self._BOLs.append(BOLpos)

    def src(self):
        return self._src

    def __len__(self):
        return self._breakPoint

    def __getitem__(self, i):
        return self._src[i]

    def lineNum(self, pos):
        for i in range(len(self._BOLs)):
            if pos >= self._BOLs[i] and pos <= self._EOLs[i]:
                return i
        raise AssertionError('unknown position: {}'.format(pos))

    def getRowCol(self, pos=None):
        if pos is None:
            pos = self._pos
        lineNum = self.lineNum(pos)
        BOL = self._BOLs[lineNum]
        return lineNum + 1, pos - BOL + 1

    def getRowColLine(self):
        row, col = self.getRowCol()
        return row, col, self._srcLines[row - 1]

    def pos(self):
        return self._pos

    def setPos(self, pos):
        self.checkPos(pos)
        self._pos = pos

    def validPos(self, pos):
        return pos <= self._breakPoint and pos >= 0

    def checkPos(self, pos):
        if not pos <= self._breakPoint:
            raise AssertionError(
                "pos ({}) is invalid: beyond the stream's end ({})".format(
                    pos, self._breakPoint - 1
                )
            )
        elif not pos >= 0:
            raise AssertionError("pos (" + str(pos) + ") is invalid: less than 0")

    def breakPoint(self):
        return self._breakPoint

    def setBreakPoint(self, pos):
        if pos > len(self._src):
            raise AssertionError(
                "New breakpoint ({}) is invalid: beyond the end of stream's "
                "source string ({})".format(pos, len(self._src))
            )
        elif not pos >= 0:
            raise AssertionError(
                "New breakpoint (" + str(pos) + ") is invalid: less than 0"
            )

        self._breakPoint = pos

    def atEnd(self):
        return self._pos >= self._breakPoint

    def peek(self, offset=0):
        self.checkPos(self._pos + offset)
        pos = self._pos + offset
        return self._src[pos]

    def getc(self):
        pos = self._pos
        assert self.validPos(pos + 1)
        self._pos += 1
        return self._src[pos]

    def advance(self, offset=1):
        self.checkPos(self._pos + offset)
        self._pos += offset

    def readTo(self, to, start=None):
        self.checkPos(to)
        if start is None:
            start = self._pos
        self._pos = to
        return self._src[start:to]

    def readToEOL(self, start=None, gobble=True):
        EOLmatch = EOLZre.search(self._src, self._pos)
        if gobble:
            pos = EOLmatch.end()
        else:
            pos = EOLmatch.start()
        return self.readTo(to=pos, start=start)

    def find(self, it, pos=None):
        if pos is None:
            pos = self._pos
        return self._src.find(it, pos)

    def startswith(self, it, pos=None):
        return self.find(it, pos) == self._pos

    def findBOL(self, pos=None):
        if pos is None:
            pos = self._pos
        src = self._src
        return max(src.rfind('\n', 0, pos) + 1, src.rfind('\r', 0, pos) + 1, 0)

    def findEOL(self, gobble=False):
        match = EOLZre.search(self._src, self._pos)
        if gobble:
            return match.end()
        else:
            return match.start()

    def isLineClearToStartToken(self):
        BOL = self.findBOL()
        return BOL == self._pos or self._src[BOL:self._pos].isspace()

    def matchWhiteSpace(self):
        return not self.atEnd() and self.peek() in WS_CHARS

    def getWhiteSpace(self, maximum=None):
        if not self.matchWhiteSpace():
            return ''
        start = self._pos
        breakPoint = self.breakPoint()
        if maximum is not None:
            breakPoint = min(breakPoint, self._pos + maximum)
        while self._pos < breakPoint:
            self.advance()
            if not self.matchWhiteSpace():
                break
        return self._src[start:self._pos]
