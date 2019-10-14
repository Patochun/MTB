import bpy
from mathutils import *

# for material
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper

import numpy as np
import math
import random
import time
import os
import os.path

# How to install a new python module in the blender (here mido) :
# http://www.codeplastic.com/2019/03/12/how-to-install-python-modules-in-blender/
# Mido is a library for working with MIDI messages and ports.
# It’s designed to be as straight forward and Pythonic as possible:
# https://mido.readthedocs.io/en/latest/installing.html
import mido
from mido import MidiFile

b_dat = bpy.data
b_con = bpy.context
b_scn = b_con.scene
b_ops = bpy.ops

# ********************************************************************
# Midi_To_Blend
# version = 1.003
# Blender version = 2.8
# Author = Patrick Mauger
# Web Site = docouatzat.com
# Mail = docouatzat@gmail.com
#
# Licence used = Creative Commons CC BY
# Check licence here : https://creativecommons.org
#
# Generate 3D animations from midifile
# ********************************************************************


def find_collection(context, item):
    """ Research an existing collection
    IN
        context     obj     Context, almost always C (bpy.context)
        item        obj     Object
    OUT
                    obj     The collection founded or
                            the master collection if not
    """
    collections = item.users_collection
    if len(collections) > 0:
        return collections[0]
    return context.scene.collection


def create_collection(collection_name, parent_collection, delete):
    """ Create collection
    IN
        collection_name     str         The name of new collection
        parent_collection   obj         Parent Collection
        delete              boolean     If True then delete if already exist
                                        before create
    OUT
                            obj         The new collection created
    """
    if collection_name in bpy.data.collections:
        collection = bpy.data.collections[collection_name]
        if delete:
            for ob in collection.objects:
                bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.collections.remove(collection)
        else:
            return bpy.data.collections[collection_name]
    new_collection = bpy.data.collections.new(collection_name)
    parent_collection.children.link(new_collection)
    return new_collection


def add_cube(collect, Name, x, y, z, mat):
    """ Create a Cube Mesh
    IN
        collect     obj     collection
        name        str     name of created cube
        x, y, z     float   coordinates
        mat         obj     material
    OUT
        The object cube created
    """

    bpy.ops.mesh.primitive_cube_add(enter_editmode=False, location=(x, y, z))

    # ToDO remark : Assume the last cube created is named "cube"
    # because this name is free... Dangerous
    obj = bpy.data.objects.get("Cube")
    obj.name = Name

    collect_to_unlink = find_collection(b_con, obj)
    collect.objects.link(obj)
    collect_to_unlink.objects.unlink(obj)

    return obj

""" ========================= Class ========================= """


