# -*- coding: UTF-8 -*-
import re


class StringReader(object):
    def __init__(self, text):
        self.text = text
        self.maxlength = len(text)
        self.currentPosition = 0

    def isOverLength(self, length):
        return length >= self.maxlength or length < 0

    def isCurrentPositionValid(self):
        return self.isPositionValid(self.currentPosition)

    def isPositionValid(self, p):
        return p >= 0 and p < self.maxlength

    def peek(self, length):
        if not self.isCurrentPositionValid():
            return None
        m = self.currentPosition
        n = m + length
        if self.isOverLength(n):
            return self.text[m:]
        else:
            return self.text[m:n]

    def peekNext(self):
        return self.peek(1)

    def read(self, length):
        if not self.isCurrentPositionValid():
            return None
        m = self.currentPosition
        n = m + length
        if self.isOverLength(n):
            self.currentPosition = -1
            return self.text[m:]
        else:
            self.currentPosition += length
            return self.text[m:n]

    def readNext(self):
        return self.read(1)

    def skipBlank(self):
        if not self.isCurrentPositionValid():
            return
        while self.peekNext() == ' ':
            self.readNext()

    def readStringPatternWord(self, pattern):
        if not self.isCurrentPositionValid():
            return None
        l = self.peekNext()
        if not l:
            return None
        result = ''
        while l and re.compile(pattern).match(l):
            result += self.readNext()
            l = self.peekNext()
        return result

    def readStringVariable(self):
        if not self.isCurrentPositionValid():
            return None
        m = self.currentPosition
        text = self.text[m:]
        v = self.text[m]
        if v == '"' or v == "'":
            try:
                idx = text.index(v, 1)
                n = idx + 1
                self.currentPosition += n
                if not self.isCurrentPositionValid():
                    self.currentPosition = -1
                return text[:n]
            except ValueError as e:
                return None
        else:
            return None

    def isEnd(self):
        return self.currentPosition == -1


