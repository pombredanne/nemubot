import socket
import _thread
import time

import message

class Server:
    def __init__(self, server, nick, owner, realname):
      self.nick = nick
      self.owner = owner
      self.realname = realname

      if server.hasAttribute("server"):
        self.host = server.getAttribute("server")
      else:
        self.host = "localhost"
      if server.hasAttribute("port"):
        self.port = int(server.getAttribute("port"))
      else:
        self.port = 6667
      if server.hasAttribute("password"):
        self.password = server.getAttribute("password")
      else:
        self.password = None

      self.channels = list()
      for channel in server.getElementsByTagName('channel'):
        self.channels.append(channel.getAttribute("name"))

    def send_msg (self, channel, msg, cmd = "PRIVMSG", endl = "\r\n"):
      for line in msg.split("\n"):
        if line != "" and self.accepted_channel(channel):
          self.s.send (("%s %s :%s%s" % (cmd, channel, line, endl)).encode ())

    def send_global (self, msg, cmd = "PRIVMSG", endl = "\r\n"):
      for channel in self.channels:
        self.send_msg (channel, msg, cmd, endl)


    def launch(self, mods):
      _thread.start_new_thread(self.connect, (mods,))

    def accepted_channel(self, channel):
      return (self.channels.count(channel) != -1)

    def read(self, mods):
      self.readbuffer = "" #Here we store all the messages from server
      while 1:
        try:
            self.readbuffer = self.readbuffer + self.s.recv(1024).decode() #recieve server messages
        except UnicodeDecodeError:
            print ("ERREUR de décodage unicode")
            continue
        temp = self.readbuffer.split("\n")
        self.readbuffer = temp.pop( )

        for line in temp:
          msg = message.Message (self, line)
#          try:
          msg.treat (mods)
#          except:
#              print ("Une erreur est survenue lors du traitement du message : %s"%line)


    def connect(self, mods):
      self.s = socket.socket( ) #Create the socket
      self.s.connect((self.host, self.port)) #Connect to server

      if self.password != None:
        self.s.send(b"PASS " + self.password.encode () + b"\r\n")
      self.s.send(("NICK %s\r\n" % self.nick).encode ())
      self.s.send(("USER %s %s bla :%s\r\n" % (self.nick, self.host, self.realname)).encode ())
      print ("Connection to %s:%d completed" % (self.host, self.port))

      self.s.send(("JOIN %s\r\n" % ' '.join (self.channels)).encode ())
      print ("Listen to channels: %s" % ' '.join (self.channels))

      self.read(mods)