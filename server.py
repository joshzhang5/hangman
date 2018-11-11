#!/usr/bin/env python3

import select
import socket
import sys
import queue
import struct
import io
import random
import time

from collections import deque

WORDS = ["dog", "cat", "rat", "snake", "wasp", "lion", "boar", "lynx", "tiger", "sphynx", "baboon", "monkey", "elephant", "aardwolf", "whale"]
HOST = "localhost"

# GameInstance is an FSM that transitions between the below states
STATE_INITIALIZING = 0 # Initial state before a user selects multiplayer or single player
STATE_MATCHING = 1 # In a multiplayer game, yet to match with a user
STATE_TURN_1 = 2 # Player 1's turn
STATE_TURN_2 = 3 # Player 2's turn (in multiplayer)
STATE_END = 4

# Game instance advances it's FSM based on messages passed
# By the server layer

class GameInstance():
    def __init__(self, player1):
        self.state = STATE_INITIALIZING
        self.incorrectGuesses = set()
        self.correctGuesses = set()
        self.player1 = player1
        self.player2 = None
        self.word = None
        self.wordState = None
        self.unixStartTime = time.time()

        # Multiplayer gets set to TRUE in the matching state
        self.multiplayer = False
        
    def addPlayer2(self, player2):
        if self.player2:
            raise Exception("Player 2 already set!")
        if self.multiplayer == False:
            raise Exception("Non-multiplayer games cannot have second player!")
        self.player2 = player2
        self.state = STATE_TURN_1

        # Pick a word
        self.word = random.choice(WORDS)
        self.wordState = "_" * len(self.word)
        
        self.player1.send(GameServer.constructMsg("Game Starting!"))
        self.player2.send(GameServer.constructMsg("Game Starting!"))

        self.informState()

    def getPlayer1(self):
        return self.player1

    def getPlayer2(self):
        if not self.multiplayer:
            raise Exception("No player 2!")
        return self.player2

    def getPlayers(self):
        if self.multiplayer:
            return self.player1, self.player2
        else:
            return (self.player1,)

    def getWordState(self):
        return self.wordState

    def getState(self):
        return self.state

    def isMultiplayer(self):
        return self.multiplayer

    # Informs the current state to the player(s) of the game
    # Called between every transition
    def informState(self):
        if not self.multiplayer:
            player1Msg = self.createGameMsg()
            self.player1.send(player1Msg)
        else:
            activePlayerMessage = ["Your turn!\n"]
            waitingPlayerMessage = ["Waiting on Player " + (str(1) if self.state == STATE_TURN_1 else str(2)) + "...\n"]
            player1Msgs, player2Msgs = activePlayerMessage, waitingPlayerMessage 
            if self.state == STATE_TURN_2:
                player1Msgs,  player2Msgs = player2Msgs, player1Msgs

            for msg in player1Msgs:
                self.player1.send(GameServer.constructMsg(msg))
            for msg in player2Msgs:
                self.player2.send(GameServer.constructMsg(msg))

            if self.state == STATE_TURN_1:
                self.player1.send(self.createGameMsg())
            else:
                self.player2.send(self.createGameMsg())

    # Advances the state machine with each client message
    def readClientMsg(self, player, msg):
        if self.state == STATE_INITIALIZING:
            # interpret message as single player or multiplayer
            if (int(msg) == 0): 
                # single player
                # start the game immediately
                # Pick a word
                # check if there are too many Games occuring right now
                self.word = random.choice(WORDS)
                self.wordState = "_" * len(self.word)
                self.multiplayer = False
                # Not neccessary
                # player.send(GameServer.constructMsg("Game Start!"))
                self.state = STATE_TURN_1
            elif (int(msg) == 2):
                # multiplayer
                self.state = STATE_MATCHING
                self.multiplayer = True
                return # Do not inform state until we have left the queue
            else:
                player.send(GameServer.constructMsg("Invalid multiplayer mode."))
                
                return # Do not advance state
        elif (self.state == STATE_TURN_1 and player == self.player1) or (self.state == STATE_TURN_2 and player == self.player2):
            # check if letter has alrea dy been guessed
            if msg in self.correctGuesses or msg in self.incorrectGuesses:
                player.send(GameServer.constructMsg("Letter has already been guessed!"))
                return # Do not inform state.
            if chr(msg) in self.word:
                new_str = ""
                for i, l in enumerate(self.word):
                    if(l == chr(msg)):
                        new_str += chr(msg)
                    else:
                        new_str += self.wordState[i]
                self.wordState = new_str
                # Examples don't send this.
                player.send(GameServer.constructMsg("Correct!"))
                self.correctGuesses.add(msg)
            else:
                self.incorrectGuesses.add(msg) 
                # Examples don't send this.
                player.send(GameServer.constructMsg("Incorrect!"))
            # Switch turns if multiplayer
            if self.multiplayer:
                self.state = STATE_TURN_2 if self.state == STATE_TURN_1 else STATE_TURN_1

        elif self.state == STATE_END:
            return # Do not do anything; game has ended.
        else:
            player.send(GameServer.constructMsg("Not your turn!"))
            return # Do not inform state.
      
        # Inform clients of state

        # Check end conditions
        if len(self.incorrectGuesses) >= 6:
            self.endGame("You Lose!")
        elif len(self.correctGuesses) == len(self.word):
            self.endGame("You Win!")
        else:
            self.informState()


    def getIncorrectGuesses(self):
        return self.incorrectGuesses

    def createGameMsg(self):
        # Creates game control packet
        # includes length of word, and the number incorrect
        word_len = len(self.word.encode("ascii"))
        num_incorrect = len(self.getIncorrectGuesses())
        incorrectLetters = ""
        for incorrect in self.getIncorrectGuesses():
            incorrectLetters += chr(incorrect)
        return struct.pack("BBB", 0, word_len, num_incorrect) + self.wordState.encode("ascii") + incorrectLetters.encode("ascii")
    
    # Ends the game
    def endGame(self, outcomeMsg):
        print("Game ended with outcome " + outcomeMsg)
        self.state = STATE_END
        for player in self.getPlayers():
            player.send(self.createGameMsg())
            player.send(GameServer.constructMsg(outcomeMsg))
            player.send(GameServer.constructMsg("Game Over!"))


