#include <zmq.h>
#include <string.h>

#define IP_ADDRESS "localhost"      // This computer
//#define IP_ADDRESS "192.168.1.102"  // DHCP IP address
//#define IP_ADDRESS "99.95.164.127"  // Public IP address (needs port forwarding)

#define PORT 5100

#define COMMAND "Swing"

#define MAX_REPLY_LENGTH 512

int main(void) {

    char socket_str[32];
    char reply[MAX_REPLY_LENGTH];

    // Create ZMQ context
    void *context = zmq_ctx_new();

    // Create socket
    void *socket = zmq_socket(context, ZMQ_REQ);

    // Connect socket to port
    printf("Connecting to IP address %s port %d\n", IP_ADDRESS, PORT);
    sprintf(socket_str, "tcp://%s:%d", IP_ADDRESS, PORT);
    zmq_connect(socket, socket_str);

    // Send command
    printf("Sending command: %s\n", COMMAND);
    zmq_send(socket, COMMAND, strlen(COMMAND), 0);

    // Get the reply
    zmq_recv(socket, reply, MAX_REPLY_LENGTH, 0);
    printf("Received reply: %s\n", reply);

    // Clean up
    zmq_close(socket);
    zmq_ctx_destroy(context);

    return 0;
}
