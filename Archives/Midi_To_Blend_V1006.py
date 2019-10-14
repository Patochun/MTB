import bpy
import bmesh
import mathutils
import numpy as np
import math
import random
import time
import os
import os.path
# for material
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper

# How to install a new python module in the blender (here mido) :
# http://www.codeplastic.com/2019/03/12/how-to-install-python-modules-in-blender/
# Mido is a library for working with MIDI messages and ports.
# It’s designed to be as straight forward and Pythonic as possible:
# https://mido.readthedocs.io/en/latest/installing.html
import mido
from mido import MidiFile

# Global blender objects
b_dat = bpy.data
b_con = bpy.context
b_scn = b_con.scene
b_ops = bpy.ops

# ********************************************************************
# Midi_To_Blend
# version = 1.006
# Blender version = 2.8
# Author = Patrick Mauger
# Web Site = docouatzat.com
# Mail = docouatzat@gmail.com
#
# Licence used = Creative Commons CC BY
# Check licence here : https://creativecommons.org
#
# Generate 3D objects animated from midifile
# ********************************************************************

""" ========================= Standard functions ========================= """


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

def rgb_random_color():
    """
    Return a random color list for Red, Green, Blue
    IN
    OUT
        list r,g,b random value between 0.0 to 1.0 each
    """
    r, g, b = [random.random() for i in range(3)]
    return r, g, b

def add_empty(collect, name_of_empty, x, y, z):
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
    obj_empty.name = name_of_empty
    assign_to_collection(collect, obj_empty)

    return obj_empty


def add_cube(collect, name_of_cube, x, y, z, mat, empty_parent):
    """ Create a Cube Mesh
    IN
        collect         obj     collection
        name_of_cube    str     name of created cube
        x, y, z         float   coordinates
        mat             obj     material
    OUT
        The object cube created
    """
    b_ops.mesh.primitive_cube_add(enter_editmode=False, location=(x, y, z))

    # ToDO remark : Assume the last cube created is named "Cube"
    # because this name is free... Dangerous
    obj_cube = b_dat.objects.get("Cube")
    obj_cube.name = name_of_cube
    obj_cube.parent = empty_parent

    # Little bevel is always a nice idea for a cube
    obj_cube.modifiers.new(name="Bevel", type='BEVEL')
    b_ops.object.modifier_apply(apply_as='DATA', modifier="Bevel")

    assign_to_collection(collect, obj_cube)

    return obj_cube


