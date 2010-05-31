#!/usr/bin/env python


import sys
import os
import socket
import select
import string
import traceback
import urllib
import time

import msnlib
import msncb
import re
import json
import urllib

from optparse import OptionParser


"""
MSN Client

This is a fully usable msn client, which also serves as reference
implementation for msnlib-based code.
For further information refer to the documentation or the source (which is
always preferred).
Please direct any comments to albertito@blitiri.com.ar.
You can find more information, and the package itself, at
http://blitiri.com.ar/p/msnlib/
"""


#
# constant strings
#

help = """\
Command list:
status [mode]   Shows the current status, or changes it to "mode", which can
        be one of: online away busy brb phone lunch invisible idle
q       Quits the program
w       Prints your entire contact list
ww      Prints your entire contact list, including email addresses
wn      Prints your entire contact list, including real nicks
wr      Prints your reverse contact list
wd      Prints the differences between your forward and reverse lists
e       Prints your online contacts
ee      Prints your online contacts, including email addresses
eg      Prints your online contacts with the groups
en      Prints your online contacts, including real nicks
h       Shows your incoming message history
add e [n] [g]   Adds the user "e" with the nick "n" to the group "g"
del nick    Deletes the user with nick "nick"
ren nick new    Renames the user with nick "nick" to appear as "new"
lignore [nick]  Locally ignores the user, or display the locally ignored users
lunignore nick  Removes a user from the locally ignored users list
block nick  Blocks a user
unblock nick    Unblocks a blocked user
g       Shows the group list
gadd gname  Adds the group "gname"
gdel gname  Deletes the group "gname". Note that all the users in the
        group will be deleted too.
gren old new    Renames the group "old" with the name "new"
color [theme]   Shows or set the color theme to "theme"
close nick  Closes the switchboard connection with "nick"
config      Shows the configuration
info [nick] Shows the user information and pending messages (if any),
        or our personal info
nick [newnick]  Changes your nick to "newnick" or shows own nick
privacy p a Sets whether accept messages from people not on your list (p)
        and require authorization (a)
m nick text Sends a message to "nick" with the "text"
a text      Sends a message to the last person you sent a message to
r text      Sends a message to the last person that sent you a message
invite u1 to u2 Invites u1 into the chat with u2

In most cases, where you are asked for a nick, you can alternatively enter the
email.  This makes it easier to handle people with weird or long nicks.
"""


#
# colors, for nice output
#

class color_default:
    def __init__(self):
        self.name = 'default'
        self.black =    '\x1b[0;30m'
        self.red =  '\x1b[0;31m'
        self.green =    '\x1b[0;32m'
        self.yellow =   '\x1b[0;33m'
        self.blue = '\x1b[0;34m'
        self.magenta =  '\x1b[0;35m'
        self.cyan = '\x1b[0;36m'
        self.white =    '\x1b[0;37m'
        self.normal =   '\x1b[0m'
        self.bold = '\x1b[1m'
        self.clear =    '\x1b[J'

class color_bw:
    def __init__(self):
        self.name = 'bw'
        self.black =    '\x1b[0;30m'
        self.red =  '\x1b[0m'
        self.green =    '\x1b[0m'
        self.yellow =   '\x1b[0m'
        self.blue = '\x1b[0m'
        self.magenta =  '\x1b[0m'
        self.cyan = '\x1b[0m'
        self.white =    '\x1b[0m'
        self.normal =   '\x1b[0m'
        self.bold = '\x1b[0m'
        self.clear =    '\x1b[J'

color_classes = {
    'default':  color_default,
    'bw':       color_bw
}
c = color_classes['default']()


# command list for tab-completion purposes
command_list = [ 'a', 'add', 'block', 'close', 'color', 'config', 'del', 'e',
    'ee', 'eg', 'en', 'g', 'gadd', 'gdel', 'green', 'h', 'help', 'info',
    'invite', 'lignore', 'luignore', 'm', 'nick', 'privacy', 'q', 'r',
    'ren', 'status', 'unblock', 'w', 'wn', 'wd', 'wr', 'ww' ]


# add by zhangwj
def handle_msg(email, line):
    """handle the msg"""
    global options
    
    pid = os.fork()
    if pid == -1:
        return -1
    elif pid > 0:
        return 1
    else:
        os.system(options.file + ' ' + email + ' ' + urllib.quote(json.dumps(line)))
        sys.exit()

def runAsDaemon():
    pid = os.fork()
    if pid == -1:
        return -1
    elif pid > 0:
        sys.exit()
    else:
        if os.setsid() == -1 :
            return -1

#
# different useful prints
#

def printl(line, color = c.normal, bold = 0):
    "Prints a line with a color"
    out = ''
    if line and line[0] == '\r':
        clear_line()
    if bold:
        out = c.bold
    out = color + out + line + c.normal
    safe_write(out)
    safe_flush()

def perror(line):
    "Prints an error"
    out = ''
    out += c.yellow + c.bold + '!' + c.normal
    out += c.red + c.bold + '!' + c.normal
    out += c.blue + c.bold + '!' + c.normal
    out += ' ' + c.green + c.bold + line + c.normal + '\a'
    safe_write(out)
    safe_flush()

def pexc(line):
    "Prints an exception"
    out = '\n'
    out += ( c.cyan + c.bold + '!' + c.normal ) * 3
    safe_write(out)
    safe_write(c.bold + line)
    safe_flush()
    traceback.print_exc()
    safe_write(c.normal)
    safe_write('\n')
    safe_flush()

def print_list(md, only_online = 0, userlist = None, include_emails = 0,
        include_realnicks = 0):
    "Prints the user list"
    if not userlist:
        userlist = md.users
    ul = userlist.keys()
    ul.sort()
    for email in ul:
        u = userlist[email]
        if u.status != 'FLN':
            hl = 1
        else:
            if only_online: continue
            hl = 0
        status = msnlib.reverse_status[u.status]
        printl('%7.7s :: %s' % (status, u.nick), bold = hl)
        if include_emails:
            printl(' (%s)' % (email), bold = hl)
        if include_realnicks:
            printl(' (%s)' % (u.realnick), bold = hl)
        if 'B' in u.lists:
            printl(' [!]')
        if email not in md.reverse.keys():
            printl(' [X]')
        printl('\n')

def print_diff(md):
    "Prints the differences between forward and reverse lists"
    fwdl = md.users.keys()
    fwdl.sort()

    revl = md.reverse.keys()
    revl.sort()

    printl("People you have that don't have you:\n", bold = 1)
    for email in fwdl:
        if email not in revl:
            user = md.users[email]
            printl("    %s (%s)\n" % (user.nick, email))
    printl('\n')

    printl("People you don't have that have you:\n", bold = 1)
    for email in revl:
        if email not in fwdl:
            user = md.reverse[email]
            printl("    %s (%s)\n" % (user.nick, email))

def print_group_list(md):
    "Prints the group list"
    gids = md.groups.keys()
    gids.sort()
    for gid in gids:
        printl('%3.3s :: %s\n' % (gid, md.groups[gid]))

def print_grouped_list(md, only_online = 0, include_emails = 0):
    db = {}
    for gid in md.groups.keys():
        db[gid] = []
    for gid in md.groups.keys():
        for e in md.users.keys():
            if md.users[e].gid == gid:
                db[gid].append(e)
    gids = db.keys()
    gids.sort()
    for gid in gids:
        printl(':: %s ::\n' % md.groups[gid], bold = 1)
        ul = db[gid]
        ul.sort()
        for email in ul:
            u = m.users[email]
            if u.status != 'FLN':
                hl = 1
            else:
                if only_online: continue
                hl = 0
            status = msnlib.reverse_status[u.status]
            printl('\t%7.7s :: %s' % (status, u.nick), bold = hl)
            if include_emails:
                printl(' (%s)' % (email), bold = hl)
            if 'B' in u.lists:
                printl(' [!]')
            if email not in md.reverse.keys():
                printl(' [X]')
            printl('\n')

