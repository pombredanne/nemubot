#!/usr/bin/python2.7
# coding=utf-8

from datetime import datetime
import re
import socket
import string
import time
import imp

class Message:
  def __init__ (self, srv, line):
    self.srv = srv
    self.time = datetime.now ()
    line = line.rstrip() #remove trailing 'rn'

    if line.find(' PRIVMSG ') != -1: #Call a parsing function
      complete = line[1:].split(':',1) #Parse the message into useful data
      info = complete[0].split(' ')

      self.cmd = "PRIVMSG"
      self.sender = (info[0].split('!'))[0]
      self.channel = info[2]
      self.content = complete[1]

    elif line.find(' NICK ') != -1:
      complete = line[1:].split(':',1) #Parse the message into useful data
      if len(complete) > 1:
        info = complete[0].split(' ')

        self.cmd = "NICK"
        self.sender = (info[0].split('!'))[0]
        self.content = complete[1]
      else:
        self.cmd = "NONE"

    elif line.find(' JOIN ') != -1:
      complete = line[1:].split(':',1) #Parse the message into useful data
      if len(complete) > 1:
        info = complete[0].split(' ')

        self.cmd = "JOIN"
        self.sender = (info[0].split('!'))[0]
        self.channel = complete[1]
      else:
        self.cmd = "NONE"

    elif line.find(' PART ') != -1:
      complete = line[1:].split(':',1) #Parse the message into useful data
      info = complete[0].split(' ')

      self.cmd = "PART"
      self.sender = (info[0].split('!'))[0]
      self.channel = info[2]
      if len (complete) > 1:
        self.content = complete[1]
      else:
        self.content = ""

    elif line.find(' PING ') != -1: #If server pings then pong
      line = line.split()

      self.cmd = "PING"
      self.content = line[1]

    else:
      self.cmd = "UNKNOWN"
      print (line)


  def send_msg (self, channel, msg, cmd = "PRIVMSG", endl = "\r\n"):
    self.srv.send_msg (channel, msg, cmd, endl)

  def send_global (self, msg, cmd = "PRIVMSG", endl = "\r\n"):
    self.srv.send_global (msg, cmd, endl)

  def send_chn (self, msg):
    """Send msg on the same channel as receive message"""
    self.srv.send_msg (self.channel, msg)

  def send_snd (self, msg):
    """Send msg to the sender who send the original message"""
    self.srv.send_msg (self.sender, msg)




  def treat (self, mods):
    if self.cmd == "PING":
      self.pong ()
    elif self.cmd == "PRIVMSG" and self.srv.accepted_channel(self.channel):
      self.parsemsg (mods)
    elif self.cmd == "NICK":
      print ("%s change de nom pour %s" % (self.sender, self.content))
    elif self.cmd == "PART":
      print ("%s vient de quitter %s" % (self.sender, self.channel))
    elif self.cmd == "JOIN":
      print ("%s arrive sur %s" % (self.sender, self.channel))


  def pong (self):
    self.srv.s.send(("PONG %s\r\n" % self.content).encode ())


  def parsemsg (self, mods):
    #Treat all messages starting with 'nemubot:' as distinct commands
    if self.content.find("%s:"%self.srv.nick) == 0:
      messagel = self.content.lower()

      #Is it a simple response?
      if re.match(".*(m[' ]?entends?[ -]+tu|h?ear me|do you copy|ping)", messagel) is not None:
        self.send_chn ("%s: pong"%(self.sender))

      elif re.match(".*(quel(le)? heure est[ -]il|what time is it)", messagel) is not None:
        now = datetime.now()
        self.send_chn ("%s: j'envoie ce message à %s:%d:%d."%(self.sender, now.hour, now.minute, now.second))

      elif re.match(".*di[st] (a|à) ([a-zA-Z0-9_]+) (.+)$", messagel) is not None:
        result = re.match(".*di[st] (a|à) ([a-zA-Z0-9_]+) (qu(e |'))?(.+)$", self.content)
        self.send_chn ("%s: %s"%(result.group(2), result.group(5)))
      elif re.match(".*di[st] (.+) (a|à) ([a-zA-Z0-9_]+)$", messagel) is not None:
        result = re.match(".*di[st] (.+) (à|a) ([a-zA-Z0-9_]+)$", self.content)
        self.send_chn ("%s: %s"%(result.group(3), result.group(1)))

      elif re.match(".*di[st] sur (#[a-zA-Z0-9]+) (.+)$", self.content) is not None:
        result = re.match(".*di[st] sur (#[a-zA-Z0-9]+) (.+)$", self.content)
        if self.srv.channels.count(result.group(1)):
          self.send_msg(result.group(1), result.group(2))
      elif re.match(".*di[st] (.+) sur (#[a-zA-Z0-9]+)$", self.content) is not None:
        result = re.match(".*di[st] (.+) sur (#[a-zA-Z0-9]+)$", self.content)
        if self.srv.channels.count(result.group(2)):
          self.send_msg(result.group(2), result.group(1))

      #Try modules
      else:
        for im in mods.keys():
          if mods[im].parseask(self):
            return

    #Owner commands
    elif self.content[0] == '`' and self.sender == self.srv.owner:
      self.cmd = self.content[1:].split(' ')
      if self.cmd[0] == "reload":
        if len(self.cmd) > 1:
          if self.cmd[1] in mods:
            mods[self.cmd[1]].save_module ()
            imp.reload(mods[self.cmd[1]])
            mods[self.cmd[1]].load_module (self.srv.datas_dir)
            self.send_snd ("Module %s rechargé avec succès."%self.cmd[1])
          else:
            self.send_snd ("Module inconnu %s."%self.cmd[1])
        else:
          self.send_snd ("Usage: `reload /module/.")
          self.send_snd ("Loaded modules: " + ', '.join(mods.keys()) + ".")

    #Messages stating with !
    elif self.content[0] == '!':
      self.cmd = self.content[1:].split(' ')
      if self.cmd[0] == "help":
        if len (self.cmd) > 1:
          if self.cmd[1] in mods:
            self.send_snd(mods[self.cmd[1]].help_full ())
          else:
            self.send_snd("No help for command %s" % self.cmd[1])
        else:
          self.send_snd("Pour me demander quelque chose, commencez votre message par mon nom ; je réagis à certain messages commençant par !, consulter l'aide de chaque module :")
          for im in mods.keys():
            self.send_snd("  - !help %s: %s" % (im, mods[im].help_tiny ()))

      for im in mods.keys():
        if mods[im].parseanswer(self):
          return

    else:
      for im in mods.keys():
        if mods[im].parselisten(self):
          return