def add_grid(collect, name_of_grid, x, y, z, mat, sx, sy, list_note):
    """ Create a Grid Mesh and 127 empty hooked to 127 faces
    IN
        collect         obj     collection
        name_of_grid    str     name of created grid
        x, y, z         float   coordinates
        mat             obj     material
        sx              int     subdivisions x
        sy              int     subdivisions y
        list_note       list    list of used notes
    OUT
        The object grid created
    """
    # Create collection for this track
    col_obj = create_collection(name_of_grid, collect, delete=True)

    # Create the empty parent off all Hook
    empty_parent_name = 'GD_' + name_of_grid + '_Parent'
    empty_parent = add_empty(col_obj, empty_parent_name, 0, 0, 0)

    b_ops.mesh.primitive_grid_add(x_subdivisions=sx, y_subdivisions=sy, size=64, enter_editmode=False, location=(x, y, z))

    # ToDO remark : Assume the last grid created is named "Grid"
    # because this name is free... Dangerous
    obj_grid = b_dat.objects.get("Grid")
    obj_grid.name = name_of_grid
    assign_to_collection(col_obj, obj_grid)
    empty_parent.parent = obj_grid

    # Add an hook for each note used on respective face
    me = obj_grid.data
    for x in range(1, 127):
        if x not in list_note:
            continue
        b_ops.object.mode_set(mode="EDIT")
        b_ops.mesh.select_all(action='DESELECT')
        b_ops.object.mode_set(mode="OBJECT")
        # Math to distribute hooks with harmony on faces
        num_face = ((x * 3 - 2) + ((((x - 1) // 12) + 1) * 72)) - 36
        # Select vertice
        b_dat.meshes[me.name].polygons[num_face].select = True
        b_ops.object.mode_set(mode="EDIT")
        b_ops.object.hook_add_newob()
        obj_empty = b_dat.objects.get("Empty")
        obj_empty.name = name_of_grid + "_note_" + str(x)
        obj_empty.parent = empty_parent
        assign_to_collection(col_obj, obj_empty)
        b_ops.object.mode_set(mode="OBJECT")

    return obj_grid

def add_light(collect, name_of_light, x, y, z, empty_parent):
    """ Create a Light
    IN
        collect         obj     collection
        name_of_light   str     name of created light
        x, y, z         float   coordinates
    OUT
        The object light created
    """
    # Create light datablock, set attributes
    obj_data = b_dat.lights.new(name=name_of_light, type='POINT')
    obj_data.energy = 0  # mean no note velocity at this time

    # Create new object with our light datablock
    obj_light = b_dat.objects.new(name=name_of_light, object_data=obj_data)
    obj_light.location = (x, y, z)
    obj_light.data.color = rgb_random_color()
    obj_light.parent = empty_parent

    b_con.view_layer.active_layer_collection.collection.objects.link(obj_light)
    assign_to_collection(collect, obj_light)

    return obj_light


def add_fountain(collect, name_of_fountain, x, y, z, empty_parent):
    """ Create a Fountain of particules
    IN
        collect             obj     collection
        name_of_fountain    str     name of created light
        x, y, z             float   coordinates
    OUT
        The object light created
    """

    # Create small icosphere for the emitter
    b_ops.mesh.primitive_ico_sphere_add(radius=0.25, subdivisions=3, enter_editmode=False, location=(x, y, z))
    obj_fountain = b_dat.objects.get("Icosphere")
    obj_fountain.name = name_of_fountain
    assign_to_collection(collect, obj_fountain)
    obj_fountain.parent = empty_parent

    # add particle system to the ico sphere to become an emitter
    b_ops.object.particle_system_add()
    ps = obj_fountain.particle_systems
    name_of_ps = name_of_fountain + "_PS"
    ps.active.name = name_of_ps

    # Create small UV sphere to become the particle object
    b_ops.mesh.primitive_uv_sphere_add(radius=1, enter_editmode=False, location=(x, y, z - 2))
    obj_fountain_pt = b_dat.objects.get("Sphere")
    obj_fountain_pt.name = name_of_fountain + "_particle"
    assign_to_collection(collect, obj_fountain_pt)
    obj_fountain_pt.parent = empty_parent

    # Set all usefull parameters to emitter
    ps.active.settings.render_type = 'OBJECT'
    ps.active.settings.instance_object = obj_fountain_pt
    ps.active.settings.count = 1000000
    ps.active.settings.frame_end = 100000
    ps.active.settings.lifetime = 1
    ps.active.settings.emit_from = 'FACE'
    ps.active.settings.distribution = 'JIT'
    ps.active.settings.userjit = 10
    ps.active.settings.object_align_factor[2] = 0

    return obj_fountain


def add_pb(collect, name_of_pb, x, y, z, mat, empty_parent):
    """ Create a Paper Ball
    IN
        collect         obj     collection
        name_of_pb      str     name of Paper Ball
        x, y, z         float   coordinates
        mat             obj     material
    OUT
        The object Paper Ball created
    """
    b_ops.mesh.primitive_uv_sphere_add(radius=2, enter_editmode=False, location=(x, y, z))

    # ToDO remark : Assume the last uv_sphere created is named "Sphere"
    # because this name is free... Dangerous
    obj_pb = b_dat.objects.get("Sphere")
    obj_pb.name = name_of_pb
    obj_pb.parent = empty_parent

    # Modifier Subdivision
    mod1 = obj_pb.modifiers.new(name="Subdivision", type='SUBSURF')
    mod1.render_levels = 4
    mod1.levels = 2

    # Create texture
    tex = b_dat.textures.new("Voronoi", 'VORONOI')

    # Modifier Displacement
    mod2 = obj_pb.modifiers.new(name="Displacement", type='DISPLACE')
    mod2.strength = 0
    mod2.texture = tex

    assign_to_collection(collect, obj_pb)

    return obj_pb


""" ========================= Class ========================= """


class Track_Class:

    # Track initializations
    def __init__(self, idx_track, track, name, visual_type):
        """
        Initialization of the Class Track_Class
        IN
            See below for comment
        OUT
            The new object instanciated
        """
        # Parameters
        self.idx = idx_track            # Track index number
        self.track = track              # the track object from mido
        self.name = name                # mean the name or description
        self.visual_type = visual_type  # mean the type of visualization

        # Internal use
        self.last_note_status = {}      # dictionnary {note:status}
        self.list_note = []             # list of note used in this track
        self.min_note = 128             # lower note of the track, mean the first note
        self.max_note = 0               # highest note of the track, mean the last note
        self.loc_coef = 2.5             # localisation coef (!)
        self.curve = 1                  # mean the delta number of frame between evt change

        def Track_is_BG():
            """
            Instanciate with a track typed : BG - BarGraphs
            """
                # Create cubes from only used notes
            b_scn.frame_current = 1
            col_name = 'BG_' + str(self.idx)
            # Create collection for this track
            col_obj = create_collection(col_name, new_collec, delete=True)
            # Create the empty parent off all cubes
            empty_parent_name = 'BG_' + str(self.idx) + '_Parent'
            empty_parent = add_empty(col_obj, empty_parent_name, 0, 0, 4)
            # Create one cube by used note
            for x in range(self.min_note, self.max_note + 1):
                if x in self.list_note:
                    cube_name = col_name + "_" + str(x)
                    add_cube(col_obj, cube_name, (x - 63) * self.loc_coef, self.idx * self.loc_coef, 0, mat_c, empty_parent)
            return None

        def Track_is_GD():
            """
            Instanciate with a track typed : GD - Grid
            """
            # Create grid x = (12x3) + 1) et y = (11*3) + 1 => (12*11 = 132 notes)
            grid_name = 'GD_' + str(self.idx)
            add_grid(new_collec, grid_name, 0, 0, 0, mat_c, 37, 34, self.list_note)
            return None

        def Track_is_LT():
            """
            Instanciate with a track typed : LT - Light
            """
            col_name = 'LT_' + str(self.idx)
            # Create collection for this track
            col_obj = create_collection(col_name, new_collec, delete=True)
            # Create the empty parent off all light
            empty_parent_name = 'LT_' + str(self.idx) + '_Parent'
            empty_parent = add_empty(col_obj, empty_parent_name, 0, 0, 4)
            # Create one light by used note
            for x in range(self.min_note, self.max_note + 1):
                if x in self.list_note:
                    light_name = col_name + "_" + str(x)
                    add_light(col_obj, light_name, (x - 63) * self.loc_coef, self.idx * self.loc_coef, 4, empty_parent)
            return None

        def Track_is_FT():
            """
            Instanciate with a track typed : FT - Fountain
            """
            col_name = 'FT_' + str(self.idx)
            # Create collection for this track
            col_obj = create_collection(col_name, new_collec, delete=True)
            # Create the empty parent off all light
            empty_parent_name = 'FT_' + str(self.idx) + '_Parent'
            empty_parent = add_empty(col_obj, empty_parent_name, 0, 0, 4)
            # Create one fountain by used note
            for x in range(self.min_note, self.max_note + 1):
                if x in self.list_note:
                    fountain_name = col_name + "_" + str(x)
                    add_fountain(col_obj, fountain_name, (x - 63) * self.loc_coef, self.idx * self.loc_coef, 2, empty_parent)
            return None

        def Track_is_PB():
            """
            Instanciate with a track typed : PB - Paper Ball
            """
            col_name = 'PB_' + str(self.idx)
            # Create collection for this track
            col_obj = create_collection(col_name, new_collec, delete=True)
            # Create the empty parent off all light
            empty_parent_name = 'PB_' + str(self.idx) + '_Parent'
            empty_parent = add_empty(col_obj, empty_parent_name, 0, 0, 4)
            for x in range(self.min_note, self.max_note + 1):
                if x in self.list_note:
                    paperball_name = col_name + "_" + str(x)
                    add_pb(col_obj, paperball_name, (x - 63) * self.loc_coef, self.idx * self.loc_coef, 0, mat_c, empty_parent)
            return None


        """ ======= Main of __init__ ========================================== """

        # Know notes used in track
        if mid.type == 0:
            # For MIDI file type 0 the only track we see here is the track 0
            # Assume channel mean track instead of
            for msg in track:
                if msg.type == 'note_on':
                    if msg.channel == self.idx:
                        if msg.note not in self.list_note:
                            self.list_note.append(msg.note)
                            self.last_note_status[msg.note] = 0
        elif mid.type == 1:
            for msg in track:
                if (msg.type == 'note_on'):
                    if msg.note not in self.list_note:
                        self.list_note.append(msg.note)
                        self.last_note_status[msg.note] = 0

        # If no note in this track then return without creating any object
        # Because no event will be treated later
        if not self.list_note:
            return

        self.min_note = min(self.list_note)
        self.max_note = max(self.list_note)
        self.curve = framerate // 8
        # All objects are created the most centered as possible
        # Type BG = Bargraphs
        if self.visual_type == "BG":
            Track_is_BG()
        # Type GD = Grid
        elif self.visual_type == "GD":
            Track_is_GD()
        # Type LT = Light
        elif self.visual_type == "LT":
            Track_is_LT()
        # Type FT = Fountain
        elif self.visual_type == "FT":
            Track_is_FT()
        # Type PB = Paper Ball
        elif self.visual_type == "PB":
            Track_is_PB()
        return

    # Add an new midi event related to the track
    def add_evt(self, evt, frame, note, velocity):

        def BG_note_evt(frame, note, velocity):
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
            if velocity != self.last_note_status[note]:
                BG_note_evt(frame - self.curve, note, self.last_note_status[note])

            obj = b_dat.objects[cube_name]
            obj.scale = 1.0, 1.0, (velocity / 16) + 1.0
            obj.keyframe_insert(data_path='scale', frame=frame)
            obj.location = (63 - note) * self.loc_coef, self.idx * self.loc_coef, (velocity / 16)
            obj.keyframe_insert(data_path='location', frame=frame)
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

            # To avoid value slowly grow before the note
            if velocity != self.last_note_status[note]:
                GD_note_evt(frame - self.curve, note, self.last_note_status[note])

            obj = b_dat.objects[note_name]
            vel = velocity - self.last_note_status[note]
            vec = mathutils.Vector((0.0, 0.0, vel / 12))
            obj.location = obj.location + vec
            obj.keyframe_insert(data_path='location', frame=frame)
            self.last_note_status[note] = velocity
            return None

        def LT_note_evt(frame, note, velocity):
            """ LT = Light
            Change energy of light/note accordingly to velocity
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
            note_name = 'LT_' + str(self.idx) + "_" + str(note)

            if velocity != self.last_note_status[note]:
                LT_note_evt(frame - self.curve, note, self.last_note_status[note])

            obj = b_dat.objects[note_name]
            energy = velocity * 400
            obj.data.energy = energy
            obj.data.keyframe_insert(data_path='energy', frame=frame)
            self.last_note_status[note] = velocity
            return None

        def FT_note_evt(frame, note, velocity):
            """ FT = Fountain
            Activate emitter of fountain accordingly to velocity
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
            note_name = 'FT_' + str(self.idx) + "_" + str(note)

            if velocity != self.last_note_status[note]:
                FT_note_evt(frame - self.curve, note, self.last_note_status[note])

            obj = b_dat.objects[note_name]
            ps = obj.particle_systems
            ps.active.settings.lifetime = velocity / 2
            ps.active.settings.keyframe_insert(data_path='lifetime', frame=frame)
            ps.active.settings.object_align_factor[2] = velocity / 6
            ps.active.settings.keyframe_insert(data_path='object_align_factor', index=2, frame=frame)
            self.last_note_status[note] = velocity
            return None

        def PB_note_evt(frame, note, velocity):
            """ PB = Paper Ball
            Place note_on with Track object, velocity and keyframe
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
            pb_name = 'PB_' + str(self.idx) + "_" + str(note)

            # To avoid pb slowly grow before the note
            if velocity != self.last_note_status[note]:
                PB_note_evt(frame - self.curve, note, self.last_note_status[note])

            obj = b_dat.objects[pb_name]
            mod = obj.modifiers[1]
            mod.strength = velocity / 127
            mod.keyframe_insert(data_path='strength', frame=frame)
            self.last_note_status[note] = velocity
            return None


        # Main - add_evt - For now suppose all type evt is note_on or note_off
        # Dispatch by type of object
        if self.visual_type == "BG":
            BG_note_evt(frame, note, velocity)
        elif self.visual_type == "GD":
            GD_note_evt(frame, note, velocity)
        elif self.visual_type == "LT":
            LT_note_evt(frame, note, velocity)
        elif self.visual_type == "FT":
            FT_note_evt(frame, note, velocity)
        elif self.visual_type == "PB":
            PB_note_evt(frame, note, velocity)

        return None


""" ========================= MAIN ========================= """

time_start = time.time()

# Clear system console
os.system("cls")

# Create the principal collection, mean Midi To Blender
col_name = "MTB"
new_collec = create_collection(col_name, b_con.scene.collection, delete=True)

# Create materials - temporary => to be replaced by function
mat_c = b_dat.materials.new(name="Material_Cube")
mat_c.use_nodes = True
principled = PrincipledBSDFWrapper(mat_c, is_readonly=False)
principled.base_color = (0.8, 0.4, 0.2)

# path and name of midi file - temporary => replaced when this become an add-on
path = "H:\\Python\\MTB\\data"
# path = "D:\\OneDrive\\Blog\\YT_Patrick Mauger\\02 - Midi_To_Blend\\MTB\\data"
filename = "T1_meanwoman"
filemid = path + "\\" + filename + ".mid"
fileaudio = path + "\\" + filename + ".mp3"

# Open MIDIFile with the module MIDO
mid = MidiFile(filemid)

# type = 0 - (single track): all messages are in one track and use the same tempo and start at the same time
# type = 1 - (synchronous): all messages are in separated tracks and use the same tempo and start at the same time
# type = 2 - (asynchronous): each track is independent of the others for tempo and for start - not yet supported
if (mid.type == 2):
    raise RuntimeError("Only type 0 or 1, type " + str(mid.type) + " is not yet supported")

# load audio file mp3 with the meme name of midi file if exist
# into sequencer
if os.path.exists(fileaudio):

    if not b_scn.sequence_editor:
        b_scn.sequence_editor_create()

    # Clear the VSE, then add an audio file
    b_scn.sequence_editor_clear()
    my_contextmem = b_con.area.type
    my_context = 'SEQUENCE_EDITOR'
    b_con.area.type = my_context
    my_context = b_con.area.type
    b_ops.sequencer.sound_strip_add(filepath=fileaudio, relative_path=True, frame_start=1, channel=1)
    b_con.area.type = my_contextmem
    my_context = b_con.area.type
    b_con.scene.sequence_editor.sequences_all[filename + ".mp3"].volume = 0.025


# Set pulsation per quarter note (ppq)
# Mean the number of pulsation per round note / 4 = black note
ppq = mid.ticks_per_beat

# Init Max frame number founded for all track, mean the end of animation
max_num_frame = 0

# take the framerate directly from blender
framerate = b_con.scene.render.fps

# Fill d_tempo with tempo founded into track 0
# For type 0 and 1 midifile
track = mid.tracks[0]
tempo_count = 0
d_tempo = {}
for msg in track:
    if msg.type == 'set_tempo':
        tempo_count += 1
        d_tempo[msg.time] = msg.tempo

# l_tempo_time contain the list of founded tempos sorted by time
l_tempo_time = sorted(d_tempo.keys())
tempo_count = len(d_tempo)

# List of Track <= receive object Track_Class
TrackList = []

# Dictionnary used by MIDI file type 0 to convert channel number found in track 0 into track number
d_channel_to_tracklist = {}

# Creating the 3D track vizualisation objects
if (mid.type == 0):
    track = mid.tracks[0]
    l_channel = []
    for msg in track:
        if msg.type == ('note_on'):
            if msg.channel not in l_channel:
                l_channel.append(msg.channel)
    l_channel = sorted(l_channel)
    print(l_channel)
    # Assume one channel found equal one track
    current_track = 0
    for current_channel in l_channel:
        track_name = "Channel " + str(current_channel)
        TrackList.append(Track_Class(current_channel, track, track_name, "BG"))
        d_channel_to_tracklist[current_channel] = current_track
        current_track += 1
elif (mid.type == 1):
    for current_track, track in enumerate(mid.tracks):
        # Instancing Track Object
        # Here will take place the choice by user from UI interface later
        # For now, is manual and is here directly in the script
        if current_track == 1:
            TrackList.append(Track_Class(current_track, track, track.name, "GD"))
        elif current_track == 4:
            TrackList.append(Track_Class(current_track, track, track.name, "BG"))
        elif current_track == 2:
            TrackList.append(Track_Class(current_track, track, track.name, "FT"))
        else:
           TrackList.append(Track_Class(current_track, track, track.name, "PB"))


# Main LOOP on midifile track
for current_track, track in enumerate(mid.tracks):
    print('Track {}: {}, {} evt(s)'.format(current_track, track.name, len(track)))

#   Initialize the time cumul in ticks and second for the track
    time_in_ticks_cumul = 0
    time_in_sec_Cumul = 0
#   set current tempo to the first tempo founded in list (indice 0)
#   and set the next_tempo for evaluation (indice 1)
    current_tempo = d_tempo[l_tempo_time[0]]
    next_tempo = 1

    # Parse midi message for the current track
    for msg in track:

        time_in_ticks_cumul += msg.time

        # Check if Tempo need to be changed
        if next_tempo < tempo_count:
            if time_in_ticks_cumul > l_tempo_time[next_tempo]:
                current_tempo = d_tempo[l_tempo_time[next_tempo]]
                next_tempo += 1

        time_in_sec = mido.tick2second(msg.time, ppq, current_tempo)
        time_in_sec_Cumul += time_in_sec

        # Evaluate the current frame by using the blender framerate
        current_frame = int(time_in_sec_Cumul * framerate)

        # Check if note_on with velocity 0 will become note_off
        if (msg.type == 'note_on') and (msg.velocity == 0):
            msgtype = 'note_off'
        else:
            msgtype = msg.type

        # Define real current track accordingly with MIDI file type 0,1 or 2
        if mid.type == 0:
            cur_track = d_channel_to_tracklist[msg.channel]
        else:
            cur_track = current_track

        # If note_on or note_off invoke Class function appropriate
        if msgtype in ('note_on','note_off'):
            velocity = msg.velocity * (msgtype == 'note_on')  # to avoid note_off with velocity != 0
            TrackList[cur_track].add_evt(msgtype, current_frame, msg.note, velocity)

        # here, later, how to deal with other msg type like
        # control_change
        # program_change
        # pitchwheel
        # and so on...

    # Manage the last frame number : mean the end of animation
    if current_frame > max_num_frame:
        max_num_frame = current_frame

# Add one second at the end of animation
b_scn.frame_end = max_num_frame + framerate

print("Script Finished: %.4f sec" % (time.time() - time_start))

# End of script - Enjoy
