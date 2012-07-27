# Written by Nick Rusnov <rusnovn@gmail.com>

import re
import string
import sys
from cStringIO import StringIO

DEBUG=True

def urlsafe(url):
    """Simple little thing to prevent badness in urls:
    Don't want to mess with prequoted URLs though, no to urllib.quote.
    We can stick all the badness preventing transforms here."""
    return url.translate(string.maketrans(" \t\"'","++++"),'\n\r')

urlmatch = re.compile('^(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+(:[0-9]+)?\/|\/([\w#!:.?+=&%@!\-\/]))?')

WHAT_PUSH = 0 # please push my tag name into the list
WHAT_CONT = 1 # just continue, one-off
WHAT_ENCL = 2 # please give me the enclosure once you hit my end tag (only for IMG, URL right now)
WHAT_DUMP = 3 # there was an error in my definition so just dump it into the output stream

(ST_START, ST_BEGIN_TAG, ST_COLLECT_TAG, ST_COLLECT_OPT, ST_CR, ST_P, ST_BEGIN_SMILE, ST_COLLECT_SMILE) = range(8)

alphanum = string.ascii_letters + string.digits
smile_forbidden = '\n\t \r[]<>&'

# this is really just for debugging purposes, but we can gradually migrate the buffer swapping and such
# needed to support ENCL to here.
class PPStateMachine:
    def __init__(self):
        self.inited = False
        self.tagcollection = None
        self.Reset()
        self.inited = True
    def Reset(self):
        self.inited and DEBUG and sys.stderr.write("** RESET %s %s %s\n" % (self.tagcollection.getvalue(), self.tagname, self.optvalue))
        self.state = ST_START
        val = None
        if self.tagcollection:
            val = self.tagcollection.getvalue()
        self.tagcollection = StringIO()
        self.tagname = ''
        self.optvalue = ''
        return val

    def ChangeState(self, state):
        DEBUG and sys.stderr.write("** CHANGE STATE: %d\n" % state)
        self.state = state
    def State(self):
        return self.state

class PPTag:
    def __init__(self, tag):
        self._tag = tag

    def getTag(self):
        return self._tag

    def getSpec(self):
        start = None
        end = None
        keys = dir(self)
        if 'start' in keys:
            start = self.start

        if 'end' in keys:
            end = self.end

        if self.__dict__.has_key('spec'):
            start,end = self.__dict__['spec']

        return (start, end)


class PPEasyTag(PPTag):
    def __init__(self, bbtag, htmltag):
        PPTag.__init__(self, bbtag)
        self.htmltag = htmltag

    def start(self, option):
        return WHAT_PUSH, "<%s>" % self.htmltag
    def end(self):
        return "</%s>" % self.htmltag

class PPSizeTag(PPTag):
    def __init__(self):
        PPTag.__init__(self, 'size')

    def start(self, option):
        return WHAT_PUSH, "<span style='size: %s'>" % option
    def end(self):
        return "</span>"

class PPQuoteTag(PPTag):
    def __init__(self, quoteeclass='quotee', quoteclass='quote'):
        PPTag.__init__(self, 'quote')
        self.quoteeclass = quoteeclass
        self.quoteclass = quoteclass

    def start(self, option):
        return WHAT_PUSH, """<span class="%s">%s</span><blockquote class="%s">""" % (self.quoteeclass, option, self.quoteclass)
    def end(self):
        return "</blockquote>"

# to properly support [code], we need ENCL to work so that stuff comes through unmolested
class PPCodeTag(PPTag):
    def __init__(self, codeclass="code"):
        PPTag.__init__(self, 'code')
        self.codeclass = codeclass
    def start(self, option):
        return WHAT_PUSH, """<code class="%s">""" % self.codeclass
    def end(self):
        return "</code>"

class PPColorTag(PPTag):
    def __init__(self):
        PPTag.__init__(self, 'color')
        self.colors = ['aqua', 'black', 'blue','fuchia','gray','green','lime','maroon','navy','olive','purple','red','silver','teal','white','yellow']
        self.color_re = re.compile('^#([A-Fa-f0-9][A-Fa-f0-9][A-Fa-f0-9]){1,2}$')

    def start(self, option):
        if not (self.color_re.match(option) or option in self.colors):
            return WHAT_DUMP,''
        return WHAT_PUSH, """<span style="color: %s">""" % option

    def end(self):
        return "</span>"

