# MTB
 Midi To Blender

Here the code MTB to create some animations from MIDI file as input.

Note : this script use the MIDO Python module
How to install a new python module in the blender (here mido) :
http://www.codeplastic.com/2019/03/12/how-to-install-python-modules-in-blender/
Mido is a library for working with MIDI messages and ports.
It’s designed to be as straight forward and Pythonic as possible:
https://mido.readthedocs.io/en/latest/installing.html

This script work with some input files and these lines allow you to choose them :

path and name of midi file - temporary => replaced when this become an add-on
path = "C:\\tmp\\MTB\\data"
path = "D:\\OneDrive\\Blog\\MTB\\data"
filename = "Melody 01"
If use_channel = True then manage separate channel as usual, wherever the tracks where the channel event are
If use_channel = False then MIDI File don't use channel info and we use 1 track = 1 channel
use_channel = False
filemid = path + "\\" + filename + ".mid"
fileaudio = path + "\\" + filename + ".mp3"
filejson = path + "\\" + filename + ".json"
filelog = path + "\\" + filename + ".log"