def print_user_info(email):
    "Prints the user information, and pending messages"
    u = m.users[email]
    out = c.bold
    out += c.bold + 'User info for ' + email + '\n'
    out += c.bold + 'Nick:\t\t' + c.normal + u.nick + '\n'
    out += c.bold + 'Status:\t\t' + c.normal + msnlib.reverse_status[u.status] + '\n'
    if 'B' in u.lists:
        out += c.bold + 'Mode:\t\t' + c.normal + 'blocked' + '\n'
    if u.gid != None:
        out += c.bold + 'Group:\t\t' + c.normal + m.groups[u.gid] + '\n'
    if u.realnick:
        out += c.bold + 'Real Nick:\t' + c.normal + u.realnick + '\n'
    if u.homep:
        out += c.bold + 'Home phone:\t' + c.normal + u.homep + '\n'
    if u.workp:
        out += c.bold + 'Work phone:\t' + c.normal + u.workp + '\n'
    if u.mobilep:
        out += c.bold + 'Mobile phone:\t' + c.normal + u.mobilep + '\n'
    if u.priv.has_key('typing') and u.priv['typing']:
        out += c.bold + 'Last typing at:\t' + c.normal
        out += time.asctime(time.localtime(u.priv['typing'])) + '\n'
    if u.sbd:
        out += c.bold + 'Switchboard:\t' + c.normal + str(u.sbd) + '\n'
        if u.sbd.msgqueue:
            out += c.bold + 'Pending messages:' + '\n'
            for msg in u.sbd.msgqueue:
                out += c.bold + '\t>>> ' + c.normal + msg + '\n'
    printl(out)

def print_prompt():
    "Prints the user prompt"
    # safe_write('\r' + c.red + c.bold + '[msn] ' + c.normal)
    # safe_flush()
    pass

def print_inc_msg(email, lines, eoh = 0, quiet = 0, ptime = 1, recvtime = 0):
    """Prints an incoming message from a list of lines and an optional
    end-of-header pointer.  You can also pass the original received time as
    a parameter, this is used for history printed."""
    nick = email2nick(email)
    if not nick: nick = email
    if email in ignored:
        return
    if ptime:
        if recvtime:
            ctime = time.strftime('%I:%M:%S%p', time.localtime(recvtime))
        else:
            ctime = time.strftime('%I:%M:%S%p', now())
        printl('%s ' % ctime, c.blue)
    printl('%s' % nick, c.cyan, 1)
    if len(lines[eoh:]) == 1:
        printl(' <<< %s\n' % lines[eoh], c.yellow, 1)
    else:
        printl(' <<< \n\t', c.yellow, 1)
        msg = string.join(lines[eoh:], '\n\t')
        msg = msg.replace('\r', '')
        printl(msg + '\n', c.bold)
    beep(quiet)

def print_out_msg(nick, msg):
    "Prints an outgoing message"
    ctime = time.strftime('%I:%M:%S%p', now())
    printl('%s ' % ctime, c.blue)
    printl('%s' % nick, c.cyan, 1)
    printl(' >>> ', c.yellow, 1)
    printl('%s' % msg)


def beep(q = 0):
    "Beeps unless it's told to be quiet"
    if not q:
        printl('\a')


def safe_flush():
    """Safely flushes stdout. It fixes a strange issue with flush and
    nonblocking io, when flushing too fast."""
    c = 0
    while c < 100:
        try:
            sys.stdout.flush()
            return
        except IOError:
            c +=1
            time.sleep(0.01 * c)
    raise Exception, 'flushed too many times, giving up. Please report!'

def safe_write(text):
    """Safely writes to stdout. It fixes the same issue that safe_flush,
    that is, writing too fast raises errors due to nonblocking fd."""
    text = re.sub(r'\x1b\[[^m|J]+[m|J]', '', text)
    if len(text) == 0:
        return
    c = 1
    while c:
        try:
            sys.stdout.write(text)
            return
        except IOError:
            c += 1
            time.sleep(0.01 * c)
    raise Exception, 'wrote too many times, giving up. Please report!'


#
# useful functions
#

def quit(code = 0):
    "Exits"
    printl('Closing\n', c.green, 1)
    try:
        try:
            m.disconnect()
        except:
            pass
        global oldtermattr
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSAFLUSH, oldtermattr)
    except:
        pass
    sys.exit(code)

def nick2email(nick):
    "Returns an email according to the given nick, or None if noone matches"
    for email in m.users.keys():
        if m.users[email].nick == nick:
            return email
    if nick in m.users.keys():
        return nick
    return None

def email2nick(email):
    "Returns a nick accoriding to the given email, or None if noone matches"
    if email in m.users.keys():
        return m.users[email].nick
    else:
        return None

def findemailnick(email, begin):
    """Check if the email/nick of the given user begins with the given
    beginning. Returns 1 if it matches the nick, or 2 if it matches the
    email."""
    if m.users[email].nick.find(begin) == 0:
        return 1
    elif email.find(begin) == 0:
        return 2
    return 0

# global variable for matchemail()
start_from = 0
def matchemail(begin, only_online = 0, start = 0):
    """"Returns a matching email/nick for the given beginning; it avoids
    beginnings with spaces. If only_online is equal to 1 searchs only for
    not offline users or users with an sbd.  If start=1 it iterates the
    last match and do a cyclical search."""

    global start_from

    if ' ' in begin:
        return None

    emails = m.users.keys()

    if start_from >= len(emails):
        # the list has changed while iterating, reset
        start_from = 0

    if start:
        pos = (start_from + 1) % len(emails)
    else:
        pos = start_from

    found = 0
    while not found:
        # we made a complete loop without matches
        if start and pos == start_from:
            break
        elif pos == (start_from - 1) % len(emails):
            break

        #msnlib.debug("l: %d %s\n" % (pos, emails[pos]))
        current = emails[pos]
        if only_online and m.users[current].status == 'FLN':
            pos = (pos + 1) % len(emails)
            continue
        if findemailnick(emails[pos], begin):
            found = 1
            break
        pos = (pos + 1) % len(emails)

    start_from = pos

    if found:
        if findemailnick(emails[pos], begin) == 1:
            # return the nick
            nick = email2nick(emails[pos])
            if ' ' in nick:
                return emails[pos]
            return nick
        else:
            return emails[pos]
    else:
        start_from = 0
        return None


def gname2gid(gname):
    "Returns a group name according to the given group id"
    for gid in m.groups.keys():
        if m.groups[gid] == gname:
            return gid
    return None

def get_config(file):
    "Parses a simple config file, and returns a var:value dict"
    try:
        fd = open(file)
    except:
        return None
    lines = fd.readlines()
    config = {}
    for i in lines:
        i = i.strip()
        if i.find('=') < 0:
            continue
        if i[0] == '#':
            continue
        var, value = i.split('=', 1)
        var = var.strip()
        value = value.strip()
        config[var] = value
    return config

def null(s):
    "Null function, useful to void debug ones"
    pass

