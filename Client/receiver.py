#! /usr/bin/python3
# coding: utf-8

from __future__ import division

import json
import logging
import os
import socket
from datetime import datetime
from socket import timeout as TimeoutException
from struct import unpack
from threading import Thread

import requests
from cv2 import flip, imdecode
from kivy.app import App
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.lang.builder import Builder
from kivy.properties import (BooleanProperty, ColorProperty, ListProperty,
                             NumericProperty, StringProperty)
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.effectwidget import EffectBase
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from numpy import frombuffer, uint8
from telegram import Bot, ChatAction, ParseMode

from lunar import lunar_phase

shader = """
// http://stackoverflow.com/a/21604810/1209937
// hash based 3d value noise
// function taken from https://www.shadertoy.com/view/XslGRr
// Created by inigo quilez - iq/2013
// License Creative Commons Attribution-NonCommercial-ShareAlike
// 3.0 Unported License.

// ported from GLSL to HLSL then back to GLSL

float hash( float n )
{
    return fract(sin(n)*43758.5453);
}

float noise(vec3 x)
{
    // The noise function returns a value in the range -1.0f -> 1.0f

    vec3 p = floor(x);
    vec3 f = fract(x);

    f       = f*f*(3.0-2.0*f);
    float n = p.x + p.y*57.0 + 113.0*p.z;

    return mix(
        mix(
            mix(hash(n+0.0), hash(n+1.0), f.x),
            mix(hash(n+57.0), hash(n+58.0),f.x),
            f.y
        ),
        mix(
            mix(hash(n+113.0), hash(n+114.0),f.x),
            mix(hash(n+170.0), hash(n+171.0),f.x),
            f.y
        ),
        f.z
    );
}
vec4 effect(vec4 color, sampler2D texture, vec2 tex_coords, vec2 coords){
   float val = noise(vec3(time / 15., coords.x / 600., coords.y / 400.));
   vec4 col1 = vec4(255./255., 155./255., 155./255., 1.);
   vec4 col2 = vec4(100.0/255., 20.0/255., 205.0/255., 1.);
   vec4 col3 = vec4(120.0/255., 200.0/255., 100.0/255., 1.);

   return color * (
        col1 * sin(mod(val, 1.)) +
        col2 * sin(mod(val+.3, 1.)) +
        col3 * sin(mod(val+.2, 1.)));
}
"""


def weather_api():
    try:

        api_key = "somethingwentwronghere"
        lat, lon = "60.020037", "22.500597"
        url = (
            f"https://api.openweathermap.org/data/2.5/onecall"
            f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        )

        response = requests.get(url)
        data = json.loads(response.text)["current"]

        temp = "{:0.0f}".format(data["temp"])
        icon = (
            f"https://openweathermap.org/img/wn/"
            f"{data['weather'][0]['icon']}@2x.png"
        )

    except Exception as error:
        logging.error(error)
        icon = "https://openweathermap.org/img/wn/50n@2x.png"
        temp = "-40"

    return icon, temp


Builder.load_string(
    """
<BoardText@Label>:
    font_name: './fonts/JosefinSans-Bold.ttf'
    font_size: 60
    size: self.texture_size
    size_hint: None, None
    outline_color: 0, 0, 0, .1
    outline_width: 2

<Weather>:
    pos_hint: {'center_x': .5, 'center_y': .5}
    size_hint: None, None
    size: 90, 90
    color: 1, 1, 1, .5
    font_size: 30
    canvas.before:
        Color:
            rgba: root.heat
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [50, ]

    FloatLayout:

        Label:
            pos_hint: {'top': 1.2, 'right': 1.2}
            size_hint: None, None
            size: self.texture_size
            padding: 4, 4
            markup: True
            text: "[b]{0}[/b]\u00b0".format(root.deg)
            font_size: 17
            color: 0, 0, 0, 1
            canvas.before:
                Color:
                    rgba: 1, 1, 1, .9
                RoundedRectangle:
                    size: self.size
                    pos: self.pos
                    radius: [20, ]


<Lunar>:
    pos_hint: {'center_x': .5, 'center_y': .5}
    size_hint: None, None
    size: 90, 90
    canvas.before:
        Color:
            rgba: .3, 1, .3, .5
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: [50, ]
    Image:
        size: 60, 60
        size_hint: None, None
        source: root.path
        canvas.before:
            Color:
                rgba: 0, 0, 0, .4
            RoundedRectangle:
                size: self.size
                pos: self.pos
                radius: [50, ]

<Picture>:
    Stream:
        id: streamer
        fps: 60

    EffectWidget:
        effects: root.effects

        Widget:
            opacity: 0 if streamer.ready else 1
            canvas.before:
                Color:
                    rgb: .2, .2, .2
                Rectangle:
                    size: self.size
                    pos: self.pos

    Label:
        text: 'Väntar på flödet från kameran..'
        font_name: './fonts/JosefinSans-Bold.ttf'
        opacity: 0 if streamer.ready else 1
        outline_color: 0, 0, 0, .1
        outline_width: 5
        font_size: 70
        color: 1, 1, 1, .9

    BoxLayout:
        size_hint: None, None
        size: 600, 230
        pos_hint: {'right': 1}
        padding: 15
        spacing: 5
        canvas.before:
            Color:
                rgba: .129, .129, .129, .5
            RoundedRectangle:
                size: self.size
                pos: self.pos
                radius: 30, 0, 0, 0

        Carousel:
            anim_move_duration: 2.5
            size_hint_x: None
            width: 160
            loop: True
            id: station

            Weather:
                id: weather

                AsyncImage:
                    id: weather_icon
                    size: 90, 90
                    size_hint: None, None
                    source: self.parent.path
                    canvas.before:
                        Color:
                            rgba: 0, 0, 0, .4
                        RoundedRectangle:
                            size: self.size
                            pos: self.pos
                            radius: [60, ]

            Lunar:
                id: lunar

                AsyncImage:
                    id: lunar_icon
                    size: 90, 90
                    size_hint: None, None
                    source: self.parent.path
                    canvas.before:
                        Color:
                            rgba: 0, 0, 0, .4
                        RoundedRectangle:
                            size: self.size
                            pos: self.pos
                            radius: [60, ]

        BoxLayout:
            orientation: 'vertical'
            spacing: 3

            BoardText:
                color: 1, 1, 1, .9
                text: 'LindCamV2'

            BoardText:
                id: date
                color: 1, 1, 1, .7
                text: '00.00.0000'
                font_size: 58

            BoardText:
                id: time
                color: 1, 1, 1, .5
                text: '00:00:00'
                font_size: 56

"""
)


