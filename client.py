#!/usr/bin/env python3

import socket
import select
from collections import deque
import binascii
import sys
buf = deque()

STATE_ENTER_MULTIPLAYER = 0
STATE_WAIT_RESPONSE = 2
STATE_READ_MSG = 3
STATE_READ_STATE_LENGTH = 4
STATE_READ_LETTERS = 5
STATE_READ_INCORRECT = 6
STATE_ENTER_LETTER = 7


state = STATE_ENTER_MULTIPLAYER

multiplayer = False
while state == STATE_ENTER_MULTIPLAYER:
    val = input("Multiplayer game? (y/n?)")
    if len(val) > 1 or (val != 'y' and val != 'n'):
        print("Please enter y/n")
        print(len(val))
        continue
    else:
        if val == 'y':
            multiplayer = True
        else:
            multiplayer = False
        state = STATE_WAIT_RESPONSE

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('localhost', 9001))
s.setblocking(0)
if multiplayer:
    s.send(bytes([1,2]))
else:
    s.send(bytes([1,0]))
bytesToRead = 0

num_incorrect = 0
incorrectLetters = set()
correctLetters = set()
lastGuess = None
wordProgress = ""

while True:
    ready_to_read, ready_to_write, in_error = \
               select.select(
                  [s],
                  [],
                  [],
                  0.1)
    for sock in ready_to_read:
        data = sock.recv(1024)
        if not data:
            # we have disconnected
            print("Lost connection to server.")
            sys.exit(0)
        for byte in data:
            buf.append(byte)
    if state == STATE_WAIT_RESPONSE:
        # Wait for a single byte from the server, to determine whether we will wait for a msg or client state
        if len(buf) > 0:
            msg_flag = buf.popleft()
            if msg_flag != 0:
                state = STATE_READ_MSG
                bytesToRead = msg_flag
            else:
                bytesToRead = 2
                state = STATE_READ_STATE_LENGTH
    elif state == STATE_READ_MSG:
        if len(buf) >= bytesToRead:
            # create the string to print out
            msg = ""
            while(bytesToRead > 0):
                msg += chr(buf.popleft())
                bytesToRead -= 1
            print(msg)
            if(msg == 'Game Over!'): # Disconnect gracefully
                sys.exit(0)
            state = STATE_WAIT_RESPONSE
    elif state == STATE_READ_STATE_LENGTH:
        if len(buf) >= bytesToRead:
            word_length = buf.popleft()
            num_incorrect = buf.popleft()
            bytesToRead = word_length
            state = STATE_READ_LETTERS
    elif state == STATE_READ_LETTERS:
        if len(buf) >= bytesToRead:
            wordProgress = ""
            while(bytesToRead > 0):
                char = chr(buf.popleft())
                wordProgress += char
                correctLetters.add(char)
                bytesToRead -= 1
            bytesToRead = num_incorrect
            state = STATE_READ_INCORRECT
    elif state == STATE_READ_INCORRECT:
        if len(buf) >= bytesToRead:
            while(bytesToRead > 0):
                char = chr(buf.popleft())
                incorrectLetters.add(char)
                bytesToRead -= 1
            print(wordProgress)
            print("Incorrect guesses:")
            print(incorrectLetters)
        if len(incorrectLetters) < 6 and sum([1 for _ in wordProgress if _ == '_']) > 0:
            state = STATE_ENTER_LETTER
        else:
            state = STATE_WAIT_RESPONSE

    elif state == STATE_ENTER_LETTER:
        val = input("Please enter a letter: ")
        if len(val) > 1:
            print("Please enter one character.")
            continue
        elif not val.isalpha() :
            print("Please enter a letter")
            continue
        elif val.lower() in incorrectLetters or val.lower() in correctLetters:
            print("Please enter a letter you haven't entered before.")
            continue
        else:
            lastGuess = val.lower()
            s.send(bytes([1]) + val.lower().encode('ascii'))
            state = STATE_WAIT_RESPONSE