def log_msg(email, type, msg, mtime = 0, users = []):
    """Logs the message or event of the 'type', related to 'email',
    with the content 'msg', to a file in the specified directory.  See
    documentation for more specific details, specially about
    formatting."""

    if not config['log history']:
        return

    if config['profile']:
        prepend = config['profile'] + '::'
    else:
        prepend = ''
    if users:
        # copy and sort the user list, so we log always to the same
        # file regarding the order the users were joined
        # FIXME: sometimes we crash because filename is too long
        usorted = users[:]
        usorted.sort()
        file = config['history directory'] + '/' + prepend + 'M::'
        file += string.join(usorted, ',')
    else:
        file = config['history directory'] + '/' + prepend + email
    if not mtime:
        mtime = time.time()
    out = ''
    out += time.strftime('%d/%b/%Y %H:%M:%S ', time.localtime(mtime))
    out += email + ' '
    if type == 'in':
        out += '<<< '
        msg = msg.replace('\r', '')
        lines = msg.split('\n')
        if len(lines) == 1:
             out += msg + '\n'
        else:
            out += '\n\t'
            out += string.join(lines[:], '\n\t')
            out += '\n'
    elif type == 'out':
        out += '>>> ' + msg + '\n'
    elif type == 'status':
        out += '*** ' + msg + '\n'
    elif type == 'multi':
        out += '+++ ' + msg + '\n'
    elif type == 'realnick':
        out += '--- ' + msg + '\n'

    fd = open(file, 'a')
    fd.write(out)
    fd.close()
    del(fd)
    return

def now():
    "Returns the current time, in tuple format"
    return time.localtime(time.time())


#
# terminal handling
#

# all this is _ugly_, a real mess; luckily it's pretty much self contained.
# if you're trying to follow the code, i highly recommend you to skip this
# section; you really don't need to know it, just think of redraw_cli() pretty
# much as print_prompt(), stdin_read() as sys.stdin.readline(), and
# clear_line() as printf('\r'). actually that's quite near true when we don't
# use termios.
# it has been written in a way that if termios is not available, we fall back
# to the normal and old behaviour which is guaranteed to work.

# try:
    # all of this disables line-buffering on the terminal (thus allowing
    # char-by-char reads) and echoing (so we output whatever we want); and
    # finally sets the file nonblocking so we can read all that's
    # available without complications.
    # you should read termios and fcntl manpages to find out the details
    # import termios
    # stdinfd = sys.stdin.fileno()
    # oldtermattr = termios.tcgetattr(stdinfd)
    # newtermattr = termios.tcgetattr(stdinfd)
    # newtermattr[3] = newtermattr[3] & ~termios.ICANON & ~termios.ECHO
    # termios.tcsetattr(stdinfd, termios.TCSANOW, newtermattr)
    # import fcntl, os
    # fcntl.fcntl(stdinfd, fcntl.F_SETFL, os.O_NONBLOCK)
    # del(newtermattr)
    # use_termios = 1
# except:
#     use_termios = 0
use_termios = 0

# now we try to find out the console size; if we fail we fall back to
# the good old 80x24.
# note that the (' ' * 10) is just awful, but there is no sane way of
# doing this without using a C module. it's based on 'struct winsize',
# but as we only use the first 4 bytes, we don't ask for more; then we
# unpack the two shorts into (lenght, width)
try:
    import struct
    winsize = fcntl.ioctl(stdinfd, termios.TIOCGWINSZ, ' ' * 10)
    winsize = struct.unpack('hh', winsize[:4])
except:
    winsize = (24, 80)
screenwidth = winsize[1]

# input buffer, where all the characters written by the user are stored in
inbuf = ''

# vars to control the tabs completions:
# match of commands
matchc_last = 0
matchc_status = 0
matchc_root = ''
# match of last send/received
matchl_status = 0
# match of m command
matchm_status = 0
matchm_root = ''
# match of others arguments
matchp_status = 0
matchp_root = ''

# input history buffer, to store previous commands.
# we use a list [buffer, pointer] to avoid namespace pollution
inbuf_history = [[], -1]

def stdin_read():
    """Reads from stdin, and acts in consecuense. If you don't use
    termios, it's almost the same as calling readline(); but otherwise it
    handles all the input reading."""
    global inbuf
    if not use_termios:
        inbuf = sys.stdin.readline()
        tmpbuf = inbuf
        inbuf = ''
        out = parse_cmd(tmpbuf)
        printl(out + '\n', c.green, 1)
        redraw_cli()
        return

    in_esc = 0
    input = sys.stdin.read()

    global matchc_last
    global matchc_status
    global matchc_root
    global matchl_status
    global matchm_status
    global matchm_root
    global matchp_status
    global matchp_root

    for char in input:
        # decrease the flag of the tab completion of commands
        if matchc_status != 0:
            matchc_status = matchc_status - 1
        # decrease the flag of the last received/last send completion
        elif matchl_status != 0:
            matchl_status = matchl_status - 1
        # decrease the flag of the m completion
        elif matchm_status != 0:
            matchm_status = matchm_status - 1
        # decrease the flag of the other arguments completion
        elif matchp_status != 0:
            matchp_status = matchp_status - 1

        if char == '\r':
            # replace \r with \n, so we handle mac keyboard input
            # properly (it breaks \r\n tho, but nobody uses it)
            char = '\n'
        inbuf = inbuf + char
        if char == '\n':
            # command history
            if len(inbuf_history[0]) > config['input history size']:
                del(inbuf_history[0][0])
            inbuf_history[0].append(inbuf[:-1])
            inbuf_history[1] = len(inbuf_history[0]) - 1 # moves the pointer

            safe_write(char)
            tmpbuf = inbuf
            inbuf = ''
            out = parse_cmd(tmpbuf)
            printl(out + '\n', c.green, 1)
            redraw_cli()

        elif char == '\b' or ord(char) == 127:      # ^H / DEL
            inbuf = inbuf[:-2]
            redraw_cli()

        elif ord(char) == 21:               # ^U
            inbuf = ''
            redraw_cli()

        elif ord(char) == 23:               # ^W
            inbuf = inbuf[:-1]
            inbuf = inbuf.rstrip()
            pos = inbuf.rfind(' ')
            if pos > 0:
                inbuf = inbuf[:pos].rstrip() + ' '
            else:
                inbuf = ''
            redraw_cli()

        elif char == '\t':              # tab
            p = inbuf.split()

            # we do a basic cycling between the last received and
            # last sent; first we build the two strings and then
            # we see which one applies according to some messy
            # logic
            # FIXME: it fails if we haven't in our contact list
            # the person with we are talking
            if email2nick(last_received):
                nick = email2nick(last_received)
                if ' ' in nick:
                    nick = last_received
                mtolrecv = 'm ' + nick + ' '
            else:
                mtolrecv = None

            if email2nick(last_sent):
                nick = email2nick(last_sent)
                if ' ' in nick:
                    nick = last_sent
                mtolsent = 'm ' + nick + ' '
            else:
                mtolsent = None

            # in an empty buffer we fill with the last received or
            # the last sent
            if len(p) == 0:
                if mtolsent:
                    inbuf = mtolsent
                    matchl_status = 2
                elif mtolrecv:
                    inbuf = mtolrecv
                    matchl_status = 2
                else:
                    inbuf = inbuf[:-1]
                    beep()

            # if in the last cycle we have replaced with
            # mtolsent or mtolrecv we try to fill ciclical
            elif mtolsent and mtolrecv and matchl_status == 1:
                if inbuf.strip() == mtolrecv.strip():
                    inbuf = mtolsent
                    matchl_status = 2
                else:
                    inbuf = mtolrecv
                    matchl_status = 2

            # temporarily if not mtolsent or mtolrecv we beep
            # FIXME it do nothing if there's only mtolrecv and
            # it changes between two tabs
            elif matchl_status == 1:
                # it avoids that in the next iteration the
                # empty buffer completion will be taked for
                # an m completion
                matchl_status = 2
                inbuf = inbuf[:-1]
                beep()

            # we have something that is neither mtolsent or
            # mtolrecv, if is the m command we try to find a
            # matching email/nick
            elif p[0] == 'm' and len(p) == 2:
                begin = p[1]
                if matchm_status == 1:
                    begin = matchm_root

                # we try to match with onlines contacts
                # and contacts with sbd
                email = matchemail(begin, 1, matchm_status)
                if not email:
                    inbuf = inbuf[:-1]
                    beep()
                else:
                    matchm_root = begin
                    matchm_status = 2
                    inbuf = 'm ' + email + ' '

            # if there's an only word buffer we try to match
            # with one of the commands
            elif len(p) == 1:
                # if it's the 2nd tab we build a ciclical
                # matching; if not, we remember the last match
                if matchc_status == 1:
                    p[0] = matchc_root
                    matchc_last = matchc_last + 1

                found = 1
                while found or matchc_last != len(command_list):
                    if matchc_last == len(command_list):
                        matchc_last = 0
                        found = 0
                        continue
                    elif command_list[matchc_last].find(p[0]) == 0:
                        matchc_status = 2
                        matchc_root = p[0]
                        break
                    matchc_last = matchc_last + 1
                if matchc_last == len(command_list):
                    inbuf = inbuf[:-1]
                    beep()
                else:
                    inbuf = command_list[matchc_last] + ' '

            else:
                pn = p[len(p) - 1]
                if matchp_status == 1:
                    pn = matchp_root

                # we try to match with all of contacts
                email = matchemail(pn, 0, matchp_status)
                if not email:
                    inbuf = inbuf[:-1]
                    beep()
                else:
                    matchp_root = pn
                    matchp_status = 2
                    inbuf = inbuf.rstrip()
                    pos = inbuf.rfind(' ')
                    inbuf = inbuf[:pos] + ' ' + email + ' '

            redraw_cli()

        elif ord(char) == 4:                # EOT
            safe_write('\n')
            out = parse_cmd('')
            printl(out + '\n', c.green, 1)

        elif ord(char) == 27:               # ESC
            # we use in_esc for escape secuenses (composed of
            # ESC + '[' + LETTER). 1 means got ESC, 2 means got
            # '['. Here we set to 1, and the rest are in the
            # generic handling
            in_esc = 1
            inbuf = inbuf[:-1]

        elif ord(char) < 32:                # unhandled control
            msnlib.debug('Got weird char: %d' % ord(char))
            redraw_cli_cond(char)

        else:                       # normal
            if not in_esc:
                # Never allow lines longer than 1500, since
                # that's the max for a single message.
                # Actually this calculates based on the whole
                # buffer and not on just the message, but the
                # code is nicer and 16 bytes won't make a
                # difference.
                if len(inbuf) > 1500:
                    inbuf = inbuf[:1500]
                    beep()
                    redraw_cli()
                else:
                    redraw_cli_cond(char)
                continue

            # comes from a escape code
            elif in_esc == 1:
                if char == '[':
                    in_esc = 2
                else:
                    in_esc = 0
                inbuf = inbuf[:-1]
            elif in_esc == 2:
                if char == 'A':         # up
                    if inbuf_history[1] == -1:
                        # hit the top, or it's empty;
                        # remove it from the buffer
                        inbuf = inbuf[:-1]
                    else:
                        clear_line()
                        pos = inbuf_history[1]
                        inbuf = inbuf_history[0][pos]
                        inbuf_history[1] -= 1
                        redraw_cli()
                elif char == 'B':       # down
                    if not inbuf_history[0]:
                        # it's empty, so we only
                        # remove it from the buffer
                        inbuf = inbuf[:-1]
                    elif inbuf_history[1] == len(inbuf_history[0]) - 1:
                        # hit the bottom, clear the buffer
                        clear_line()
                        inbuf = ''
                        redraw_cli()
                    else:
                        inbuf_history[1] += 1
                        clear_line()
                        pos = inbuf_history[1]
                        inbuf = inbuf_history[0][pos]
                        redraw_cli()
                else:               # unhandled esc
                    inbuf = inbuf[:-1]
                in_esc = 0

