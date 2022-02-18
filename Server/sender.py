#!/usr/bin/env python3
# coding: utf-8
from __future__ import division

import struct
import subprocess
from datetime import datetime
from io import BytesIO
from math import ceil
from socket import AF_INET, SOCK_DGRAM, socket
from threading import Thread

from cv2 import IMWRITE_JPEG_QUALITY, imencode
from paramiko import SSHClient, WarningPolicy
from picamera import PiCamera
from picamera.array import PiRGBArray
from telegram import Bot, ChatAction, ParseMode, Update
from telegram.ext import CallbackContext, CommandHandler, Updater


def helps(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    functions = [
        '<i>/start</i>', '<i>/stop</i>', '<i>/reboot1</i>',
        '<i>/reboot2</i>', '<i>/picture</i>', '<i>/status</i>']
    message = ", ".join(functions[:-1])

    update.message.reply_text(
        f"Commands for the <b>camera</b>:\n"
        f"{message} and {functions[-1]}.",
        parse_mode='HTML')


def reboot1(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /reboot1 is issued."""
    update.message.reply_text(
        "Got it. Rebooting the <b>camera</b>..",
        parse_mode='HTML')

    subprocess.run(["sudo", "reboot"])


def reboot2(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /reboot2 is issued."""
    update.message.reply_text(
        "Got it. Rebooting the <b>receiver</b>..",
        parse_mode='HTML')

    client = SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(WarningPolicy())
    client.connect(
        '192.168.3.13',
        port=22,
        username='pi',
        password='123')
    client.exec_command('sudo reboot')


def picture(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /picture is issued."""
    global send_picture

    send_picture = True
    update.message.reply_text(
        "<i>One moment.</i>",
        parse_mode='HTML')


def transfer_picture(image, channel):
    """Send a message when the command /picture is issued."""
    global bot

    time_now = datetime.now()
    date_ = time_now.strftime("%d.%m.%Y")
    time_ = time_now.strftime("%H:%M:%S")

    bot.sendChatAction(
        channel, action=ChatAction.UPLOAD_PHOTO)

    flag, image = imencode('.png', image)

    if flag:
        picture = BytesIO(image)
        picture.name = f"{date_}_{time_}.png"
        picture.seek(0)
        bot.send_photo(
            chat_id=channel,
            photo=picture,
            caption="The picture you wanted.",
        )

        print('Done sending the picture..')


def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    global stop_instance, is_not_running

    stop_instance = False

    if is_not_running:
        Thread(target=cam_runner).start()

    update.message.reply_text('Will try rebooting the camera.')


def stop(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /stop is issued."""
    global stop_instance, is_not_running

    if not is_not_running:
        stop_instance = True

    update.message.reply_text('Will try stopping the camera.')


def status(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /status is issued."""
    global stop_instance, is_not_running

    state = 'is off' if is_not_running else 'is on'
    update.message.reply_text(f"The camera {state}.")


class FrameSegment:
    """
    Object to break down image frame segment
    if the size of image exceed maximum datagram size
    """
    MAX_DGRAM = 2**16
    MAX_IMAGE_DGRAM = MAX_DGRAM - 64

    def __init__(self, sock, port, addr, quality):
        self.s = sock
        self.port = port
        self.addr = addr
        self.quality = [int(IMWRITE_JPEG_QUALITY), quality]

    def udp_frame(self, img):
        """
        Compress image and Break down
        into data segments
        """
        compress_img = imencode(
            '.jpg', img, self.quality)[1]
        dat = compress_img.tobytes()
        size = len(dat)
        count = ceil(size / (self.MAX_IMAGE_DGRAM))
        array_pos_start = 0
        while count:
            array_pos_end = min(size, array_pos_start + self.MAX_IMAGE_DGRAM)
            self.s.sendto(
                struct.pack("B", count) + dat[array_pos_start: array_pos_end],
                (self.addr, self.port)
            )
            array_pos_start = array_pos_end
            count -= 1


def cam_runner():
    global is_not_running, stop_instance, bot, bot_settings
    global send_picture

    with PiCamera() as camera:
        camera.resolution = (1280, 720)
        camera.framerate = 35
        rawCapture = PiRGBArray(
            camera, size=camera.resolution)
        remote = '192.168.1.13'
        port = 6666

        x = 'x'.join([str(v) for v in camera.resolution])
        channel = bot_settings.get('channel')
        bot.send_message(
            chat_id=channel,
            text=(
                f"The <b>camera</b> is ready to be used.\n"
                f"Remote flow: <b>{remote}:{port}</b>\n"
                f"with <b>{camera.framerate}</b> FPS/Sec.\n"
                f"Picture size is <b>{x}</b>.\n"),
            parse_mode=ParseMode.HTML)

        print(f"Pushing data to {remote}:{port}")
        print(f"Framerate is on {camera.framerate} FPS")
        print(f"Picture size is {x}")

        s = socket(AF_INET, SOCK_DGRAM)
        fs = FrameSegment(s, port, remote, quality=45)

        for frame in camera.capture_continuous(
            rawCapture,
            format="bgr",
            use_video_port=True
        ):
            image = frame.array
            fs.udp_frame(image)
            rawCapture.truncate(0)
            is_not_running = False

            if stop_instance:
                stop_instance = False
                is_not_running = True
                break

            if send_picture:
                send_picture = False
                Thread(
                    target=transfer_picture,
                    args=(image, channel, )
                ).start()

        s.close()


if __name__ == "__main__":
    send_picture = False
    stop_instance = False
    is_not_running = False

    bot_settings = {
        "token": "blablablaaaaaaaaaa",
        "channel": "-101010101010101",
        "allowed_users": [123456789]
    }
    bot = Bot(bot_settings.get('token'))
    bot.sendChatAction(
        bot_settings.get('channel'),
        action=ChatAction.TYPING)

    updater = Updater(bot_settings.get('token'), use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("help", helps))
    dispatcher.add_handler(CommandHandler("picture", picture))
    dispatcher.add_handler(CommandHandler("status", status))
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("stop", stop))
    dispatcher.add_handler(CommandHandler("reboot1", reboot1))
    dispatcher.add_handler(CommandHandler("reboot2", reboot2))
    updater.start_polling()
    # updater.idle()
    Thread(target=cam_runner).start()