class Parser(object):
    def __init__(self, text):
        self.text = text
        self.textStack = []
        self.parseStack = []
        self.priorityStack = []
        self.reader = StringReader(text)
        self.pair = {
            ')': '('
        }

        self.syntax_definition = {
            'condition': [
                (1, '\('),
                (1, '\)'),
                (1, '\|'),
                (1, ',')
            ],
            'operator': [
                (1, '='),   # equal
                (2, '!='),  # not equal
                (1, '@'),   # between
                (2, '!@'),  # not between
                (1, '%'),   # contains
                (2, '!%'),  # not contains
                (1, '>'),   # great than
                (1, '<'),   # less than
                (2, '>='),  # great equal than
                (2, '<=')   # less equal than
            ]
        }
        self.string_definition = {
            'string': [(1, """["']""")]
        }
        self.variable_definiation = {
            'variable': [(1, """[A-Za-z0-9_]""")]
        }
        self.convertToStack()

    def checkDefinition(self, table, char):
        # result = None
        for k, v in table.items():
            for l, p in v:
                if len(char) == l and re.compile(p).match(char):
                    return (k, p)
        return (None, None)

    def convertToStack(self):
        self.reader.skipBlank()
        while not self.reader.isEnd():
            if self.reader.peekNext() == ' ':
                self.reader.skipBlank()
            else:
                char2 = self.reader.peek(2)
                (syntaxDef, pattern) = self.checkDefinition(self.syntax_definition, char2)
                if syntaxDef:
                    self.reader.read(2)
                    self.textStack.insert(0, (syntaxDef, char2))
                    continue
                char = self.reader.peekNext()
                (syntaxDef, pattern) = self.checkDefinition(self.syntax_definition, char)
                if syntaxDef:
                    self.reader.readNext()
                    self.textStack.insert(0, (syntaxDef, char))
                    continue
                (stringDef, pattern) = self.checkDefinition(self.string_definition, char)
                if stringDef:
                    word = self.reader.readStringVariable()
                    self.textStack.insert(0, (stringDef, word))
                    continue
                (varDef, pattern) = self.checkDefinition(self.variable_definiation, char)
                if varDef:
                    word = self.reader.readStringPatternWord(pattern)
                    self.textStack.insert(0, (varDef, word))
                    continue
                self.raiseError('Scan error, char not allow', (None, self.reader.currentPosition))

    def convertToStackbak(self):
        self.reader.skipBlank()
        while not self.reader.isEnd():
            if self.reader.peekNext() == ' ':
                self.reader.skipBlank()
            elif self.reader.peekNext() == '"' or self.reader.peekNext() == '"':
                word = self.reader.readStringVariable()
                if word:
                    self.textStack.insert(0, ('value', word))
                else:
                    word = self.reader.readStringPatternWord("""[\w"']""")
                    self.textStack.insert(0, ('name', word))
            elif self.reader.peek(2) == '!=' or self.reader.peek(2) == '>=' or self.reader.peek(
                    2) == '<=' or self.reader.peek(2) == '!#':
                word = self.reader.read(2)
                self.textStack.insert(0, ('operator', word))
            elif self.reader.peekNext() == '(' or self.reader.peekNext() == ')' or self.reader.peekNext() == ',' or self.reader.peekNext() == '|':
                word = self.reader.readNext()
                self.textStack.insert(0, ('condition', word))
            elif self.reader.peekNext() == '@' or self.reader.peekNext() == '!' or self.reader.peekNext() == '@' or self.reader.peekNext() == '=':
                word = self.reader.readNext()
                self.textStack.insert(0, ('operator', word))
            else:
                word = self.reader.readStringPatternWord('\w')
                if word:
                    self.textStack.insert(0, ('name', word))
                else:
                    self.raiseError('Scan error', (None, self.reader.currentPosition))

    def raiseError(self, desc, node):
        raise Exception('%s at %s' % (desc, node[1]))

    def parsePush(self, node, status, parseFunc, parseEndStatus):
        self.textStack.pop()
        status.append(node[1])
        result = parseFunc(status)
        status[-1] = parseEndStatus
        return result

    def parsePop(self, node, status, parseEndStatus):
        previousChar = self.pair.get(node[1], None)
        if not previousChar:
            return
        if len(status) > 2 and status[-2] == previousChar:
            self.textStack.pop()
            status.pop()
            status[-1] = parseEndStatus
        else:
            self.raiseError('Parse error, mismatch %s' % node[1], node)

    def parseSingleCondition(self, status):
        operator = None
        fieldName = None
        value = None
        status.append('S')
        finished = False
        while len(self.textStack) > 0 and status[-1] != 'E':
            node = self.textStack[-1]
            if status[-1] == 'S':
                if node[0] == 'variable':
                    status[-1] = 'S1'
                    fieldName = node[1]
                    self.textStack.pop()
                else:
                    self.raiseError('Parse error, should be name', node)
            elif status[-1] == 'S1':
                if node[0] == 'operator':
                    status[-1] = 'S2'
                    operator = node[1]
                    self.textStack.pop()
                else:
                    self.raiseError('Parse error, should be operator', node)
            elif status[-1] == 'S2':
                if node[0] == 'string':
                    value = node[1]
                    status[-1] = 'E'
                    self.textStack.pop()
                else:
                    self.raiseError('Parse error, should be value', node)
        status.pop()
        return ('condition', (operator, fieldName, value))

    def parseCondition(self, status):
        status.append('S')
        finished = False
        left_result = None
        right_result = None
        operator = None
        while len(self.textStack) > 0 and status[-1] != 'E':
            node = self.textStack[-1]
            if status[-1] == 'S':
                if node[0] == 'condition' and node[1] == '(':
                    left_result = self.parsePush(node, status, self.parseCondition, 'S1')
                elif node[0] == 'variable':
                    left_result = self.parseSingleCondition(status)
                    status[-1] = 'S1'
                else:
                    self.raiseError('Parse error, should be nest condition or condition', node)
            elif status[-1] == 'S1':
                right_result = None
                if node[0] == 'condition' and node[1] == '|':
                    status[-1] = 'S'
                    operator = 'or'
                    self.textStack.pop()
                    self.priorityStack.append(('or', left_result))
                elif node[0] == 'condition' and node[1] == ',':
                    status[-1] = 'S2'
                    operator = 'and'
                    self.textStack.pop()
                elif node[0] == 'condition' and node[1] == ')':
                    self.parsePop(node, status, 'E')
                else:
                    self.raiseError('Parse error, should be and or bracket', node)
            elif status[-1] == 'S2':
                if node[0] == 'condition' and node[1] == '(':
                    right_result = self.parsePush(node, status, self.parseCondition, 'S3')
                elif node[0] == 'variable':
                    right_result = self.parseSingleCondition(status)
                    status[-1] = 'S3'
                else:
                    self.raiseError('Parse error, should be nest condition or condition', node)
            elif status[-1] == 'S3':
                if node[0] == 'condition' and node[1] == ')':
                    self.parsePop(node, status, 'E')
                elif node[0] == 'condition':
                    if len(status) > 0:
                        status[-1] = 'S1'
                        left_result = (operator, left_result, right_result)

                else:
                    self.raiseError('Parse error, not be any text here', node)
        status.pop()
        if operator and right_result:
            finalResult = ('andor', (operator, left_result, right_result))
            # finalResult = (operator, left_result, right_result)
        else:
            finalResult = left_result
        while len(self.priorityStack) > 0:
            (left_operator, left_result_in_stack) = self.priorityStack.pop()
            finalResult = (left_operator, left_result_in_stack, finalResult)
        return finalResult

    def parse(self):
        status = []
        return self.parseCondition(status)

    def loop(self, result):
        (type, node) = result[0], result[1]
        if type == 'andor':
            return self.loop(node)
        elif type == 'condition':
            return self.loop(node)
        n, l, r = result[0], result[1], result[2]
        if n == 'and' or n == 'or':
            left = self.loop(l)
            right = self.loop(r)
            if n == 'and':
                return '(%s %s %s)' % (left, ' && ', right)
            else:
                return '(%s %s %s)' % (left, ' || ', right)
        else:
            return '%s %s %s' % (l, n, r)

    def toDict(self, result):
        (type, node) = result[0], result[1]
        if type == 'andor':
            dict = self.toDict(node)
            return dict
        elif type == 'condition':
            dict = self.toDict(node)
            return dict
        n, l, r = result[0], result[1], result[2]
        if n == 'and' or n == 'or':
            left = self.toDict(l)
            right = self.toDict(r)
            return {'opt': n, 'left': left, 'right': right}
        else:
            # Remove padding ' "
            r = r[1:-1]
            return {'opt': n, 'field': l, 'value': r}