class Weather(AnchorLayout):
    heat = ColorProperty((0.3, 0.3, 1, 0.5))
    path = StringProperty("")
    deg = StringProperty("")


class Lunar(AnchorLayout):
    path = StringProperty("")


class Picture(FloatLayout):
    effects = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.effects = [EffectBase(glsl=shader)]


class Stream(Image):
    color = ColorProperty((0, 0, 0, 1))
    allow_stretch = BooleanProperty(True)
    nocache = BooleanProperty(True)
    fps = NumericProperty(60)
    ready = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.MAX_DGRAM = 2 ** 16
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(("0.0.0.0", 6666))
        self.s.settimeout(5)
        self.buffer = b""
        Thread(target=self.update).start()

    def update(self, dt=None):

        try:
            seg, addr = self.s.recvfrom(self.MAX_DGRAM)

            if unpack("B", seg[0:1])[0] in (0, 1):
                Clock.schedule_once(self.set_image, -1)
                Clock.schedule_once(self.update, 0)

            else:
                self.buffer += seg[1:]

        except TimeoutException:
            self.set_ready_state(False)
            Thread(target=self.update).start()

        except Exception as error:
            logging.critical(error)

    def set_image(self, *largs):
        frame = imdecode(frombuffer(self.buffer, dtype=uint8), 1)
        buf1 = flip(frame[:, :, ::-1], 0)
        buf = buf1.tobytes()
        image_texture = Texture.create(
            size=(frame.shape[1], frame.shape[0]), colorfmt="rgb"
        )
        image_texture.blit_buffer(
            buf,
            colorfmt="rgb",
            bufferfmt="ubyte"
        )
        self.texture = image_texture
        self.set_ready_state(True)
        self.buffer = b""

    def set_ready_state(self, b=False):
        self.color = (b, b, b, b)
        self.ready = b


class CamApp(App):
    color_base = {
        "cold": (0.3, 0.3, 1, 0.5),
        "warmer": (0.5, 0.5, 1, 0.8),
        "warm": (0.3, 1, 0.3, 0.5),
        "hot": (1, 1, 0, 0.8),
    }
    deg_base = {
        "cold": [str(x) for x in range(-40, 0)],
        "warmer": [str(x) for x in range(0, 19)],
        "warm": [str(x) for x in range(19, 27)],
        "hot": [str(x) for x in range(27, 61)],
    }

    def build(self):
        self.root = Picture()
        Thread(target=self.setup).start()

        return self.root

    def setup(self, dt=None):
        # Clock.schedule_once(self.check_weather, 0)
        Clock.schedule_once(self.check_lunar, 0)
        Clock.schedule_interval(self.check_weather, 7200)
        Clock.schedule_interval(self.check_lunar, 7200)
        Clock.schedule_interval(self.time_set, 1)
        Clock.schedule_once(self.card_looper, 540)

        bot.sendChatAction(
            bot_settings.get("channel"), action=ChatAction.TYPING)
        bot.send_message(
            chat_id=bot_settings.get("channel"),
            text="<b>Reciver</b> is ready to be used.",
            parse_mode=ParseMode.HTML,
        )

    def check_weather(self, dt):

        try:
            ids = self.root.ids
            weather = ids.weather
            weather.path, weather.deg = weather_api()

            colors = [
                self.color_base[i]
                for i, x in self.deg_base.items()
                if weather.deg in x
            ][0]

            weather.heat = colors
            ids.weather_icon.reload()

        except Exception as error:
            logging.error(error)

    def check_lunar(self, dt):
        lunar_ = os.path.join("./icons/lunar", lunar_phase())
        ids = self.root.ids
        ids.lunar.path = lunar_
        ids.lunar_icon.reload()

    def card_looper(self, dt):
        station = self.root.ids.station
        station.load_next()

        Clock.schedule_once(
            self.card_looper, 30 if station.index % 2 == 0 else 540)

    def time_set(self, dt):
        time_now = datetime.now()
        target = self.root.ids

        target.date.text = time_now.strftime("%d.%m.%Y")
        target.time.text = time_now.strftime("%H:%M:%S")


if __name__ == "__main__":
    bot_settings = {
        "token": "blablablablaaaaaaa",
        "channel": "-10101010101010",
        "allowed_users": [123456789]
    }

    bot = Bot(bot_settings.get("token"))
    CamApp().run()