class Track_Class:

    # Track initializations
    def __init__(self, idx_track, track, name, visual_type):
        self.idx = idx_track            # Set the index number
        self.name = name                # mean the name or description
        self.visual_type = visual_type  # mean the type of visualization
        self.track = track
        self.last_note_status = {}      # dictionnary {note:status}
        self.BGLocCoef = 2.5            # localisation coef for BG type

        self.list_note = []
        min_note = 128
        max_note = 0
        # Know notes used in track
        for msg in track:
            if (msg.type == 'note_on'):
                if msg.note not in self.list_note:
                    self.list_note.append(msg.note)
                    self.last_note_status[msg.note] = 0
                if msg.note < min_note:
                    min_note = msg.note
                if msg.note > max_note:
                    max_note = msg.note

        # Type BG = Bargraphs
        if self.visual_type == "BG":
            # Create cubes from only used notes
            scn.frame_current = 1
            for x in range(min_note, max_note + 1):
                if x in self.list_note:
                    cube_name = 'BG_' + str(self.idx) + "_" + str(x)
                    add_cube(nCol, cube_name, x * self.BGLocCoef,
                             self.idx * self.BGLocCoef, 0, mat_c)
                    obj = bpy.data.objects[cube_name]
                    obj.scale = 1.0, 1.0, 1.0
                    obj.keyframe_insert('scale')
        elif self.visual_type == "GRID":
            pass

    # Add an new midi event related to the track
    def add_evt(self, evt, frame, note, velocity):

        def BG_note_on(Frame, Note, Velocity):
            """ BG = Bargraphs
            Place note_on with Track object, velocity and keyframe
            IN
                Frame       int     Index of frame
                Track       int     Track number
                Note        int     Note number (0-127)
                Velocity    int     Note on Velocity
            OUT
                None
            """
            cube_name = 'BG_' + str(self.idx) + "_" + str(Note)

            # To avoid bargraphs slowly grow before the note
            if self.last_note_status[Note] == 0:
                BG_note_off(Frame - 1, Note)

            scn.frame_current = Frame
            obj = bpy.data.objects[cube_name]
            obj.scale = 1.0, 1.0, (Velocity / 8) + 1.0
            obj.keyframe_insert('scale')
            obj.location = Note * self.BGLocCoef, self.idx * self.BGLocCoef, (Velocity / 8)
            obj.keyframe_insert('location')

            self.last_note_status[Note] = velocity
            return None

        def BG_note_off(Frame, Note):
            """ BG = Bargraphs
            Place note_off with object and keyframe
            IN
                Frame       int     Index of frame
                Track       int     Track number
                Note        int     Note number (0-127)
            OUT
                None
            """
            cube_name = 'BG_' + str(self.idx) + "_" + str(Note)

            # To avoid bargraphs slowly grow before the note
            if self.last_note_status[Note] != 0:
                BG_note_on(Frame - 1, Note, self.last_note_status[Note])

            scn.frame_current = Frame
            obj = bpy.data.objects[cube_name]
            obj.scale = 1.0, 1.0, 1.0
            obj.keyframe_insert('scale')
            obj.location = Note * self.BGLocCoef, self.idx * self.BGLocCoef, 0
            obj.keyframe_insert('location')

            self.last_note_status[Note] = velocity
            return None

        # Main - add_evt
        if self.visual_type == "BG":
            if evt == 'note_on':
                BG_note_on(frame, note, velocity)
            elif evt == 'note_off':
                BG_note_off(frame, note)
        elif self.visual_type == "GRID":
            pass

        return None


""" ========================= MAIN ========================= """

# Clear system console
os.system("cls")
col_name = "MTB"  # mean Midi To Blender

# Create a new collection even if already exist
nCol = create_collection(col_name, b_con.scene.collection, delete=True)

# Create materials for cubes
# Cube body
mat_c = bpy.data.materials.new(name="Material_Cube")
mat_c.use_nodes = True
principled = PrincipledBSDFWrapper(mat_c, is_readonly=False)
principled.base_color = (0.8, 0.4, 0.2)

# path = "H:\\Python\\MTB\\data"
path = "D:\\OneDrive\\Blog\\YT_Patrick Mauger\\02 - Midi_To_Blend\\MTB\\data"
filename = "T1_Classic"
filemid = path + "\\" + filename + ".mid"
fileaudio = path + "\\" + filename + ".mp3"

if os.path.exists(fileaudio):

    if not b_scn.sequence_editor:
        b_scn.sequence_editor_create()

    #clear the VSE, then add an audio file
    b_scn.sequence_editor_clear()
    my_contextmem = b_con.area.type
    print(str(my_contextmem))
    my_context = 'SEQUENCE_EDITOR'
    b_con.area.type = my_context
    my_context = b_con.area.type
    print(str(my_context))
    b_ops.sequencer.sound_strip_add(filepath=fileaudio, relative_path=True, frame_start=1, channel=1)
    print("loaded new sound ",fileaudio)
    b_con.area.type = my_contextmem
    my_context = b_con.area.type
    print(str(my_context))

    # Sequences.new_sound(name, filepath, channel, frame_start)
#    soundstrip = b_scn.sequence_editor.sequences.new_sound("coolname", "fileaudio", 1, 1)

# Open MIDIFile with the module MIDO
mid = MidiFile(filemid)
print(mid)

# type = 0 - (single track): all messages are saved in one track
# type = 1 - (synchronous): all tracks start at the same time
# type = 2 - (asynchronous): each track is independent of the others
if (mid.type != 1):
    print('not type 1 midifile')
    raise RuntimeError("Only type 1")

# Set some variables
PPQ = mid.ticks_per_beat
print(PPQ)

# Tb_Notes for memorize some informations.
# The first index mean :
# 0 => Memorize if this note is used
# 1 => Contain the last velocity encountered
Tb_Notes = np.zeros((2, 32, 128), dtype=int)
Tb_Notes.fill(0)

