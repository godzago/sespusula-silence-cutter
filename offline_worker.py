"""Acceptance worker: fail on all attempted outbound socket connections."""
import socket


def blocked(*args,**kwargs):
    raise RuntimeError('Çevrimdışı test sırasında ağ bağlantısı denendi.')


socket.socket.connect=blocked
socket.socket.connect_ex=blocked
socket.create_connection=blocked

from speech_worker import main
main()