class GameServer():
    def __init__(self, port):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Re-use socket address if necessary
        linger_enabled = 1
        linger_time = 10 #This is in seconds.
        linger_struct = struct.pack('ii', linger_enabled, linger_time)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # set linger to guarentee pending messages sent
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger_struct)
        
        self.server.setblocking(0)
        self.server.bind((HOST, port))
        self.server.listen(6)

        # Input sockets
        self.inputs = [self.server]

        # Output Sockets
        self.outputs = []

        # Maps sockets to GameInstances
        self.gamesMap = {}

        # list of GameInstances looking to be matched, used to make sure "Waiting for other player!" messages only sent once.
        self.matchQueue = set()

        # Client buffers buffers incoming messages from recv
        self.clientBuffers = {}

    def getGames(self):
        return sorted(self.gamesMap.values(), key=lambda game: game.unixStartTime)

    # send server-overloaded message and gracefully shut down the socket
    def handleServerOverload(s):
        errMsg = GameServer.constructMsg("server-overloaded")
        s.send(errMsg)
        s.shutdown(socket.SHUT_RDWR)
        s.close()

    # handles a new incoming connection
    def handleConnection(self, s):
        connection, client_address = s.accept()
        connection.setblocking(0)
        # Set up new game if there are < 3 currently active games.
        activeGames = filter(lambda x: (x.getState() == STATE_TURN_1 or x.getState() == STATE_TURN_2), self.gamesMap.values())
        if len(set(activeGames)) == 3:
            GameServer.handleServerOverload(connection)
        else:
            self.inputs.append(connection)
            self.outputs.append(connection)
            
            # Buffers incoming data from recv from this client
            self.clientBuffers[connection] = deque()

            # Initializes a GameInstance in STATE_INITIALIZING state
            self.gamesMap[connection] = GameInstance(connection)

            print("Connection with a client established!")
            
    # Handles incoming data
    def handleData(self, s):
        data = s.recv(1024)
        if data:
            for byte in data:
                self.clientBuffers[s].append(byte)
            if s not in self.outputs:
                self.outputs.append(s)

            # We have to handle parsing the multiplayer messages seperately because
            # Those messages violate the protocal
            if self.gamesMap[s].getState() == STATE_INITIALIZING:
                if len(self.clientBuffers[s]) >= 1:
                    byte_1 = self.clientBuffers[s].popleft()
                    self.gamesMap[s].readClientMsg(s, byte_1)

            # Parse the rest of the buffered data normally
            while len(self.clientBuffers[s]) >= 2:
                byte_1 = self.clientBuffers[s].popleft()
                byte_2 = self.clientBuffers[s].popleft()
                data = self.parseClientMsg((byte_1, byte_2))
                if data == None:
                    print("Client sent invalid data!")
                    s.send(GameServer.constructMsg("Client sent invalid data!\n"))
                else:
                    # Relay msg to the associated GameInstance
                    self.gamesMap[s].readClientMsg(s, data)
        elif not data:
            # Client has disconnected
            print("Client has disconnected!")
            self.endGame(self.gamesMap[s])

    def matchMultiplayerGames(self):

        # match games in chronological order 
        while (len([game for game in self.getGames() if game.getState() == STATE_MATCHING]) >= 2):
            pendingGames = [game for game in self.getGames() if game.getState() == STATE_MATCHING]
            # Match second game as player2 to first game; destroy the 2nd game
            game1, game2 = pendingGames[0], pendingGames[1]
            player1, player2 = game1.getPlayer1(), game2.getPlayer1()
            game1.addPlayer2(player2)
            # Remove game2 from gameList
            self.gamesMap[player2] = game1 

            # remove games from that match queue if they exist
            if (game1 in self.matchQueue):
                self.matchQueue.remove(game1)
            if (game2 in self.matchQueue):
                self.matchQueue.remove(game2)
        
        # Send a one time message to unmatched players that server is waitingg for new multiplayer connections 
        # and add them to the match queue
        for game in [game for game in self.getGames() if game.getState() == STATE_MATCHING and game not in self.matchQueue]:
            waitingPlayer = game.getPlayer1()
            waitingPlayer.send(GameServer.constructMsg("Waiting for other player!"))
            self.matchQueue.add(game)

    # Returns binary string representing the message passed
    # Byte 0: length of message
    # Byte 1-length: message
    def constructMsg(msg):
        encoded_msg = msg.encode('ascii')
        packed_string = struct.pack("B", len(encoded_msg)) + encoded_msg
        return packed_string

    # Parses the message sent by cleint
    # Byte 0: length of Data (always 1)
    # Byte 1: Data
    def parseClientMsg(self, msg):
        msg_len = int(msg[0])
        if (msg_len != 1):
            return None
        data = msg[1]
        return data

    # Ends the games logically and forcibly closes sockets
    def endGame(self, game):
        players = game.getPlayers()
        # remove each player from buffers
        for player in players:
            self.gamesMap.pop(player, None)
            self.clientBuffers.pop(player, None)
            if player in self.inputs:
                self.inputs.remove(player)
            if player in self.outputs:
                self.outputs.remove(player)
            player.close() # clos esocket
    def loop(self):
        while self.inputs:
            readable, writable, exceptional = select.select(
                self.inputs, self.outputs, self.inputs, 5)
            
            # Check if a socket disconnected
            # If so, delete all players
            for s in exceptional:
                # End game
                game = self.gamesMap[s]
                self.endGame(game)

            # Read incoming data
            for s in readable:
                if s is self.server: # client is trying to connect
                    self.handleConnection(s)
                else: # we've recieved data
                    try:
                        self.handleData(s) # Read data/advance game states
                    except (ConnectionError or ConnectionResetError): # Client disconnected
                        # End game
                        game = self.gamesMap[s]
                        self.endGame(game)
            
            self.matchMultiplayerGames()

            # Checks if any games have ended. If so, we must disconnect such players
            for game in self.getGames():
                if game.getState() == STATE_END:
                    self.endGame(game)


if len(sys.argv) < 2:
    raise Exception("Port number not provided!")

server = GameServer(int(sys.argv[1]))

try:
    print("Starting server at port "  + sys.argv[1])
    server.loop()
except KeyboardInterrupt:
    server.server.shutdown(socket.SHUT_RDWR)
    server.server.close()
finally:
    print ("Shutting down server")
    
