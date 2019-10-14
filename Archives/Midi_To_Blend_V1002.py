import bpy
from mathutils import *
D = bpy.data
C = bpy.context

# for material
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper

import numpy as np
import math
import random
import time
import os

# How to install a new module in the blender python (here mido) :
# http://www.codeplastic.com/2019/03/12/how-to-install-python-modules-in-blender/
# Mido is a library for working with MIDI messages and ports. It’s designed to be as straight forward and Pythonic as possible:
# https://mido.readthedocs.io/en/latest/installing.html
import mido
from mido import MidiFile

# ********************************************************************
# Midi_To_Blend
# version = 1.002
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

# Research about a collection
# IN
#   context             obj         Context, almost always C (bpy.context)
#   item                obj         Object
# OUT
#                       obj         The collection founded or the master collection if not
def find_collection(context, item):
    collections = item.users_collection
    if len(collections) > 0:
        return collections[0]
    return context.scene.collection

# Create collection
# IN
#   collection_name     str         The name of new collection
#   parent_collection   obj         Parent Collection
#   delete              boolean     If True then delete if already exist before create
# OUT
#                       obj         The new collection created
def create_collection(collection_name, parent_collection, delete):
    if collection_name in bpy.data.collections:
        mycol = bpy.data.collections[collection_name]
        if delete:
            for ob in mycol.objects:
                bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.collections.remove(mycol)
        else:
            return bpy.data.collections[collection_name]
    new_collection = bpy.data.collections.new(collection_name)
    parent_collection.children.link(new_collection)
    return new_collection

# Create a Cube Mesh
# IN
#   collect             obj         collection
#   name                str         name of created cube
#   x, y, z             float       coordinates
#   mat                 obj         material
# OUT
#   The object cube created
def Add_Cube(collect, Name, x, y, z, mat):

    bpy.ops.mesh.primitive_cube_add(enter_editmode=False, location=(x* 2.5, y * 2.5, z * 2.5))

    # Assume the last cube created is named "cube" because this name is free
    obj = bpy.data.objects.get("Cube")
    obj.name = Name

    collect_to_unlink = find_collection(C, obj)
    collect.objects.link(obj)
    collect_to_unlink.objects.unlink(obj)

    return obj

# Place note_on with Track object, velocity and keyframe
# IN
#   Frame               int         Index of frame
#   Track               int         Track number
#   Note                int         Note number (0-127)
#   Velocity            int²        Note on Velocity
# OUT
#   
def note_on( Frame, Track, Note, Velocity):

    Obj_Name = 'c_' + str(Track) + "_" + str( Note)

    # To avoid bargraphs slowly grow before the note
    if Tb_Notes[ 1, Track, Note] == 0:
        note_off( Frame - 1, Track, Note)
    
    scn.frame_current = Frame
    obj = bpy.data.objects[Obj_Name]
    obj.scale = 1.0, 1.0, (Velocity / 8) + 1.0
    obj.keyframe_insert('scale')

    Tb_Notes[ 1, Track, Note] = Velocity

# Place note_off with object and keyframe
# IN
#   Frame               int         Index of frame
#   Track               int         Track number
#   Note                int         Note number (0-127)
# OUT
#   
def note_off( Frame, Track, Note):

    Obj_Name = 'c_' + str(Track) + "_" + str( Note)

    # To avoid bargraphs slowly grow before the note
    if Tb_Notes[ 1, Track, Note] != 0:
        note_on( Frame - 1, Track, Note, Tb_Notes[ 1, Track, Note])

    scn.frame_current = Frame
    obj = bpy.data.objects[Obj_Name]
    obj.scale = 1.0, 1.0, 1.0
    obj.keyframe_insert('scale')

    Tb_Notes[ 1, Track, Note] = 0


# ------------------
# MAIN
# ------------------

# Clear system console
os.system("cls")
Col_Name = "BarGraphs"


# bpy.ops.transform.translate(value=(1, 1, 1))

# Create a new collection even if already exist
nCol = create_collection(Col_Name, C.scene.collection, delete=True)
#raise RuntimeError("Debug 1")

# Create materials for cubes
# Cube body
mat_c = bpy.data.materials.new(name="Material_Cube")
mat_c.use_nodes = True
principled = PrincipledBSDFWrapper(mat_c, is_readonly=False)
principled.base_color = (0.8, 0.4, 0.2)

