#!/usr/bin/env python
#
# This is a very simple example of a client that sends a "Swing" remote
# command to the IV Swinger 2 application.
#
"""Simple IV Swinger 2 remote command client example"""

import zmq  # pip install pyzmq

IP_ADDRESS = "localhost"       # This computer
# IP_ADDRESS = "192.168.1.102"   # DHCP IP adddress
# IP_ADDRESS = "99.95.164.127"   # Public IP address (needs port forwarding)

PORT = 5100

COMMAND = "Swing"

# Create ZMQ context
context = zmq.Context()

# Create socket
socket = context.socket(zmq.REQ)

# Connect socket to port
print(f"Connecting to IP address {IP_ADDRESS} port {PORT}")
socket.connect(f"tcp://{IP_ADDRESS}:{PORT}")

# Send command
print(f"Sending command: {COMMAND}")
socket.send_string(COMMAND)

#  Get the reply.
reply = socket.recv_string()
print(f"Received reply: {reply}")