def redraw_cli():
    """Redraws the current prompt line, including user input; it first
    clears the line, either automatically or up to 'lenght' chars."""
    return ''
    global inbuf, screenwidth
    clear_line()
    print_prompt()
    lenght = screenwidth - 7    # we subsctract the prompt lenght + 1
    safe_write(inbuf[-lenght:])
    safe_flush()

def redraw_cli_cond(char):
    """Same as redraw_cli, but conditional over the lenght of stdin. That
    means that if inbuf is getting too big, we redraw; otherwise we just
    write the character. It's used mostly to avoid innecesary redraw
    overhead (it avoids 90% of cases)."""
    global inbuf, screenwidth
    if len(inbuf) >= (screenwidth - 7):
        redraw_cli()
    else:
        safe_write(char)
        safe_flush()

def clear_line():
    """Clears the current line by overwriting it with spaces."""
    global inbuf, screenwidth
    if use_termios:
        safe_write('\r' + (screenwidth - 1) * ' ' + '\r')


#
# stdin command parser
#

def parse_cmd(cmd):
    """Parses the commands introduced by the user. It's pretty long and
    boring, as expected."""

    global c, last_sent, last_received  # ugly but necesary

    if len(cmd) == 0:
        quit()
    elif len(cmd) == 1:
        return ''

    # cut trailing newline and clean up
    if cmd[-1] == '\n':
        cmd = cmd[:-1]
    cmd = cmd.lstrip()
    orig_cmd = cmd
    s = cmd.split()
    if len(s) > 1:
        cmd = s[0]
        # recover original params to preserve whitespace
        # use as index the first parameter to the command
        params = orig_cmd[orig_cmd.find(s[1]):]
    else:
        if not cmd: return ''
        cmd = s[0]
        params = ''


    # parse
    if   cmd == 'status':       # change status
        if not params:
            return 'Your current status is %s' % msnlib.reverse_status[m.status]
        if not m.change_status(params):
            out = 'Status must be one of:\n'
            out += '\tonline, away, busy, brb, phone, lunch, invisible or idle'
            return out
        return 'Status changed to: %s' % params

    elif cmd == 'q':        # quit
        quit()

    elif cmd == 'reload':       # reload callbacks
        reload(msncb)
        m.cb = msncb.cb()

    elif cmd == 'w':        # list
        print_grouped_list(m)

    elif cmd == 'ww':       # list, include emails
        print_grouped_list(m, include_emails = 1)

    elif cmd == 'wn':       # list, include real nicks
        print_list(m, include_realnicks = 1)

    elif cmd == 'wr':       # reverse list
        print_list(m, userlist = m.reverse, include_emails = 1)

    elif cmd == 'wd':       # difference list
        print_diff(m)

    elif cmd == 'e':        # list (online only)
        print_list(m, only_online = 1)

    elif cmd == 'eg':
        print_grouped_list(m, only_online = 1)

    elif cmd == 'ee':
        print_grouped_list(m, only_online = 1, include_emails = 1)

    elif cmd == 'en':
        print_list(m, only_online = 1, include_realnicks = 1)

    elif cmd == 'g':        # list groups
        print_group_list(m)

    elif cmd == 'raw':      # send a raw message
        try:
            cmd = params[0:3]
            pars = params[4:]
        except:
            return 'Error parsing command'
        m._send(cmd, pars)

    elif cmd == 'debug':        # enable/disable debugging
        p = params.split()
        if len(p) != 1:
            return 'Error parsing command'
        if p[0] == 'off':
            msnlib.debug = null
            msncb.debug = null
            return 'Debugging disabled'
        elif p[0] == 'on':
            reload(msnlib)
            reload(msncb)
            return 'Debugging enabled'
        else:
            return 'Unknown parameter - must be "on" or "off"'

    elif cmd == 'config':       # show config variables
        keys = config.keys()
        keys.sort()
        for var in keys:
            value = str(config[var])
            if var == 'password':
                value = '<not displayed>'
            printl(c.bold + var + ' = ' + c.normal + value + '\n')
        printl(c.bold + 'use_termios = ' + str(use_termios) + '\n')
        printl(c.bold + 'screensize = ' + str(winsize) + '\n')

    elif cmd == 'color':        # configure/show colors
        p = params.split()
        if len(p) != 1:
            printl(c.bold + "Currently using theme " + c.name + '\n')
            printl(c.bold + "Available themes:\n")
            for i in color_classes.keys():
                printl(c.bold + "\t* " + i + '\n')
        elif p[0] not in color_classes.keys():
            return "The specified theme is not available"
        else:
            c = color_classes[p[0]]()
            return "Changed theme to " + p[0]

    elif cmd == 'close':        # close a connection
        p = params.split()
        if len(p) != 1:
            return 'Error parsing command'
        email = nick2email(p[0])
        if not email:
            return 'Unknown nick (%s)' % p[0]
        if not m.users[email].sbd:
            return 'No socket opened for %s' % p[0]
        desc = str(m.users[email].sbd)
        m.close(m.users[email].sbd)
        return 'Closed socket %s' % desc

    elif cmd == 'privacy':      # set privacy mode
        p = params.split()
        if len(p) != 2:
            return 'Error parsing command'
        try:
            public = int(p[0])
            auth = int(p[1])
            if public not in (0, 1) or auth not in (0, 1):
                return 'Error: both parameters must be 1 or 0'
        except:
            return 'Error: both parameters must be 1 or 0'
        m.privacy(public, auth)

    elif cmd == 'lignore':      # ignore a user locally
        p = params.split()
        if len(p) == 0:
            printl(c.bold + 'Locally ignored users\n')
            for e in ignored:
                printl(email2nick(e) + ' (' + e + ')\n')
            return ''
        email = nick2email(p[0])
        if not email:
            return 'Unknown nick (%s)' % p[0]
        if email in ignored:
            return 'User is already being locally ignored'
        ignored.append(email)
        return 'User is now being locally ignored'

    elif cmd == 'lunignore':    # unignore a locally ignored user
        p = params.split()
        if len(p) == 0:
            return 'Error parsing command'
        email = nick2email(p[0])
        if email not in ignored:
            return 'User is not being locally ignored'
        ignored.remove(email)
        return 'User is no longer locally ignored'

    elif cmd == 'block':
        p = params.split()
        if len(p) == 0:
            return 'Error parsing command'
        email = nick2email(p[0])
        if not email:
            return 'Unknown nick (%s)' % p[0]
        m.userblock(email)
        return 'User %s blocked' % email

    elif cmd == 'unblock':
        p = params.split()
        if len(p) == 0:
            return 'Error parsing command'
        email = nick2email(p[0])
        if not email:
            return 'Unknown nick (%s)' % p[0]
        m.userunblock(email)
        return 'User %s unblocked' % email

    elif cmd == 'add':      # add a user
        p = params.split()
        if   len(p) == 0:
            return 'Error parsing command'
        elif len(p) == 1:
            email = nick = p[0]
            gid = '0'
        elif len(p) == 2:
            email = p[0]
            nick = p[1]
            gid = '0'
        else:
            email = p[0]
            nick = p[1]
            group = p[2]
            gid = gname2gid(group)
            if not gid: gid = group
            if gid not in m.groups.keys():
                return 'Unknown group'
        m.useradd(email, nick, gid)

    elif cmd == 'del':      # delete a user
        p = params.split()
        if len(p) != 1: return 'Error parsing command'
        email = nick2email(p[0])
        if not email:
            return 'Unknown nick (%s)' % p[0]
        m.userdel(email)

    elif cmd == 'ren':      # rename a user
        p = params.split(None, 1)
        if len(p) < 2: return 'Error parsing command'
        email = nick2email(p[0])
        if not email:
            return 'Unkown nick (%s)' % p[0]
        newnick = p[1].strip()
        u = m.users[email]
        m.userren(email, newnick)

    elif cmd == 'gadd':     # add a group
        p = params.split()
        if len(p) != 1: return 'Error parsing command'
        m.groupadd(p[0])

    elif cmd == 'gdel':     # delete a group
        p = params.split()
        if len(p) != 1: return 'Error parsing command'
        gname = p[0]
        gid = gname2gid(gname)
        if not gid: gid = gname
        if gid not in m.groups.keys():
            return 'Unknown group'
        for e in m.users.keys():
            u = m.users[e]
            if u.gid == gid:
                printl('User %s (%s) will be deleted\n' % \
                    (u.nick, e), bold = 1)
        m.groupdel(gid)

    elif cmd == 'gren':     # rename a group
        p = params.split()
        if len(p) != 2: return 'Error parsing command'
        newname = p[1]
        origname = p[0]
        gid = gname2gid(origname)
        if not gid: gid = origname
        if gid not in m.groups.keys():
            return 'Unknown group'
        m.groupren(gid, newname)

    elif cmd == 'invite':       # invite a user to an existing sbd
        p = params.split()
        if len(p) != 3: return 'Error parsing command'
        if p[1] != 'to': return 'Error parsing command'
        email = nick2email(p[0])
        if not email: email = p[0]
        dst = nick2email(p[2])
        if not dst: dst = p[2]
        for i in (email, dst):
            if i not in m.users.keys():
                return 'User %s unknown' % i
        dst_sbd = m.users[dst].sbd
        if not dst_sbd:
            return 'No current chat with user %s' % dst
        m.invite(email, dst_sbd)

    elif cmd == 'nick':     # show or change our nick
        if len(params) < 1:
            return "Your current nick is: %s" % m.nick
        nick = params
        m.change_nick(nick)

    elif cmd == 'info':     # user info
        p = params.split()
        if len(p) != 1:
            out = ''
            out += c.bold + 'Info for ' + m.email + '\n'
            out += c.bold + 'Nick:\t\t' + c.normal + m.nick + '\n'
            out += c.bold + 'Status:\t\t' \
                + c.normal + msnlib.reverse_status[m.status] + '\n'
            out += c.bold + 'Home phone:\t' + c.normal + str(m.homep) + '\n'
            out += c.bold + 'Work phone:\t' + c.normal + str(m.workp) + '\n'
            out += c.bold + 'Mobile phone:\t' + c.normal + str(m.mobilep) + '\n'
            out += c.bold + 'Users in contact list: ' + str(len(m.users)) + '\n'
            out += c.bold + 'Users in reverse list: ' + str(len(m.reverse)) + '\n'
            out += c.bold + 'Notification server: ' + c.normal + str(m) + '\n'
            if m.sb_fds:
                out += c.bold + 'Switchboard connections:\n'
                for i in m.sb_fds:
                    out += c.bold + '\tSB: ' + c.normal + str(i) + '\n'
            printl(out)
        else:
            email = nick2email(p[0])
            if not email:
                return 'Unknown nick (%s)' % str(p[0])
            print_user_info(email)

    elif cmd == 'sync':     # manual sync
        m.sync()

    elif cmd == 'h':        # show history
        printl('Incoming Message History (last %d messages)\n' \
            % config['history size'], c.green, 1)
        for i in history_ring:
            rtime = i[0]
            email = i[1]
            msg = i[2]
            print_inc_msg(email, msg, quiet = 1, ptime = 1, recvtime = rtime)

    # send a message
    elif cmd == 'm' or cmd == 'msg' or cmd == 'r' or cmd == 'a':
        if cmd == 'm' or cmd == 'msg':
            p = params.split()
            if len(p) < 1:
                return 'Please enter a nick and a message'
            nick = p[0]
            email = nick2email(nick)
            # begin the message content after the nick
            begin = len(nick + ' ')
            msg = params[begin:]
        elif cmd == 'r':
            email = last_received
            nick = email2nick(email)
            if not nick: nick = email
            msg = params
        elif cmd == 'a':
            email = last_sent
            nick = email2nick(email)
            if not nick: nick = email
            msg = params
        if not email:
            if cmd == 'a': return 'Please write a message first'
            if cmd == 'r': return 'Please reply a message first'
            else: return 'Unknown nick %s' % str(p[0])
        if m.users[email].status == 'FLN' and not m.users[email].sbd:
            return 'Unable to send message: User is offline'
        if (m.status == 'FLN' or m.status == 'HDN') and not m.users[email].sbd:
            return 'Unable to send message: Not allowed when offline'

        r = m.sendmsg(email, msg)
        last_sent = email
        if r == 1:
            return 'Message for %s queued for delivery' % nick
        elif r == 2:
            print_out_msg(nick, msg)
            if len(m.users[email].sbd.emails) > 1:
                log_msg(m.email, 'out', msg, \
                    users = m.users[email].sbd.emails)
            else:
                log_msg(email, 'out', msg)
        elif r == -2:
            return 'Message too big'
        else:
            return 'Error %d sending message' % r

    elif cmd == 'help' or cmd == '?':
        return help
    else:
        return 'Unknown command, type "help" for help'

    return ''