class PPImgTag(PPTag):
    def __init__(self):
        PPTag.__init__(self, 'img')

    # to support the normal form of [img] we need ENCL to work.
    def start(self, option):
        option = urlsafe(option)
        if not (urlmatch.match(option)):
            return WHAT_DUMP, ''
        return WHAT_CONT, """<img src="%s" />""" % option

class PPURLTag(PPTag):
    def __init__(self):
        PPTag.__init__(self, 'url')

    # to support the lazy form of [url] we need ENCL to work.
    def start(self, option):
        option = urlsafe(option)
        if not (urlmatch.match(option)):
            return WHAT_DUMP, ''
        return WHAT_PUSH, """<a href="%s">""" % option
    def end(self):
        return "</a>"


class PPDecode:
     # stub, replace with hashtree
    def handle_smile(self, smile):
        if smile == ':smile:':
            return WHAT_CONT, ':-)'
        return WHAT_DUMP, ''


    tagHandlers = [
        PPSizeTag(),
        PPQuoteTag(),
        PPCodeTag(),
        PPColorTag(),
        PPImgTag(),
        PPURLTag(),
        PPEasyTag('b','strong'),
        PPEasyTag('i','em'),
        PPEasyTag('u','u'),
        PPEasyTag('tt','tt'),
        PPEasyTag('list','ul'),
        PPEasyTag('li','li'),
        PPEasyTag('table','table'),
        PPEasyTag('tr','tr'),
        PPEasyTag('td','td'),
        PPEasyTag('tablerow','tr'),
        PPEasyTag('tablecell','td'),
        PPEasyTag('center','div align="center"'),
        PPEasyTag('right','div style="text-align: right"'),
        PPEasyTag('left','div style="text-align: left"')
        ]

    tagMap = dict()

    outp = None
    penstack = []

    def __init__(self):
        # load easy tags
        for i in self.tagHandlers:
            self.tagMap[i.getTag()] = i.getSpec()

    def tagdone(self, st, ch):
        st.tagcollection.write(ch)
        tag = st.tagname.lower()
        if tag[0] == '/':
            # seek the opening
            found = -1
            rg = range(len(self.penstack))
            rg.reverse()
            for tg in rg:
                if self.penstack[tg][0] == tag[1:]:
                    DEBUG and sys.stderr.write("end tag at %d\n" % tg)
                    # found it
                    found = tg
            if found == -1:
                #fail
                # if no opening, push the tagcollection back into the output
                self.outp.write(st.tagcollection.getvalue()) # fixme, reroll
            else:
                repush = list()
                # if opening, pop each item before the opening
                frontpens = [(x, self.tagMap[x[0]]) for x in self.penstack[found+1:]]
                frontpens.reverse()
                for tg in frontpens:
                    self.outp.write(tg[1][1]())
                # pop current tag
                self.outp.write(self.tagMap[tag[1:]][1]())
                if DEBUG:
                    sys.stderr.write(str(self.penstack))
                    sys.stderr.write('\n')
                    sys.stderr.write(str(found))
                    sys.stderr.write('\n')
                self.penstack.__delitem__(found)
                if DEBUG:
                    sys.stderr.write(str(self.penstack))
                    sys.stderr.write('\n')
                    sys.stderr.write("****\n")
                # push each tag back in
                frontpens.reverse()
                for tg in frontpens:
                    self.outp.write(tg[1][0](tg[0][1])[1])

        else:
            if self.tagMap.has_key(tag):
                dispos, outv = self.tagMap[tag][0](st.optvalue)
                if dispos == WHAT_DUMP:
                    self.outp.write(st.tagcollection.getvalue()) # fixme, rewroll
                    st.Reset()
                elif dispos in (WHAT_PUSH, WHAT_CONT):
                    self.outp.write(outv)
                    if dispos == WHAT_PUSH:
                        self.penstack.append((tag, st.optvalue))
            else:
                self.outp.write(st.tagcollection.getvalue()) # fixme, reroll

    def handle_starts(self, st, ch):
        if ch == '[':
            st.Reset()
            st.ChangeState(ST_BEGIN_TAG)
            st.tagcollection.write(ch)
        elif ch == ':':
            st.Reset()
            st.ChangeState(ST_BEGIN_SMILE)
            st.tagcollection.write(ch)
            st.tagname += ch
        # we replace <, > and & with entities
        elif ch == '&':
            self.outp.write('&amp;')
        elif ch == '<':
            self.outp.write('&lt;')
        elif ch == '>':
            self.outp.write('&gt;')
        elif ch == '\n':
            st.ChangeState(ST_CR)
        else:
            self.outp.write(ch)

    def rebuffer(self, st):
        # we'll just go ahead and chop off the already processed stuff.
        self.buffer = st + self.buffer[self.chn:]
        self.chn = 0

    def decode(self,s):
        st = PPStateMachine()
        self.outp = StringIO()
        self.buffer = s
        self.penstack = []
        self.chn = 0
        while (self.chn < len(self.buffer)):
            ch = self.buffer[self.chn]
            state = st.State()
            if state == ST_START:
                self.handle_starts(st, ch)
            elif state == ST_CR:
                if ch == '\n':
                    st.ChangeState(ST_P)
                else:
                    self.outp.write('<br />\n')
                    st.ChangeState(ST_START)
                    self.handle_starts(st, ch)
            elif state == ST_P:
                if ch == '\n':
                    continue
                else:
                    self.outp.write('</p>\n<p>')
                    st.ChangeState(ST_START)
                    self.handle_starts(st, ch)
            elif state == ST_BEGIN_TAG:
                if ch == '[':
                    self.outp.write('[')
                    buf = st.Reset() # back in start state
                    self.rebuffer(buf)

                elif ch in (']', '='):
                    self.outp.write(st.tagcollection.getvalue()) # fixme reroll
                    st.Reset()
                elif ch == '/':
                    # close tag, we stay in this state so that it gets dumped if we never get other characters
                    st.tagname += ch
                    st.tagcollection.write(ch)
                elif ch in alphanum:
                    st.ChangeState(ST_COLLECT_TAG)
                    st.tagname += ch
                    st.tagcollection.write(ch)
                else:
                    self.outp.write(st.tagcollection.getvalue())
                    st.Reset()
                    self.handle_starts(st, ch)

            elif state == ST_COLLECT_TAG:
                if ch == '[':
                    self.outp.write(st.tagcollection.getvalue())
                    st.Reset()
                    st.ChangeState(ST_BEGIN_TAG)
                    st.tagcollection.write('[')
                elif ch == ']':
                    self.tagdone(st, ch)
                    st.Reset()
                elif ch == '=':
                    if st.tagname[0] == '/':
                        self.outp.write(st.tagcollection + ch)
                        st.Reset()
                    else:
                        st.ChangeState(ST_COLLECT_OPT)
                        st.tagcollection.write(ch)
                elif not ch in alphanum:
                    self.outp.write(st.tagcollection.getvalue()) # fixme reroll
                    st.ChangeState(ST_START)
                    st.Reset()
                    self.handle_starts(st, ch)
                else:
                    st.tagcollection.write(ch)
                    st.tagname += ch
            elif state == ST_COLLECT_OPT:
                if ch == ']':
                    self.tagdone(st, ch)
                    st.Reset()
                elif ch == '[':
                    self.outp.write(st.tagcollection.getvalue()) # fixme reroll
                    st.Reset()
                    st.ChangeState(ST_BEGIN_TAG)
                    st.tagcollection.write('[')
                else:
                    st.optvalue += ch
                    st.tagcollection.write(ch)
            elif state == ST_BEGIN_SMILE:
                if ch in smile_forbidden + ':':
                    self.outp.write(st.tagcollection.getvalue()) # fixme reroll
                    st.Reset()
                    self.handle_starts(st, ch)
                else:
                    st.tagname += ch
                    st.tagcollection.write(ch)
                    st.ChangeState(ST_COLLECT_SMILE)
            elif state == ST_COLLECT_SMILE:
                if ch in smile_forbidden:
                    self.outp.write(st.tagcollection.getvalue()) # fixme reroll
                    st.Reset()
                    self.handle_starts(st, ch)
                elif ch == ':':
                    st.tagcollection.write(ch)
                    st.tagname += ch
                    dispos, outv = self.handle_smile(st.tagname.lower())
                    if dispos == WHAT_DUMP:
                        self.outp.write(st.tagcollection.getvalue()) # fixme reroll
                    else:
                        self.outp.write(outv)
                    st.Reset()
                else:
                    st.tagcollection.write(ch)
                    st.tagname += ch
            self.chn += 1
        if st.State() != ST_START:
            self.outp.write(st.tagcollection.getvalue()) # fixme reroll

        if self.penstack:
            self.penstack.reverse()
            for pen in self.penstack:
                self.outp.write(self.tagMap[pen[0]][1]())
        outs = "<p>"+self.outp.getvalue()+"</p>"
        self.outp.close()
        return outs

