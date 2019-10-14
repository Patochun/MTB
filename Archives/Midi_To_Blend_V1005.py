import bpy
import bmesh
#from mathutils import *
import mathutils

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
# version = 1.005
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
        context     obj     Context, almost always b_con
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
    if collection_name in b_dat.collections:
        collection = b_dat.collections[collection_name]
        if delete:
            for ob in collection.objects:
                b_dat.objects.remove(ob, do_unlink=True)
            b_dat.collections.remove(collection)
        else:
            return b_dat.collections[collection_name]
    new_collection = b_dat.collections.new(collection_name)
    parent_collection.children.link(new_collection)
    return new_collection


def assign_to_collection(collect, obj):
    """ Assign an object to a collection
    IN
        collect     obj     collection
        obj         obj     object
    OUT
        None
    """
    collect_to_unlink = find_collection(b_con, obj)
    collect.objects.link(obj)
    collect_to_unlink.objects.unlink(obj)
    return None


def add_empty(collect, Name, x, y, z):
    """ Create a Cube Mesh
    IN
        collect     obj     collection
        name        str     name of created empty
        x, y, z     float   coordinates
    OUT
        The object cube created
    """

    b_ops.object.empty_add(type='PLAIN_AXES', location=(x, y, z))

    # ToDO remark : Assume the last cube created is named "Empty"
    # because this name is free... Dangerous
    obj_empty = b_dat.objects.get("Empty")
    obj_empty.name = Name
    assign_to_collection(collect, obj_empty)

    return obj_empty


def add_cube(collect, Name, x, y, z, mat, empty_parent):
    """ Create a Cube Mesh
    IN
        collect     obj     collection
        name        str     name of created cube
        x, y, z     float   coordinates
        mat         obj     material
    OUT
        The object cube created
    """
    b_ops.mesh.primitive_cube_add(enter_editmode=False, location=(x, y, z))

    # ToDO remark : Assume the last cube created is named "Cube"
    # because this name is free... Dangerous
    obj_cube = b_dat.objects.get("Cube")
    obj_cube.name = Name
    obj_cube.parent = empty_parent
    assign_to_collection(collect, obj_cube)

    return obj_cube

