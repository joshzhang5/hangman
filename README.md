# Hangman
## Authors
Michael Lin - Single Player implementation
Jiaxi Zhang - Multiplayer implementation/bug-fixes
## Running
Requires Python3 with no other dependencies.

Run the server with
```
python3 server.py YOUR_PORT
```

Run the client with
```
python3 client.py YOUR_IP YOUR_PORT
```

On linux both the client and server may be run directly after
chmod the server and client as executable

```
chmod +x server.py
chmod +x client.py
```

Then execute the client/server directly

```
./server.py YOUR_PORT
./client.py YOUR_IP YOUR_PORT
```

## Design
There are two classes for the server, `GameInstance` and `GameServer`.
The `GameServer` instance is responsible for managing incoming TCP connections, spawning GameInstances,
and relaying TCP messages from the TCP sockets to the appropriate GameInstances.

The `GameInstance` instances are finite state machines that transition between game states for Hangman.
The transitions between Hangman game states (e.g. between whose turn it is) depend on messages
parsed and passed from the GameServer. Additionally, as the GameInstance transitions between states,
it will directly send messages to the approrpiate TCP sockets to inform the players of their current
turn and game states.

The `GameServer` instance also will terminate `GameInstance` that have players that disconnect or otherwise
encounter errors. Terminating these `GameInstance` will also close the sockets of any other players in that game

The client is also implemented as a simple finite state machine, that will transition between waiting
for messages from the server, parsing game states, as well as accepting input from the user
to send to the server.
