# Convert an RELAX NG compact syntax schema to a Node tree
# This file released to the Public Domain by David Mertz
from . import parser

for type in parser.NODE_TYPES:
    globals()[type] = type

QUANTS = {SOME: 'oneOrMore', MAYBE: 'optional', ANY: 'zeroOrMore'}
TYPELIB_NS = 'http://www.w3.org/2001/XMLSchema-datatypes'
NAMESPACES = {
    'a': 'http://relaxng.org/ns/compatibility/annotations/1.0',
    'xml': 'http://www.w3.org/XML/1998/namespace',
}

class XMLSerializer(object):

    def __init__(self, indent=None):
        self.indent = indent or '  '
        self.reset()

    def reset(self):
        self.buf = []
        self.needs = {}
        self.ns = {}
        self.default = ''
        self.level = 0

    def write(self, s):
        self.buf.append(self.indent * self.level + s)

    def namespace(self, ns):
        assert ns in self.ns or ns in NAMESPACES, ns
        if ns not in self.ns:
            self.ns[ns] = NAMESPACES[ns]
        return self.ns[ns]

    def toxml(self, node):

        self.reset()
        types = None
        for n in node.value:
            if n.type == DATATYPES:
                types = n.value[0].strip('"')
            elif n.type == DEFAULT_NS:
                self.default = n.value[0].strip('"')
                if n.name is not None:
                    self.ns[n.name] = n.value[0].strip(' "')
            elif n.type == NS:
                self.ns[n.name] = n.value[0].strip(' "')

        prelude = ['<?xml version="1.0" encoding="UTF-8"?>']
        prelude.append('<grammar xmlns="http://relaxng.org/ns/structure/1.0"')
        if self.default:
            prelude.append('         ns="%s"' % self.default)

        self.visit(node.value)
        for ns, url in sorted(self.ns.items()):
            prelude.append('         xmlns:%s="%s"' % (ns, url))
        if types is not None or self.needs.get('types'):
            url = types if types is not None else TYPELIB_NS
            prelude.append('         datatypeLibrary="%s"' % url)

        prelude[-1] = prelude[-1] + '>'
        self.write('</grammar>')
        return '\n'.join(prelude + self.buf)

    def visit(self, nodes, indent=True):
        if indent:
            self.level += 1
        for x in nodes:
            if not isinstance(x, parser.Node):
                raise TypeError("Not a Node: " + repr(x))
            elif x.type in set([DATATYPES, DEFAULT_NS, NS]):
                continue
            elif x.type == DEFINE:
                if x.name == 'start':
                    self.write('<start>')
                else:
                    self.write('<define name="%s">' % x.name)
                self.visit(x.value)
                if x.name == 'start':
                    self.write('</start>')
                else:
                    self.write('</define>')
            elif x.type in set([MAYBE, SOME, ANY]):
                self.write('<%s>' % QUANTS[x.type])
                self.visit(x.value)
                self.write('</%s>' % QUANTS[x.type])
            elif x.type in set([INTERLEAVE, CHOICE, MIXED, LIST, DIV]):
                self.write('<%s>' % x.type.lower())
                self.visit(x.value)
                self.write('</%s>' % x.type.lower())
            elif x.type == EXCEPT:
                self.write('<except>')
                self.visit(x.value)
                self.write('</except>')
            elif x.type == NAME:
                if not x.value and '*' in x.name:
                    if x.name == '*':
                        self.write('<anyName/>')
                    else:
                        uri = self.ns[x.name.split(':', 1)[0]]
                        self.write('<nsName ns="%s"/>' % uri)
                elif x.value:
                    if x.name == '*':
                        self.write('<anyName>')
                    else:
                        uri = self.ns[x.name.split(':', 1)[0]]
                        self.write('<nsName ns="%s">' % uri)
                    self.visit(x.value)
                    if x.name == '*':
                        self.write('</anyName>')
                    else:
                        self.write('</nsName>')
                else:
                    ns, name = self.default, x.name
                    if ':' in x.name:
                        parts = x.name.split(':', 1)
                        ns = self.namespace(parts[0])
                        name = parts[1]
                    self.write('<name ns="%s">%s</name>' % (ns, name))
            elif x.type in set([REF, PARENT]):
                self.write('<%s name="%s"/>' % (x.type.lower(), x.name))
            elif x.type == LITERAL:
                self.write('<value>%s</value>' % x.name)
                self.visit(x.value, False)
            elif x.type == ANNOTATION:

                params, literals, rest = [], [], []
                for n in x.value:
                    if n.type == PARAM:
                        params.append('%s="%s"' % (n.name, n.value[0]))
                    elif n.type == LITERAL:
                        literals.append(n.name)
                    else:
                        rest.append(n)

                inter = ' ' if params else ''
                end = '/' if not (literals or rest) else ''
                tail = ''
                if literals and not rest:
                    tail = ''.join(literals) + '</%s>' % x.name

                bits = x.name, inter, ' '.join(params), end, tail
                self.write('<%s%s%s%s>%s' % bits)
                if tail:
                    continue

                for n in x.value:
                    if n.type == PARAM:
                        continue
                    elif n.type == LITERAL:
                        self.level += 1
                        self.write(n.name)
                        self.level -= 1
                    else:
                        self.visit([n])

            elif x.type == DOCUMENTATION:
                self.namespace('a')
                fmt = '<a:documentation>%s</a:documentation>'
                self.write(fmt % x.name[2:].strip())
            elif x.type == GROUP:
                self.visit(x.value, False)
            elif x.type in set([TEXT, EMPTY, NOTALLOWED]):
                self.write('<%s/>' % x.type.lower())
            elif x.type == SEQ:
                self.visit(x.value, False)
            elif x.type == DATATAG:
                self.needs['types'] = True
                if not x.value: # no parameters
                    self.write('<data type="%s"/>' % x.name)
                else:
                    name = x.name
                    if name not in ('string', 'token'):
                        name = x.name.split(':', 1)[1]
                    self.write('<data type="%s">' % name)
                    self.visit(x.value)
                    self.write('</data>')
            elif x.type == PARAM:
                bits = x.name, x.value[0]
                self.write('<param name="%s">%s</param>' % bits)
            elif x.type == ELEM:
                self.write('<element>')
                self.visit(x.value)
                self.write('</element>')
            elif x.type == ATTR:
                self.write('<attribute>')
                self.visit(x.value)
                self.write('</attribute>')
            elif x.type == ROOT:
                src = XMLSerializer(self.indent).toxml(x)
                for ln in src.splitlines()[1:]:
                    self.write(ln)
            else:
                assert False, x
        if indent:
            self.level -= 1