#
# This are the callback replacements, which only handle the output and then
# call the original callbacks to do the lower level stuff
#

# basic classes
m = msnlib.msnd()
m.cb = msncb.cb()

# status change
def cb_iln(md, type, tid, params):
    t = params.split(' ')
    status = msnlib.reverse_status[t[0]]
    email = t[1]
    rnick = urllib.unquote(t[2])
    nick = md.users[email].nick
    ctime = time.strftime('%I:%M:%S%p', now())

    printl('\r%s ' % ctime, c.blue)
    printl(nick, c.blue, 1)
    printl(' is ', c.magenta)
    printl('%s' % status, c.magenta, 1)
    log_msg(email, 'status', status)
    if config["show realnick changes"]:
        printl(' with realnick ', c.magenta)
        printl('%s' % rnick, c.magenta, 1)
        log_msg(email, 'realnick', rnick)
    printl('\n')

    msncb.cb_iln(md, type, tid, params)
m.cb.iln = cb_iln

def cb_nln(md, type, tid, params):
    status = msnlib.reverse_status[tid]
    t = params.split(' ')
    email = t[0]
    if len(params) > 1:
        rnick = urllib.unquote(t[1])
    else:
        rnick = ''

    nick = md.users[email].nick
    realnick = md.users[email].realnick
    ctime = time.strftime('%I:%M:%S%p', now())

    if tid != md.users[email].status:
        printl('\r%s ' % ctime, c.blue)
        printl(nick, c.blue, 1)
        printl(' changed status to ', c.magenta)
        printl('%s' % status, c.magenta, 1)
        log_msg(email, 'status', status)
        # if we don't know the realnick yet, include it in the same line
        if not realnick and config["show realnick changes"]:
            printl(' with realnick ', c.magenta)
            printl('%s' % rnick, c.magenta, 1)
            log_msg(email, 'realnick', rnick)
        printl("\n")

    if realnick and rnick and realnick != rnick \
            and config["show realnick changes"]:
        printl("\r%s " % ctime, c.blue)
        printl(nick, c.blue, 1)
        printl(' changed the realnick to ', c.magenta)
        printl('%s\n' % rnick, c.magenta, 1)
        log_msg(email, 'realnick', rnick)

    msncb.cb_nln(md, type, tid, params)
