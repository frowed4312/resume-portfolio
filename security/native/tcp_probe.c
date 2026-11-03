/* TCP connect worker. Python controls target scope and host concurrency. */
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
typedef SOCKET socket_t;
#define CLOSE closesocket
#else
#include <sys/socket.h>
#include <sys/select.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
typedef int socket_t;
#define INVALID_SOCKET (-1)
#define CLOSE close
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int number(const char *s, long low, long high, long *value) {
    char *end;
    if (!*s || strspn(s, "0123456789") != strlen(s)) return 0;
    *value = strtol(s, &end, 10);
    return !*end && *value >= low && *value <= high;
}

static int probe(struct sockaddr_storage *address, int length, int timeout) {
    socket_t fd = socket(address->ss_family, SOCK_STREAM, IPPROTO_TCP);
    if (fd == INVALID_SOCKET) return 0;
#ifdef _WIN32
    u_long nonblocking = 1;
    if (ioctlsocket(fd, FIONBIO, &nonblocking)) { CLOSE(fd); return 0; }
#else
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags < 0 || fcntl(fd, F_SETFL, flags | O_NONBLOCK) < 0) { CLOSE(fd); return 0; }
    if (fd >= FD_SETSIZE) { CLOSE(fd); return 0; }
#endif
    int connected = connect(fd, (struct sockaddr *)address, length) == 0;
    if (!connected) {
#ifdef _WIN32
        int error = WSAGetLastError();
        int pending = error == WSAEWOULDBLOCK || error == WSAEINPROGRESS;
#else
        int pending = errno == EINPROGRESS;
#endif
        if (pending) {
            fd_set write_set, error_set;
            FD_ZERO(&write_set); FD_ZERO(&error_set);
            FD_SET(fd, &write_set); FD_SET(fd, &error_set);
            struct timeval wait = {timeout / 1000, (timeout % 1000) * 1000};
            int ready = select((int)fd + 1, NULL, &write_set, &error_set, &wait);
            if (ready > 0) {
                int error = 0;
#ifdef _WIN32
                int size = sizeof(error);
                connected = getsockopt(fd, SOL_SOCKET, SO_ERROR, (char *)&error, &size) == 0 && error == 0;
#else
                socklen_t size = sizeof(error);
                connected = getsockopt(fd, SOL_SOCKET, SO_ERROR, &error, &size) == 0 && error == 0;
#endif
            }
        }
    }
    CLOSE(fd);
    return connected;
}

int main(int argc, char **argv) {
    long timeout;
    if (argc != 4 || !number(argv[3], 50, 10000, &timeout) || strlen(argv[2]) > 6143) {
        fprintf(stderr, "Usage: tcp-probe IP PORTS TIMEOUT_MS (50..10000)\n"); return 2;
    }
#ifdef _WIN32
    WSADATA data;
    if (WSAStartup(MAKEWORD(2, 2), &data)) return 1;
#endif
    struct sockaddr_storage address;
    memset(&address, 0, sizeof(address));
    struct sockaddr_in *v4 = (struct sockaddr_in *)&address;
    struct sockaddr_in6 *v6 = (struct sockaddr_in6 *)&address;
    int length;
    if (inet_pton(AF_INET, argv[1], &v4->sin_addr) == 1) {
        address.ss_family = AF_INET; length = sizeof(*v4);
    } else if (inet_pton(AF_INET6, argv[1], &v6->sin6_addr) == 1) {
        address.ss_family = AF_INET6; length = sizeof(*v6);
    } else { fprintf(stderr, "Expected a numeric IPv4 or IPv6 address\n"); return 2; }
    char ports_text[6144]; strcpy(ports_text, argv[2]);
    unsigned short ports[1024]; int count = 0;
    char *part = ports_text;
    do {
        char *comma = strchr(part, ',');
        if (comma) *comma = '\0';
        long port;
        if (count == 1024 || !number(part, 1, 65535, &port)) {
            fprintf(stderr, "Expected 1..1024 ports in range 1..65535\n"); return 2;
        }
        ports[count++] = (unsigned short)port;
        part = comma ? comma + 1 : NULL;
    } while (part);
    for (int i = 0; i < count; ++i) {
        if (address.ss_family == AF_INET) v4->sin_port = htons(ports[i]);
        else v6->sin6_port = htons(ports[i]);
        if (probe(&address, length, (int)timeout)) printf("%u\n", ports[i]);
    }
#ifdef _WIN32
    WSACleanup();
#endif
    return 0;
}