##############################
#                            #
#   Extraction/Format text   #
#                            #
##############################

  def just_countdown (self, delta, resolution = 5):
    sec = delta.seconds
    hours, remainder = divmod(sec, 3600)
    minutes, seconds = divmod(remainder, 60)
    an = int(delta.days / 365.25)
    days = delta.days % 365.25

    sentence = ""
    force = False

    if resolution > 0 and (force or an > 0):
      force = True
      sentence += " %i an"%(an)

      if an > 1:
        sentence += "s"
      if resolution > 2:
        sentence += ","
      elif resolution > 1:
        sentence += " et"

    if resolution > 1 and (force or days > 0):
      force = True
      sentence += " %i jour"%(days)

      if days > 1:
        sentence += "s"
      if resolution > 3:
        sentence += ","
      elif resolution > 2:
        sentence += " et"

    if resolution > 2 and (force or hours > 0):
      force = True
      sentence += " %i heure"%(hours)
      if hours > 1:
        sentence += "s"
      if resolution > 4:
        sentence += ","
      elif resolution > 3:
        sentence += " et"

    if resolution > 3 and (force or minutes > 0):
      force = True
      sentence += " %i minute"%(minutes)
      if minutes > 1:
        sentence += "s"
      if resolution > 4:
        sentence += " et"

    if resolution > 4 and (force or seconds > 0):
      force = True
      sentence += " %i seconde"%(seconds)
      if seconds > 1:
        sentence += "s"
    return sentence[1:]


  def countdown_format (self, date, msg_before, msg_after, timezone = None):
    """Replace in a text %s by a sentence incidated the remaining time before/after an event"""
    if timezone != None:
      os.environ['TZ'] = timezone
      time.tzset()

    #Calculate time before the date
    if datetime.now() > date:
        sentence_c = msg_after
        delta = datetime.now() - date
    else:
        sentence_c = msg_before
        delta = date - datetime.now()

    if timezone != None:
      os.environ['TZ'] = "Europe/Paris"

    return sentence_c % self.just_countdown(delta)


  def extractDate (self):
    """Parse a message to extract a time and date"""
    msgl = self.content.lower ()
    result = re.match("^[^0-9]+(([0-9]{1,4})[^0-9]+([0-9]{1,2}|janvier|january|fevrier|février|february|mars|march|avril|april|mai|maï|may|juin|juni|juillet|july|jully|august|aout|août|septembre|september|october|octobre|oktober|novembre|november|decembre|décembre|december)([^0-9]+([0-9]{1,4}))?)[^0-9]+(([0-9]{1,2})[^0-9]*[h':]([^0-9]*([0-9]{1,2})([^0-9]*[m\":][^0-9]*([0-9]{1,2}))?)?)?.*$", msgl + " TXT")
    if result is not None:
      day = result.group(2)
      if len(day) == 4:
        year = day
        day = 0
      month = result.group(3)
      if month == "janvier" or month == "january" or month == "januar":
        month = 1
      elif month == "fevrier" or month == "février" or month == "february":
        month = 2
      elif month == "mars" or month == "march":
        month = 3
      elif month == "avril" or month == "april":
        month = 4
      elif month == "mai" or month == "may" or month == "maï":
        month = 5
      elif month == "juin" or month == "juni" or month == "junni":
        month = 6
      elif month == "juillet" or month == "jully" or month == "july":
        month = 7
      elif month == "aout" or month == "août" or month == "august":
        month = 8
      elif month == "september" or month == "septembre":
        month = 9
      elif month == "october" or month == "october" or month == "oktober":
        month = 10
      elif month == "november" or month == "novembre":
        month = 11
      elif month == "december" or month == "decembre" or month == "décembre":
        month = 12

      if day == 0:
        day = result.group(5)
      else:
        year = result.group(5)

      hour = result.group(7)
      minute = result.group(9)
      second = result.group(11)

      print ("Chaîne reconnue : %s/%s/%s %s:%s:%s"%(day, month, year, hour, minute, second))
      if year == None:
        year = date.today().year
      if hour == None:
        hour = 0
      if minute == None:
        minute = 0
      if second == None:
        second = 1
      else:
        second = int (second) + 1
        if second > 59:
          minute = int (minute) + 1
          second = 0

      return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
    else:
      return None
