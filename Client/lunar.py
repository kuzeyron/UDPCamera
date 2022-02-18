#! /usr/bin/python3
'''
    lunar.py - Calculate Lunar Phase
    Author: Sean B. Palmer, inamidst.com
    Cf. http://en.wikipedia.org/wiki/Lunar_phase#Lunar_phase_calculation
'''
import datetime
import decimal
import math

dec = decimal.Decimal


def position(now=None):
    if now is None:
        now = datetime.datetime.now()

    diff = now - datetime.datetime(2001, 1, 1)
    days = dec(diff.days) + (dec(diff.seconds) / dec(86400))
    lunations = dec("0.20439731") + (days * dec("0.03386319269"))

    return lunations % dec(1)


def phase(pos):
    index = (pos * dec(8)) + dec("0.5")
    index = math.floor(index)
    return {
        0: "wi-moon-alt-full",
        1: "wi-moon-waxing-crescent-3",
        2: "wi-moon-alt-third-quarter",
        3: "wi-moon-waning-crescent-3",
        4: "wi-moon-alt-new",
        5: "wi-moon-alt-waxing-crescent-4",
        6: "wi-moon-alt-first-quarter",
        7: "wi-moon-waning-crescent-3"
    }[int(index) & 7]


def lunar_phase():

    return f"{phase(position())}.png"


def main():
    pos = position()
    phasename = phase(pos)

    roundedpos = round(float(pos), 3)
    print("%s (%s)" % (phasename, roundedpos))


if __name__ == '__main__':
    main()