# Tb_Tempo for memorize tempo informations.
# The first index mean :
# 0 => Time to apply tempo
# 1 => Tempo
Tb_Tempo = np.zeros((2, 5000), dtype=int)
Tb_Tempo.fill(0)

Nb_Track = -1
scn = b_con.scene
Max_Num_Frame = 0
# FrameRate = 100
FrameRate = b_con.scene.render.fps

# Fill Tb_Tempo with Tempo into track 0
# For type 1 midifile only
track = mid.tracks[0]
Nb_Tempo = 0
DTempo = {}
for msg in track:
    print(msg)
    print(msg.type)
    if msg.type == 'set_tempo':
        Nb_Tempo += 1
        Tb_Tempo[0, Nb_Tempo] = msg.time
        Tb_Tempo[1, Nb_Tempo] = msg.tempo
        DTempo[msg.time] = msg.tempo

ListTempoTime = sorted(DTempo.keys())
Nb_Tempo = len(DTempo)
print(Nb_Tempo)
print(DTempo)
print(ListTempoTime)

# List of Track <= receive object Track_Class
TrackList = []

# Main LOOP on midifile track
for i, track in enumerate(mid.tracks):
    print('Track {}: {}'.format(i, track.name))

    Nb_Track += 1

    # Instancing Track Object
    TrackList.append(Track_Class(Nb_Track, track, track.name, "BG"))

    TimePos = 0
    Tempo = Tb_Tempo[1, 0]
    Tempo = DTempo[ListTempoTime[0]]
#    print(ListTempoTime[0], Tempo)

    Next_Tempo = 1
    TpsSecCumul = 0

    # create Msg in DB following their types
    for msg in track:

        # Set the object linked with note to the velocity at the right time
        TimePos = TimePos + msg.time

        # Check if Tempo need to be changed
        if Next_Tempo < Nb_Tempo:
            if TimePos > ListTempoTime[Next_Tempo]:
                Tempo = DTempo[ListTempoTime[Next_Tempo]]
#                print( Next_Tempo, ListTempoTime[Next_Tempo], Tempo)
                Next_Tempo += 1

        TpsSec = mido.tick2second(msg.time, PPQ, Tempo)
        TpsSecCumul += TpsSec
        Num_Frame = int(TpsSecCumul * FrameRate)

#        print(TimePos, TpsSec, Num_Frame)

        # note_on and note_off => no msg in DB, just values in usual columns
        if (msg.type == 'note_on') and (msg.velocity == 0):
            msgtype = 'note_off'
        else:
            msgtype = msg.type

        # note_on
        if (msgtype == 'note_on'):
            TrackList[Nb_Track].add_evt(msgtype, Num_Frame, msg.note, msg.velocity)

        # note_off (or note_on with velocity=0)
        elif (msgtype == 'note_off'):
            TrackList[Nb_Track].add_evt(msgtype, Num_Frame, msg.note, 0)

        # control_change => no msg in DB, just values with control into note column and velocity = 0
#        if (msgtype == 'control_change'):
#            print(msg)
#            MIDIMSG = (i,str(msg),MSG_Type_to_Int(msg.type),msg.channel,msg.control,msg.time,msg.value)
        # program_change => no msg in DB, just values with program into note column and velocity = 0
#        if (msgtype == 'program_change'):
#            print(msg)
#            MIDIMSG = (i,str(msg),MSG_Type_to_Int(msg.type),msg.channel,msg.program,msg.time,0)
        # program_change => no msg in DB, just values with pitch into note column and velocity = 0
#        if (msgtype == 'pitchwheel'):
#            print(msg)
#            MIDIMSG = (i,str(msg),MSG_Type_to_Int(msg.type),msg.channel,msg.pitch,msg.time,0)
        # meta time_signature => no msg in DB, just values with pitch into note column and velocity = 0
        # change morphology of beat
        # for evaluating the number of beat with the notes flow

        # meta set_tempo => no msg in DB, just values with pitch into note column and velocity = 0
        # change just speed of beat

        # else msg in DB, values to 0 in rest of columns
#        else:
#            print(msg)
#            MIDIMSG = (i,str(msg),0,0,0,0,0)

    # Manage the last frame number for all tracks
    if Num_Frame > Max_Num_Frame:
        Max_Num_Frame = Num_Frame

scn.frame_end = Max_Num_Frame + 25

print('game over')

#    raise RuntimeError("Stopping the script here")


# End of script - Enjoy