m.cb.nln = cb_nln

def cb_fln(md, type, tid, params):
    email = tid
    nick = md.users[email].nick
    ctime = time.strftime('%I:%M:%S%p', now())
    printl('\r%s ' % ctime, c.blue)
    printl(nick, c.blue, 1)
    printl(' disconnected\n', c.magenta)
    u = m.users[email]
    if u.sbd and u.sbd.msgqueue:
        printl(c.bold + "The following messages for " + nick + " will be discarded:\n")
        for msg in u.sbd.msgqueue:
            printl(c.bold + '\t>>> ' + c.normal + msg + '\n')
    log_msg(email, 'status', 'disconnect')
    msncb.cb_fln(md, type, tid, params)
m.cb.fln = cb_fln

# server disconnect
def cb_out(md, type, tid, params):
    printl('\rServer sent disconnect (probably you logged in somewhere else)\n', c.green, 1)
    msncb.cb_out(md, type, tid, params)
m.cb.out = cb_out

def cb_bye(md, type, tid, params, sbd):
    email = tid
    if email != sbd.emails[0]:
        nick = email2nick(email)
        if not nick: nick = email
        first_nick = email2nick(sbd.emails[0])
        if not first_nick: first_nick = sbd.emails[0]
        printl('\rUser %s left the chat with %s\n' % (nick, first_nick), c.green, 1)
        log_msg(email, 'multi', 'left', users = sbd.emails)
    msncb.cb_bye(md, type, tid, params, sbd)
m.cb.bye = cb_bye


# message
def cb_msg(md, type, tid, params, sbd):
    global last_received
    t = tid.split(' ')
    email = t[0]

    # parse
    lines = params.split('\n')
    headers = {}
    eoh = 0
    for i in lines:
        # end of headers
        if i == '\r':
            break
        tv = i.split(':', 1)
        type = tv[0]
        value = tv[1].strip()
        headers[type] = value
        eoh += 1
    eoh +=1

    # handle special hotmail messages
    if email == 'Hotmail':
        if not headers.has_key('Content-Type'):
            return
        hotmail_info = {}

        # parse the body
        for i in lines:
            i = i.strip()
            if not i:
                continue
            tv = i.split(':', 1)
            type = tv[0]
            value = tv[1].strip()
            hotmail_info[type] = value

        msnlib.debug(params)
        if headers['Content-Type'] == 'text/x-msmsgsinitialemailnotification; charset=UTF-8':
            newmsgs = int(hotmail_info['Inbox-Unread'])
            if not newmsgs:
                return
            printl('\rYou have %s unread email(s)' % str(newmsgs) \
                + ' in your Hotmail account\n', c.green, 1)
        elif headers['Content-Type'] == 'text/x-msmsgsemailnotification; charset=UTF-8':
            from_name = hotmail_info['From']
            from_addr = hotmail_info['From-Addr']
            subject = hotmail_info['Subject']
            printl('\rYou have just received an email in your' + \
                ' Hotmail account:\n', c.green, 1)
            printl('\r\tFrom: %s (%s)\n' % (from_name, from_addr),
                c.green, 1)
            printl('\r\tSubject: %s\n' % subject, c.green, 1)
        return

    if headers.has_key('Content-Type') and headers['Content-Type'] == 'text/x-msmsgscontrol':
        # the typing notices
        nick = email2nick(email)
        if not nick: nick = email
        if not m.users[email].priv.has_key('typing'):
            m.users[email].priv['typing'] = 0
        if not m.users[email].priv['typing'] and email not in ignored:
            printl('\r')
            ctime = time.strftime('%I:%M:%S%p', now())
            printl('%s ' % ctime, c.blue)
            printl('%s' % nick, c.cyan, 1)
            printl(' is typing\n', c.magenta)
        m.users[email].priv['typing'] = time.time()
    elif headers.has_key('Content-Type') and headers['Content-Type'] == 'text/x-clientcaps':
        # ignore the x-clientcaps messages generated from gaim
        pass
    elif headers.has_key('Content-Type') and headers['Content-Type'] == 'text/x-keepalive':
        # ignore kopete's keepalive messages
        pass
    else:
        # messages
        m.users[email].priv['typing'] = 0
        printl('\r')
        print_inc_msg(email, lines, eoh)
        handle_msg(email, lines)
        # m.sendmsg(email, lines[-1])
        if len(sbd.emails) > 1:
            log_msg(email, 'in', string.join(lines[eoh:], '\n'), \
                users = sbd.emails)
        else:
            log_msg(email, 'in', string.join(lines[eoh:], '\n'))

        # append the message to the history, keeping it below the configured limit
        if len(history_ring) > config['history size']:
            del(history_ring[0])
        history_ring.append((time.time(), email, lines[eoh:]))

    last_received = email
    msncb.cb_msg(md, type, tid, params, sbd)

