import sys, select, socket, time
HOST = '127.0.0.1'
PORT = 8888


mySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    mySocket.bind((HOST, PORT))
except socket.error:
    sys.exit('call to bind fail')

mySocket.listen(10)
(conn, addr) = mySocket.accept()
while True:
    data = conn.recv(1024)
    if not data:
        break
    conn.send(data)


#if fd:
    #print fd[0]
    #(clientsocket, address) = fd[0].accept()
    #clientsocket.close()

#conn, addr = mySocket.accept()
#while True:
#    data = conn.recv(10240)
#    if not data: 
#        break

#    conn.send(data)
#conn.close()


#socket.gethostname()