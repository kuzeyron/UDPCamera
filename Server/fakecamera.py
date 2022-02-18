#!/usr/bin/env python3
# coding: utf-8
from __future__ import division

import struct
from math import ceil
from socket import AF_INET, SOCK_DGRAM, socket

import cv2
from imutils.video import FPS


class FrameSegment:
    """
    Object to break down image frame segment
    if the size of image exceed maximum datagram size
    """

    MAX_DGRAM = 2 ** 16
    MAX_IMAGE_DGRAM = MAX_DGRAM - 64

    def __init__(self, sock, port, addr, quality):
        self.s = sock
        self.port = port
        self.addr = addr
        self.quality = [int(cv2.IMWRITE_JPEG_QUALITY), quality]

    def udp_frame(self, img):
        """
        Compress image and Break down
        into data segments
        """
        compress_img = cv2.imencode(
            '.jpg', img, self.quality
        )[1]

        dat = compress_img.tobytes()
        size = len(dat)
        count = ceil(size / self.MAX_IMAGE_DGRAM)
        start = 0

        while count:
            end = min(
                size, start + self.MAX_IMAGE_DGRAM
            )
            self.s.sendto(
                struct.pack("B", count) + dat[start: end],
                (
                    self.addr,
                    self.port
                )
            )
            start = end
            count -= 1


if __name__ == "__main__":
    remote = '192.168.3.8'
    port = 6666

    s = socket(AF_INET, SOCK_DGRAM)
    fs = FrameSegment(s, port, remote, quality=30)

    cap = cv2.VideoCapture('/home/user/Videos/test.mp4')

    fps = FPS().start()

    while(cap.isOpened()):
        ret, image = cap.read()

        if ret:
            image = cv2.resize(
                image, (1280, 720), interpolation=cv2.INTER_AREA
            )
            fs.udp_frame(image)
            cv2.imshow('Frame', image)

        else:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        fps.update()

    fps.stop()
    print('FPS:', fps.fps())
    s.close()