m.cb.msg = cb_msg


# join a conversation and send pending messages
def cb_joi(md, type, tid, params, sbd):
    email = tid
    nick = email2nick(email)
    if not nick: nick = email
    if sbd.emails and email != sbd.emails[0]:
        first_nick = email2nick(sbd.emails[0])
        if not first_nick: first_nick = sbd.emails[0]
        printl('\rUser %s has joined the chat with %s\n' % \
            (nick, first_nick), c.green, 1)
        log_msg(email, 'multi', 'join', \
            users = sbd.emails + [email])
    elif len(sbd.msgqueue) > 0:
        printl('\rFlushing messages for %s:\n' % nick, c.green, 1)
        for msg in sbd.msgqueue:
            print_out_msg(nick, msg)
            printl('\n')
            log_msg(email, 'out', msg)
    msncb.cb_joi(md, type, tid, params, sbd)
m.cb.joi = cb_joi

def cb_iro(md, type, tid, params, sbd):
    p = params.split(' ')
    uid, ucount, email, realnick = p
    nick = email2nick(email)
    if not nick: nick = email

    if ucount == '1':
        # do nothing if we only have one participant
        pass
    else:
        first_nick = email2nick(sbd.emails[0])
        if not first_nick: first_nick = sbd.emails[0]
        # print a special message for the first user
        if uid == '1':
            printl('\rUser %s has invited us to a multi-user chat\n' % \
                first_nick, c.green, 1)
        else:
            printl('\rUser %s has joined the chat with %s\n' % \
                (nick, first_nick), c.green, 1)
            log_msg(email, 'multi', 'join', \
                users = sbd.emails + [email])
    msncb.cb_iro(md, type, tid, params, sbd)
m.cb.iro = cb_iro

# server errors
def cb_err(md, errno, params):
    if not msncb.error_table.has_key(errno):
        desc = 'Unknown'
    else:
        desc = msncb.error_table[errno]
    desc = '\rServer sent error %d: %s\n' % (errno, desc)
    perror(desc)
    msncb.cb_err(md, errno, params)
m.cb.err = cb_err

# users add, delete and modify
def cb_add(md, type, tid, params):
    t = params.split(' ')
    type = t[0]
    if type == 'RL' or type == 'FL':
        email = t[2]
        nick = urllib.unquote(t[3])
    if type == 'RL':
        out = '\r' + c.blue + c.bold + ('%s (%s) ' % (email, nick)) \
            + c.magenta + 'has added you to his contact list\n'
        printl(out)
        beep()
    elif type == 'FL':
        out = '\r' + c.blue + c.bold + ('%s (%s) ' % (email, nick)) \
            + c.magenta + 'has been added to your contact list\n'
        printl(out)
    msncb.cb_add(md, type, tid, params)
m.cb.add = cb_add

def cb_rem(md, type, tid, params):
    t = params.split(' ')
    type = t[0]
    if type == 'RL' or type == 'FL':
        email = t[2]
    if type == 'RL':
        out = '\r' + c.blue + c.bold + email + ' ' + c.magenta \
            + 'has removed you from his contact list\n'
        printl(out)
        beep()
    elif type == 'FL':
        out = '\r' + c.blue + c.bold + email + ' ' + c.magenta \
            + 'has been removed from your contact list\n'
        printl(out)
    msncb.cb_rem(md, type, tid, params)
m.cb.rem = cb_rem

def cb_rea(md, type, tid, params):
    t = params.split(' ')
    email = t[1]
    nick = urllib.unquote(t[2])
    if email != md.email:
        out = '\r' + c.blue + c.bold + email + ' ' + c.magenta \
            + 'has been renamed to ' + c.bold + nick + '\n'
        printl(out)
    else:
        out = '\r' + c.magenta + 'Your nick has been changed to ' \
            + c.bold + nick + '\n'
        printl(out)
    msncb.cb_rea(md, type, tid, params)
m.cb.rea = cb_rea

def cb_adg(md, type, tid, params):
    t = params.split(' ')
    lver, name, gid = t[0:3]
    name = urllib.unquote(name)
    out = '\r' + c.magenta + 'Group '
    out += c.blue + c.bold + '%s (%s)' % (name, gid) + c.clear
    out += c.magenta + ' has been added\n'
    printl(out)
    msncb.cb_adg(md, type, tid, params)
m.cb.adg = cb_adg

def cb_rmg(md, type, tid, params):
    t = params.split(' ')
    lver, gid = t[0:2]
    name = md.groups[gid]
    out = '\r' + c.magenta + 'Group '
    out += c.blue + c.bold + '%s (%s)' % (name, gid) + c.clear
    out += c.magenta + ' has been removed\n'
    printl(out)
    msncb.cb_rmg(md, type, tid, params)
m.cb.rmg = cb_rmg

def cb_reg(md, type, tid, params):
    t = params.split(' ')
    gid = t[1]
    origname = md.groups[gid]
    origname = urllib.unquote(origname)
    newname = t[2]
    newname = urllib.unquote(newname)
    out = '\r' + c.magenta + 'Group '
    out += c.blue + c.bold + '%s (%s)' % (origname, gid) + c.clear
    out += c.magenta + ' has been renamed to '
    out += c.blue + c.bold + '%s' % newname + '\n'
    printl(out)
    msncb.cb_reg(md, type, tid, params)
m.cb.reg = cb_reg



parser = OptionParser()
parser.add_option("-p", "--port",
                  type="int", help="port of msn send")
parser.add_option("-l", "--email",
                  help="Msn account")
parser.add_option("-t", "--password",
                help="Msn account")
parser.add_option("-f", "--file",
                    help="receive msn message proccess")
parser.add_option("-d", "--daemon", action="store_true",
                    help="run as daemon")
                  
(options, args) = parser.parse_args()


check_ok = 0
if not options.email:
    printl('-l email is required')
elif not re.match(r'[\w\_\.]+@[\w\_]+(\.[\w\_]+){1,3}', options.email):
    printl('-l invailid email')
elif not options.password:
    printl('-t password is required')
elif not options.port:
    printl('-p port is required')
elif options.port < 1024:
    printl('-p port must gt 1024')
elif not options.file:
    printl('-f exc file is require')
elif not os.access(options.file, os.X_OK):
    printl('-f file is not exc')
else:
   check_ok = 1
   
if not check_ok:
    sys.exit('-1')

if options.daemon:
    if runAsDaemon() == -1:
        printl('run as daemon failure')

config = {}
config['email'] = options.email
config['password'] = options.password
profile = None
#
# now the real thing
#
printl('* MSN Client (3.7) *\n', c.yellow, 1)

# first, the configuration
# printl('Loading config... ', c.green, 1)
# if len(sys.argv) > 1:
#     # first, try the arg as file
#     config = get_config(sys.argv[1])
#     profile = None
#     if not config:
#         # then, as the profile
#         profile = sys.argv[1]
#         file = os.environ['HOME'] + '/.msn/msnrc-' + profile
#         config = get_config(file)
# else:
#     profile = None
#     config = get_config(os.environ['HOME'] + '/.msn/msnrc')


if not config:
    perror('Error opening config file (%s), try running "msnsetup"\n' % file)
    quit(1)

config['profile'] = profile

# set the mandatory values
if config.has_key('email'):
    m.email = config['email']