def add_grid(collect, Name, x, y, z, mat, sx, sy, list_note):
    """ Create a Grid Mesh and 127 empty hooked to 127 faces
    IN
        collect     obj     collection
        name        str     name of created cube
        x, y, z     float   coordinates
        mat         obj     material
        sx          int     subdivisions x
        sy          int     subdivisions y
        list_note   list    list of used notes
    OUT
        The object grid created
    """

    # Create collection for this track
    col_obj = create_collection(Name, collect, delete=True)

    # Create the empty parent off all Hook
    empty_parent_name = 'GD_' + Name + '_Parent'
    empty_parent = add_empty(col_obj, empty_parent_name, 0, 0, 0)

    b_ops.mesh.primitive_grid_add(x_subdivisions=sx, y_subdivisions=sy, size=64, enter_editmode=False, location=(x, y, z))

    # ToDO remark : Assume the last grid created is named "Grid"
    # because this name is free... Dangerous
    obj_grid = b_dat.objects.get("Grid")
    obj_grid.name = Name
    assign_to_collection(col_obj, obj_grid)
    empty_parent.parent = obj_grid

    # Add 127 hook for 127 notes on faces
    me = obj_grid.data
    for x in range (1,127):
        if x not in list_note:
            continue
        b_ops.object.mode_set(mode="EDIT")
        b_ops.mesh.select_all(action='DESELECT')  
        b_ops.object.mode_set(mode="OBJECT")
        # Math to distribute the hook with harmony on faces
        num_face = ((x * 3 - 2) + ((( (x - 1) // 12) + 1) * 72)) - 36
        # notice in Bmesh polygons are called faces
        # select vertice
        b_dat.meshes[me.name].polygons[num_face].select = True
        b_ops.object.mode_set(mode="EDIT")
        b_ops.object.hook_add_newob()
        obj_empty = b_dat.objects.get("Empty")
        obj_empty.name = Name + "_note_" + str(x)
        obj_empty.parent = empty_parent
        assign_to_collection(col_obj, obj_empty)

        b_ops.object.mode_set(mode="OBJECT")
    return obj_grid


def add_light(collect, Name, x, y, z):
    """ Create a Light
    IN
        collect     obj     collection
        name        str     name of created cube
        x, y, z     float   coordinates
    OUT
        The object light created
    """

    # create light datablock, set attributes
    obj_data = b_dat.lights.new(name=Name, type='POINT')
    obj_data.energy = 0  # mean no note velocity at this time

    # create new object with our light datablock
    obj_light = b_dat.objects.new(name=Name, object_data=obj_data)
    obj_light.location = (x, y, z)

    b_con.view_layer.active_layer_collection.collection.objects.link(obj_light)
    assign_to_collection(collect, obj_light)

    return obj_light


""" ========================= Class ========================= """


class Track_Class:

    # Track initializations
    def __init__(self, idx_track, track, name, visual_type, note_ref):
        self.idx = idx_track            # Set the index number
        self.name = name                # mean the name or description
        self.visual_type = visual_type  # mean the type of visualization
        self.note_ref = note_ref        # note_ref for mono note type of object (LT)
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
            col_name = 'BG_' + str(self.idx)
            # Create collection for this track
            col_obj = create_collection(col_name, new_collec, delete=True)
            # Create the empty parent off all cubes
            empty_parent_name = 'BG_' + str(self.idx) + '_Parent'
            empty_parent = add_empty(col_obj, empty_parent_name, 0, 0, 0)
            # Create one cube by used note
            for x in range(min_note, max_note + 1):
                if x in self.list_note:
                    cube_name = col_name + "_" + str(x)
                    add_cube(col_obj, cube_name, (63 - x) * self.BGLocCoef,
                             self.idx * self.BGLocCoef, 0, mat_c, empty_parent)
                    obj = b_dat.objects[cube_name]
                    obj.scale = 1.0, 1.0, 1.0
                    obj.keyframe_insert('scale')
        elif self.visual_type == "GD":
            # Create grid x = (12x3) + 1) et y = (11*3) + 1 => (12*11 = 132 notes)
            grid_name = 'GD_' + str(self.idx)
            add_grid( new_collec, grid_name, 0, 0, 0, mat_c, 37, 34, self.list_note)
        elif self.visual_type == "LT":
            col_name = 'LT_' + str(self.idx)
            # Create collection for this track
            col_obj = create_collection(col_name, new_collec, delete=True)
            light_name = 'LT_' + str(self.idx) + "_note_" + str(self.note_ref)
            add_light( col_obj, light_name, 0, 0, 12)

    # Add an new midi event related to the track
    def add_evt(self, evt, frame, note, velocity):

        def BG_note_on(frame, note, velocity):
            """ BG = Bargraphs
            Place note_on with Track object, velocity and keyframe
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
            cube_name = 'BG_' + str(self.idx) + "_" + str(note)

            # To avoid bargraphs slowly grow before the note
            if self.last_note_status[note] == 0:
                BG_note_off(frame - 1, note)

            scn.frame_current = frame
            obj = b_dat.objects[cube_name]
            obj.scale = 1.0, 1.0, (velocity / 8) + 1.0
            obj.keyframe_insert('scale')
            obj.location = (63 - note) * self.BGLocCoef, self.idx * self.BGLocCoef, (velocity / 12)
            obj.keyframe_insert('location')

            self.last_note_status[note] = velocity
            return None

        def BG_note_off(frame, note):
            """ BG = Bargraphs
            Place note_off with object and keyframe
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
            OUT
                None
            """
            cube_name = 'BG_' + str(self.idx) + "_" + str(note)

            # To avoid bargraphs slowly grow before the note
            if self.last_note_status[note] != 0:
                BG_note_on(frame - 1, note, self.last_note_status[note])

            scn.frame_current = frame
            obj = b_dat.objects[cube_name]
            obj.scale = 1.0, 1.0, 1.0
            obj.keyframe_insert('scale')
            obj.location = (63 - note) * self.BGLocCoef, self.idx * self.BGLocCoef, 0
            obj.keyframe_insert('location')

            self.last_note_status[note] = velocity
            return None

        def GD_note_evt(frame, note, velocity):
            """ GD = Grid
            Place note_on with Track object, velocity and keyframe
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
            note_name = 'GD_' + str(self.idx) + "_note_" + str(note)

            # To avoid bargraphs slowly grow before the note
            if velocity != self.last_note_status[note]:
                GD_note_evt(frame - 1, note, self.last_note_status[note])

            scn.frame_current = frame
            obj = b_dat.objects[note_name]
            vel = velocity - self.last_note_status[note]
            vec = mathutils.Vector((0.0, 0.0, vel / 12))
            obj.location = obj.location + vec
            obj.keyframe_insert('location')

            self.last_note_status[note] = velocity
            
            return None

        def LT_note_evt(frame, note, velocity):
            """ LT = Light
            Adjust light energy with event
            Don't use the note number because the case of use is for only on note
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
#            note_name = 'GD_' + str(self.idx) + "_note_" + str(note)

            # To avoid bargraphs slowly grow before the note
#            if velocity != self.last_note_status[note]:
#                LT_note_evt(frame - 1, note, self.last_note_status[note])

            note_name = 'LT_' + str(self.idx) + "_note_" + str(note)

            scn.frame_current = frame
            obj = b_dat.objects[note_name]
            energy = velocity * 400
            obj.data.energy = energy
            obj.data.keyframe_insert('energy')

#            self.last_note_status[note] = velocity
            return None

        # Main - add_evt
        if self.visual_type == "BG":
            if evt == 'note_on':
                BG_note_on(frame, note, velocity)
            elif evt == 'note_off':
                BG_note_off(frame, note)
        elif self.visual_type == "GD":
            if evt == 'note_on':
                GD_note_evt(frame, note, velocity)
            elif evt == 'note_off':
                GD_note_evt(frame, note, 0)
        elif self.visual_type == "LT":
            if note == self.note_ref:
                if evt == 'note_on':
                    LT_note_evt(frame, note, velocity)
                elif evt == 'note_off':
                    LT_note_evt(frame, note, 0)
    
        return None


""" ========================= MAIN ========================= """
time_start = time.time()

# Clear system console
os.system("cls")
col_name = "MTB"  # mean Midi To Blender

# Create a new collection even if already exist
new_collec = create_collection(col_name, b_con.scene.collection, delete=True)

# Create materials for cubes
# Cube body
mat_c = b_dat.materials.new(name="Material_Cube")
mat_c.use_nodes = True
principled = PrincipledBSDFWrapper(mat_c, is_readonly=False)
principled.base_color = (0.8, 0.4, 0.2)

# path = "H:\\Python\\MTB\\data"
path = "D:\\OneDrive\\Blog\\YT_Patrick Mauger\\02 - Midi_To_Blend\\MTB\\data"
filename = "T1_meanwoman"
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

# Open MIDIFile with the module MIDO
mid = MidiFile(filemid)
print(mid)

# type = 0 - (single track): all messages are in one track
# type = 1 - (synchronous): all tracks use the same tempo and start at the same time
# type = 2 - (asynchronous): each track is independent of the others
if (mid.type != 1):
    print('not type 1 midifile')
    raise RuntimeError("Only type 1, type "+ str(mid.type)+ " is not yet supported")

# Set some variables
PPQ = mid.ticks_per_beat
print(PPQ)

# Tb_Tempo for memorize tempo informations.
# The first index mean :
# 0 => Time to apply tempo
# 1 => Tempo
Tb_Tempo = np.zeros((2, 5000), dtype=int)
Tb_Tempo.fill(0)

Nb_Track = -1
scn = b_con.scene
Max_Num_frame = 0
# frameRate = 100
frameRate = b_con.scene.render.fps

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
    if Nb_Track == 1:
        TrackList.append(Track_Class(Nb_Track, track, track.name, "GD", 0))
    elif Nb_Track == 4:
#        TrackList.append(Track_Class(Nb_Track, track, track.name, "BG", 0))
        TrackList.append(Track_Class(Nb_Track, track, track.name, "LT", note_ref=39))
    else:
        TrackList.append(Track_Class(Nb_Track, track, track.name, "BG", 0))

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
        Num_frame = int(TpsSecCumul * frameRate)

#        print(TimePos, TpsSec, Num_frame)

        # note_on and note_off => no msg in DB, just values in usual columns
        if (msg.type == 'note_on') and (msg.velocity == 0):
            msgtype = 'note_off'
        else:
            msgtype = msg.type

        # note_on
        if (msgtype == 'note_on'):
            TrackList[Nb_Track].add_evt(msgtype, Num_frame, msg.note, msg.velocity)

        # note_off (or note_on with velocity=0)
        elif (msgtype == 'note_off'):
            TrackList[Nb_Track].add_evt(msgtype, Num_frame, msg.note, 0)

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
    if Num_frame > Max_Num_frame:
        Max_Num_frame = Num_frame

scn.frame_end = Max_Num_frame + 25

print('game over')
print("My Script Finished: %.4f sec" % (time.time() - time_start))

#    raise RuntimeError("Stopping the script here")


# End of script - Enjoy