path = "H:\\Python\\MTB\\data"
file = "T1_VT_Medley_Rock.mid"
filename = path + '\\' + file

# Open MIDIFile with the module MIDO
mid = MidiFile(filename)
print(mid)

# type = 0 - (single track): all messages are saved in one track
# type = 1 - (synchronous): all tracks start at the same time
# type = 2 - (asynchronous): each track is independent of the others
if (mid.type != 1):
    print( 'not type 1 midifile')
    raise RuntimeError("Only type 1")

# Set some variables
PPQ = mid.ticks_per_beat
print(PPQ)

# Tb_Notes for memorize some informations.
# The first index mean :
# 0 => Memorize if this note is used
# 1 => Contain the last velocity encountered
Tb_Notes = np.zeros((2,32,128),dtype=int)
Tb_Notes.fill(0)

# Tb_Tempo for memorize tempo informations.
# The first index mean :
# 0 => Time to apply tempo
# 1 => Tempo
Tb_Tempo = np.zeros((2,5000),dtype=int)
Tb_Tempo.fill(0)

Nb_Track = 0
scn = C.scene
Max_Num_Frame = 0
FrameRate = 100

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
        Tb_Tempo[ 0, Nb_Tempo] = msg.time
        Tb_Tempo[ 1, Nb_Tempo] = msg.tempo
        DTempo[msg.time]=msg.tempo

ListTempoTime = sorted(DTempo.keys())
Nb_Tempo = len( DTempo)
print(Nb_Tempo)
print(DTempo)
print(ListTempoTime)

# Main LOOP on midifile track
for i, track in enumerate(mid.tracks):
    print('Track {}: {}'.format(i, track.name))

    # Search if exist at least on 'note_on' msg in the track
    # And search the min note and the max note
    min_note = 128
    max_note = 0
    Exist_Note_In_Track = False
    for msg in track:
        if (msg.type == 'note_on'):
            Exist_Note_In_Track = True
            # Mark this note as used
            Tb_Notes[ 0, i, msg.note] = -1
            # Mark this note as used
            if msg.note < min_note:
                min_note = msg.note
            if msg.note > max_note:
                max_note = msg.note

    # So if not exist, continue with next track
    if not Exist_Note_In_Track:
        continue

    Nb_Track += 1

    # Do only for the track 10 (Test purpose)
#    if i != 0:
#        continue

    # Create one line of 127 cubes for the track
    # Create only used notes
    for x in range(min_note, max_note + 1):
        if Tb_Notes[ 0, i, x] == -1:
            Add_Cube(nCol, 'c_' + str(i) + "_" + str(x), x, i, 0, mat_c)

    # Fix all objects in start state = normal
    scn.frame_current = 1
    for x in range(min_note, max_note + 1):
        if Tb_Notes[ 0, i, x] == -1:
            Obj_Name = 'c_' + str(i) + "_" + str(x)
            obj = bpy.data.objects[Obj_Name]
            obj.scale = 1.0, 1.0, 1.0
            obj.keyframe_insert('scale')

    TimePos = 0
    Tempo = Tb_Tempo[ 1, 0]
    Tempo = DTempo[ ListTempoTime[0]]
#    print( ListTempoTime[0], Tempo)

    Next_Tempo = 1
    TpsSecCumul = 0

    # create Msg in DB following their types
    for msg in track:
#        print(msg)

        # Set the object linked with note to the velocity at the right time
        TimePos = TimePos + msg.time
        
        # Check if Tempo need to be changed
        if Next_Tempo < Nb_Tempo:
            if TimePos > ListTempoTime[Next_Tempo]:
                Tempo = DTempo[ ListTempoTime[Next_Tempo]]
#                print( Next_Tempo, ListTempoTime[Next_Tempo], Tempo)
                Next_Tempo += 1
        
        TpsSec = mido.tick2second( msg.time, PPQ, Tempo)
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
            note_on( Num_Frame, i, msg.note, msg.velocity)

        # note_off (or note_on with velocity=0)
        elif (msgtype == 'note_off'):
            note_off( Num_Frame, i, msg.note)

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
