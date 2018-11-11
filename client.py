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


if len(sys.argv) < 3:
    raise Exception("Please provide server address and port as command line arguments")
    
state = STATE_ENTER_MULTIPLAYER

multiplayer = False
while state == STATE_ENTER_MULTIPLAYER:
    val = input("Two Player? (y/n)")
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
s.connect((sys.argv[1], int(sys.argv[2])))
s.setblocking(0)
if multiplayer:
    s.send(bytes([2]))
else:
    s.send(bytes([0]))

bytesToRead = 0
num_incorrect = 0
incorrectLetters = set()
correctLetters = set()
lastGuess = None
wordProgress = ""
GAME_ENDED = False

while not GAME_ENDED or len(buf) > 0:
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
            GAME_ENDED = True
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
        if len(buf) > 0 and len(buf) >= bytesToRead:
            # create the string to print out
            msg = ""
            while(bytesToRead > 0):
                msg += chr(buf.popleft())
                bytesToRead -= 1
            print(msg)
            if(msg == 'Game Over!'): # Disconnect gracefully
                s.shutdown(socket.SHUT_RDWR)
                s.close()
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
            print("Incorrect guesses: {} \n".format(' '.join(incorrectLetters)))
        if len(incorrectLetters) < 6 and sum([1 for _ in wordProgress if _ == '_']) > 0:
            state = STATE_ENTER_LETTER
        else:
            state = STATE_WAIT_RESPONSE

    elif state == STATE_ENTER_LETTER:
        val = input("Letter to guess: ")
        if len(val) > 1 or not val.isalpha():
            print("Error! Please guess one letter.")
            continue
        elif val.lower() in incorrectLetters or val.lower() in correctLetters:
            print("Error! Letter {} has been guessed before, please guess another letter.".format(val.upper()))
            continue
        else:
            lastGuess = val.lower()
            s.send(bytes([1]) + val.lower().encode('ascii'))
            state = STATE_WAIT_RESPONSE

