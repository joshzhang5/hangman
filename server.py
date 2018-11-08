import sys
import random

#TODO add 15 words of length 3-8 with at least 3 unique lengths among the 15.
WORDS = ["dog", "cat", "elephant", "wasp", "tiger", "lion", "aardwolf", "boar"]
HOST = "localhost"
# Shouldn't ever be more than 6 connection requests
MAX_CONNECTIONS = 6

class GameInstance:
    def __init__(self, isMultiplayer=False):
        self.word = random.choice(WORDS)
        self.gameState = ["_"] * len(self.word)
        self.multiplayer = isMultiplayer


def main():
    serverSocket = getServerSocket(sys.argv[0])
    games = {}
    while True:
        (clientsocket, address) = serversocket.accept()
        if address not in games:





def getServerSocket(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((HOST, port))
    socket.listen(MAX_CONNECTIONS) 
    return socket