else:
    perror('Error: email not specified in config file\n')
    quit(1)

if config.has_key('password'):
    m.pwd = config['password']
else:
    # we ask for the password, setting, if necesary, blocking IO over
    # stdin (which was disabled by the terminal handling stuff)
    import getpass
    try: fcntl.fcntl(stdinfd, fcntl.F_SETFL, os.O_SYNC)
    except: pass
    m.pwd = getpass.getpass(c.green + c.bold + "\nPassword: ")
    try: fcntl.fcntl(stdinfd, fcntl.F_SETFL, os.O_NONBLOCK)
    except: pass

# and the optional ones, setting the defaults if not present
# history size
if not config.has_key('history size'):
    config['history size'] = 10
else:
    try:
        config['history size'] = int(config['history size'])
    except:
        perror('history size must be integer, using default\n')
        config['history size'] = 10

# input history size
if not config.has_key('input history size'):
    config['input history size'] = 10
else:
    try:
        config['history size'] = int(config['history size'])
    except:
        error('input history size must be integer, using default\n')
        config['input history size'] = 10

# initial status
if not config.has_key('initial status'):
    config['initial status'] = 'online'
elif config['initial status'] not in msnlib.status_table.keys():
    perror('unknown initial status, using default\n')
    config['initial status'] = 'online'

# debug
if not config.has_key('debug'):
    config['debug'] = 0
elif config['debug'] != 'yes':
    config['debug'] = 0

# colors
if not config.has_key('color theme'):
    config['color theme'] = 'default'
try:
    c = color_classes[config['color theme']]()
except:
    perror("Unknown color theme, type 'color' for help\n")

# log history
if not config.has_key('log history'):
    config['log history'] = 1
elif config['log history'] != 'yes':
    config['log history'] = 0

# history directory
if not config.has_key('history directory'):
    config['history directory'] = os.environ['HOME'] + '/.msn/history'

# show realnick changes
if not config.has_key('show realnick changes'):
    config['show realnick changes'] = 0
elif config['show realnick changes'] != 'yes':
    config['show realnick changes'] = 0

# auto away time
if not config.has_key('auto away'):
    config['auto away'] = 0
else:
    try:
        config['auto away'] = int(config['auto away'])
    except:
        perror('auto away must be integer, using default\n')
        config['auto away'] = 0
if config['auto away'] and config['auto away'] < 60:    # sanity check
    perror('Warning: auto away time was set to less than a minute!\n')

# encoding
if not config.has_key('encoding'):
    # we use posix standard way of defining standard locale, or just fall
    # back to iso-8859-1; see locale(7) for more details
    if os.environ.has_key('LC_ALL') and os.environ['LC_ALL']:
        config['encoding'] = os.environ['LC_ALL']
    elif os.environ.has_key('LANG') and os.environ['LANG']:
        config['encoding'] = os.environ['LANG']
    else:
        config['encoding'] = 'utf-8'
m.encoding = config['encoding']

printl('done\n', c.green, 1)


# set or void the debug
if not config['debug']:
    msnlib.debug = null
    msncb.debug = null

# debug some internal variables
msnlib.debug("Terminal Handling: %d" % use_termios)
msnlib.debug("Terminal Size: %s" % str(winsize))

# login to msn
printl('Logging in... ', c.green, 1)
try:
    m.login()
    printl('done\n', c.green, 1)
except 'AuthError', info:
    errno = int(info[0])
    if not msncb.error_table.has_key(errno):
        desc = 'Unknown'
    else:
        desc = msncb.error_table[errno]
    perror('Error: %s (%s)\n' % (desc, errno))
    quit(1)
except KeyboardInterrupt:
    quit()
except ('SocketError', socket.error), info:
    perror('Network error: ' + str(info) + '\n')
    quit(1)
except:
    pexc('Exception logging in\n')
    quit(1)


# call sync to get the lists and refresh
printl('Sending user list request... ', c.green, 1)
if m.sync():
    printl('done\n', c.green, 1)
    list_complete = 0
else:
    perror('Error syncing users\n')


# global variables
history_ring = []   # history buffer
last_sent = ''      # email of the last person we sent a message to
last_received = ''  # email of the last person we received a message from
ignored = []        # people being locally ignored

# auto-away
timeout = config['auto away']
if not timeout:
    timeout = None      # must be None, not 0 because of select() semantics
auto_away = 0

# loop
#redraw_cli()

#add by wj
HOST = '127.0.0.1'
PORT = options.port
mySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    mySocket.bind((HOST, PORT))
except socket.error:
    sys.exit('call to bind fail')
    
while 1:
    fds = m.pollable()
    infd = fds[0]
    outfd = fds[1]
    #infd.append(sys.stdin)
    #add socket
    mySocket.listen(1)
    infd.append(mySocket.fileno())
    
    try:
        fds = select.select(infd, outfd, [], timeout)
    except KeyboardInterrupt:
        quit()

    if timeout and len(fds[0] + fds[1]) == 0:
        # timeout, set auto away
        if m.status == 'NLN':
            m.change_status('away')
            auto_away = 1
            printl('\rAutomatically changing status to away\n', c.green, 1)

    for i in fds[0] + fds[1]:       # see msnlib.msnd.pollable.__doc__
        if i == sys.stdin:
            # auto away revival
            if auto_away:
                auto_away = 0
                m.change_status('online')
                printl('\rAutomatically changing status back to online\n', c.green, 1)
            # read from stdin
            stdin_read()
        elif i == mySocket.fileno():
            conn, addr = mySocket.accept()
            msg = conn.recv(1024)
            if msg:
                try:
                    (cmd, email, msg) = msg.split("\n", 2)
                    if cmd != 'send':
                        conn.send('Unknown cmd')
                    elif not re.match(r'[\w\_\.]+@[\w\_]+(\.[\w\_]+){1,3}', email):
                        conn.send('invalid email')
                    else:
                        nick = email2nick(email)
                        if not nick: nick = email
                        
                        r = m.sendmsg(email, msg)
                        
                        result = '';
                        if r == 1:
                            result =  'Message for %s queued for delivery' % nick
                        elif r == 2:
                            result = 'Message for %s delivery' % nick
                            # print_out_msg(nick, msg)
                            # if len(m.users[email].sbd.emails) > 1:
                            #     log_msg(m.email, 'out', msg, \
                            #         users = m.users[email].sbd.emails)
                            # else:
                            #     log_msg(email, 'out', msg)
                        elif r == -2:
                            result = 'Message too big'
                        else:
                            result = 'Error %d sending message' % r
                        conn.send("ok\n" + result)
                except ValueError:
                    conn.send('invalid protocol')
            else:
                conn.send('error')
            conn.close()
        else:
            try:
                m.read(i)

                # see if we got all the user list, so we can
                # change our initial status (doing it earlier
                # as we used to seems to break things for some
                # people)
                if not list_complete and \
                        m.lst_total == m.syn_total:
                    list_complete = 1
                    if m.change_status(config['initial status']):
                        printl('\rStatus set to %s\n' % config['initial status'], c.green, 1)
                    else:
                        perror('\rError setting status: unknown status %s\n' % config['initial status'])



            except ('SocketError', socket.error), err:
                if i != m:
                    if i.msgqueue:
                        nick = email2nick(i.emails[0])
                        printl("\rConnection with %s closed - the following messages couldn't be sent:\n" % (nick), c.green, 1)
                        for msg in i.msgqueue:
                            printl(c.bold + '\t>>> ' + c.normal + msg + '\n')
                    m.close(i)
                else:
                    printl('\nMain socket closed (%s)\n' % str(err), c.red)
                    quit(1)
            except 'XFRError', err:
                printl("\rXFR Error: %s\n" % str(err))

            # always redraw after network event
            redraw_cli()


