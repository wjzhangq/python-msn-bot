#!/usr/bin/evn ptyhon
# -*- coding:utf-8 -*-

import msnlib, msncb
import sys, select, socket, time

m = msnlib.msnd()
m.cb = msncb.cb()

m.encoding = 'utf-8'
timeout = 300
m.email = 'test@zhangwenjin.com'
m.pwd = '123456'

def null(s):
    "Null function, useful to void debug ones"
    pass

msnlib.debug = null
msncb.debug = null

def debug(str):
    print str + ''

def now():
    "Returns the current time, in tuple format"
    return time.localtime(time.time())

def quit(code = 0):
    "Exits"
    debug('Closing')
    try:
        try:
            m.disconnect()
        except:
            pass
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
            debug('\rYou have %s unread email(s)' % str(newmsgs) \
                + ' in your Hotmail account')
        elif headers['Content-Type'] == 'text/x-msmsgsemailnotification; charset=UTF-8':
            from_name = hotmail_info['From']
            from_addr = hotmail_info['From-Addr']
            subject = hotmail_info['Subject']
            debug('\rYou have just received an email in your' + \
                ' Hotmail account:')
            debug('\r\tFrom: %s (%s)' % (from_name, from_addr))
            debug('\r\tSubject: %s' % subject)
        return

    if headers.has_key('Content-Type') and headers['Content-Type'] == 'text/x-msmsgscontrol':
        # the typing notices
        nick = email2nick(email)
        if not nick: nick = email
        if not m.users[email].priv.has_key('typing'):
            m.users[email].priv['typing'] = 0
        if not m.users[email].priv['typing']:
            debug('\r')
            ctime = time.strftime('%I:%M:%S%p', now())
            debug('%s ' % ctime)
            debug('%s' % nick)
            debug(' is typing')
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
        debug(email + '-*-' + '-*-'.join(lines));
        m.sendmsg(email, lines[-1])
    msncb.cb_msg(md, type, tid, params, sbd)

m.cb.msg = cb_msg

# server errors
def cb_err(md, errno, params):
    if not msncb.error_table.has_key(errno):
        desc = 'Unknown'
    else:
        desc = msncb.error_table[errno]
    desc = '\rServer sent error %d: %s' % (errno, desc)
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
            + c.magenta + 'has added you to his contact list'
        debug(out)
        beep()
    elif type == 'FL':
        out = '\r' + c.blue + c.bold + ('%s (%s) ' % (email, nick)) \
            + c.magenta + 'has been added to your contact list'
        debug(out)
    msncb.cb_add(md, type, tid, params)
m.cb.add = cb_add

try:
    m.login()
    debug('login done')
except 'AuthError', info:
    errno = int(info[0])
    if not msncb.error_table.has_key(errno):
        desc = 'Unknown'
    else:
        desc = msncb.error_table[errno]
    debug('Error: %s (%s)' % (desc, errno))
    quit(1)
except KeyboardInterrupt:
    quit()
except ('SocketError', socket.error), info:
    debug('Network error: ' + str(info))
    quit(1)
except:
    debug('Exception logging in')
    quit(1)

# call sync to get the lists and refresh
if m.sync():
    debug('sync done')
    list_complete = 0
else:
    debug('Error syncing users')

m.change_status('online');

while True:
    fds = m.pollable()
    infd = fds[0]
    outfd = fds[1]
    
    try:
        fds = select.select(infd, outfd, [], timeout)
    except KeyboardInterrupt:
        quit()

    if timeout and len(fds[0] + fds[1]) == 0:
        # timeout, set auto away
        if m.status == 'NLN':
            m.change_status('away')
            auto_away = 1
            debug('\rAutomatically changing status to away')

    for i in fds[0] + fds[1]:       # see msnlib.msnd.pollable.__doc__
        try:
            m.read(i)

            # see if we got all the user list, so we can
            # change our initial status (doing it earlier
            # as we used to seems to break things for some
            # people)
            if not list_complete and \
                    m.lst_total == m.syn_total:
                list_complete = 1
                debug('list_complete is ok');
        except ('SocketError', socket.error), err:
            if i != m:
                if i.msgqueue:
                    nick = email2nick(i.emails[0])
                    dubeg("\rConnection with %s closed - the following messages couldn't be sent:" % (nick))
                    for msg in i.msgqueue:
                        debug(msg )
                m.close(i)
            else:
                debug('\nMain socket closed (%s)' % str(err))
                quit(1)
        except 'XFRError', err:
            debug("\rXFR Error: %s" % str(err))
