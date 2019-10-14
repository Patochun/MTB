import bpy
import bmesh
import mathutils
import numpy as np
import math
import random
import time
import os
import os.path
import json
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
# version = 1.008
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


def rgb_random_color():
    """
    Return a random color list for Red, Green, Blue
    IN
    OUT
        list r,g,b random value between 0.0 to 1.0 each
    """
    r, g, b = [random.random() for i in range(3)]
    return r, g, b


def Create_material_simple(name_of_color, r, g, b, rand):
    """
    Return a simple diffuse material
    IN
        name        str     The name of material
        r, g, b     float   value for red, green and blue (beetwen 0.0 to 1.0)
    OUT
        material created
    """
    # Create materials - temporary => to be replaced by function
    mat = b_dat.materials.new(name="Material_Cube")
    mat.use_nodes = True
    mat.name = name_of_color
    principled = PrincipledBSDFWrapper(mat, is_readonly=False)
    if rand:
        principled.base_color = rgb_random_color()
    else:
        principled.base_color = (r, g, b)
    return mat


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


def add_duplicate_linked(collect, name_of_object, x, y, z, obj_model):
    """ Create a duplicate and linked object from template
    IN
        collect         obj     collection
        name_of_object  str     name of new object from duplicate
        x, y, z         float   coordinates
        template        obj     object template
    OUT
        The object created from duplication
    """
    if obj_model:
        obj = obj_model.copy()
        obj.name = name_of_object
        obj.location = x, y, z

        # add properties to all objects/notes
        obj['velocity'] = 0
        obj['aftertouch'] = 0

        collect.objects.link(obj)
    return obj


def add_cube(collect, name_of_cube, material, x, y, z, emp_par):
    """ Create a Cube Mesh
    IN
        collect         obj     collection
        name_of_cube    str     name of created cube
        x, y, z         float   coordinates
        mat             obj     material
    OUT
        The object cube created
    """
    b_ops.mesh.primitive_cube_add(enter_editmode=False, size=2, location=(x, y, z))

    # ToDO remark : Assume the last cube created is named "Cube"
    # because this name is free... Dangerous
    obj_cube = b_dat.objects.get("Cube")
    obj_cube.name = name_of_cube
    obj_cube.parent = emp_par
    obj_cube.data.materials.append(material)

    # Little bevel is always a nice idea for a cube
    obj_cube.modifiers.new(name="Bevel", type='BEVEL')
    b_ops.object.modifier_apply(apply_as='DATA', modifier="Bevel")

    assign_to_collection(collect, obj_cube)

    return obj_cube


def add_grid(collect, name_of_grid, material, x, y, z, sx, sy, list_note):
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
    # Create collection for this channel
    col_obj = create_collection(name_of_grid, collect, delete=True)

    # Create the empty parent off all Hook
    emp_par_name = 'GD_' + name_of_grid + '_Parent'
    emp_par = add_empty(col_obj, emp_par_name, 0, 0, 0)

    b_ops.mesh.primitive_grid_add(x_subdivisions=sx, y_subdivisions=sy, size=64, enter_editmode=False, location=(x, y, z))

    # ToDO remark : Assume the last grid created is named "Grid"
    # because this name is free... Dangerous
    obj_grid = b_dat.objects.get("Grid")
    obj_grid.name = name_of_grid
    assign_to_collection(col_obj, obj_grid)
    emp_par.parent = obj_grid

    obj_grid.data.materials.append(material)

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
        obj_empty.name = name_of_grid + "_" + str(x)
        obj_empty.parent = emp_par
        assign_to_collection(col_obj, obj_empty)
        b_ops.object.mode_set(mode="OBJECT")

    return obj_grid


def add_light(collect, name_of_light, x, y, z, emp_par):
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
    obj_light.parent = emp_par

    b_con.view_layer.active_layer_collection.collection.objects.link(obj_light)
    assign_to_collection(collect, obj_light)

    return obj_light


def add_fountain(collect, name_of_fountain, material, x, y, z, emp_par):
    """ Create a Fountain of particules
    IN
        collect             obj     collection
        name_of_fountain    str     name of created light
        x, y, z             float   coordinates
    OUT
        The object fountain created
    """

    # Create small icosphere for the emitter
    # All particles stuff are created with event note_on/note_off
    b_ops.mesh.primitive_ico_sphere_add(radius=0.5, subdivisions=3, enter_editmode=False, location=(x, y, z))
    obj_fountain = b_dat.objects.get("Icosphere")
    obj_fountain.name = name_of_fountain
    assign_to_collection(collect, obj_fountain)
    obj_fountain.parent = emp_par

    return obj_fountain


def add_pb(collect, name_of_pb, material, x, y, z, emp_par):
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
    obj_pb.parent = emp_par
    obj_pb.data.materials.append(material)

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


def search_channel_in_mtb_data(id):
    """ Search all infos about a channel in mtb_data
    IN
        id         int     Identifier of channel
    OUT
        mtb_channel
    """
    for chan in mtb_data:
        if chan['Channel'] == id:
            return chan
    return None


""" ========================= Class ========================= """


class Channel_Class:

    # Channel initializations
    def __init__(self, idx_channel, list_note, name, channel):
        """
        Initialization of the Class Channel_Class
        IN
            See below for comment
        OUT
            The new object instanciated
        """
        # Parameters
        self.idx = idx_channel                  # Channel index number
        self.name = name                        # mean the name or description
        self.visual_type = channel["Type"]      # mean the type of visualization
        self.template = channel["Template"]     # template object or ""
        self.animate = channel["Animate"]       # Animate, True or False
        self.locked = channel["Locked"]         # channel is locked ? True or False
        self.list_note = list_note              # list of note used in this channel

        # Internal use
        self.last_note_status = {}      # dictionnary {note:status}, used by animation
        self.min_note = 128             # lower note of the channel, mean the first note
        self.max_note = 0               # highest note of the channel, mean the last note

        # Internal use for 3D
        self.count_place = 0            # count of places used in channel (with note or not)
        self.cf = 2.5                   # localisation coef (!)
        self.curve = 1                  # mean the delta number of frame between evt change

        def Channel_is_BG():
            """
            Instanciate with a channel typed : BG - BarGraphs
            """
            # Create cubes from only used notes
            col_name = 'BG_' + str(self.idx)
            # Create collection for this channel
            col_obj = create_collection(col_name, new_collec, delete=True)
            # Create the empty parent off all cubes
            emp_par_name = 'BG_' + str(self.idx) + '_Parent'
            emp_par = add_empty(col_obj, emp_par_name, 0, self.idx * self.cf, 0)
            # Create material
            material = Create_material_simple(col_name + "_mat", 0.0, 0.0, 0.0, True)

            # Create template
            if self.template != "":
                obj_model = b_dat.objects.get(self.template)
            else:
                obj_model = add_cube(col_obj, col_name + "_template", material, -50 * self.cf, self.idx * self.cf, 0, emp_par)

            current_place = 0
            median_place = self.count_place // 2
            # Duplicate template, one by note
            for x in range(self.min_note, self.max_note + 1):
                if x in self.list_note:
                    BG_name = col_name + "_" + str(x)
                    add_duplicate_linked(col_obj, BG_name, (current_place - median_place) * self.cf, 0, 0, obj_model)
                current_place += 1

            # add properties to obj_model for channel properties
            obj_model['pitchbend'] = 0

            return None

        def Channel_is_GD():
            """
            Instanciate with a channel typed : GD - Grid
            """
            # Create grid x = (12x3) + 1) et y = (11*3) + 1 => (12*11 = 132 notes)
            grid_name = 'GD_' + str(self.idx)
            material = Create_material_simple(grid_name + "_mat", 0.0, 0.0, 0.0, True)
            add_grid(new_collec, grid_name, material, 0, 0, 0, 37, 34, self.list_note)
            return None

        def Channel_is_LT():
            """
            Instanciate with a channel typed : LT - Light
            """
            col_name = 'LT_' + str(self.idx)
            # Create collection for this channel
            col_obj = create_collection(col_name, new_collec, delete=True)
            # Create the empty parent off all light
            emp_par_name = 'LT_' + str(self.idx) + '_Parent'
            emp_par = add_empty(col_obj, emp_par_name, 0, self.idx * self.cf, 4)
            current_place = 0
            median_place = self.count_place // 2
            # Create one light by used note
            for x in range(self.min_note, self.max_note + 1):
                if x in self.list_note:
                    light_name = col_name + "_" + str(x)
                    add_light(col_obj, light_name, (current_place - median_place) * self.cf, 0, 4, emp_par)
                current_place += 1
            return None

        def Channel_is_FT():
            """
            Instanciate with a channel typed : FT - Fountain
            """
            col_name = 'FT_' + str(self.idx)
            # Create collection for this channel
            col_obj = create_collection(col_name, new_collec, delete=True)
            # Create the empty parent off all light
            emp_par_name = 'FT_' + str(self.idx) + '_Parent'
            emp_par = add_empty(col_obj, emp_par_name, 0, self.idx * self.cf, 4)
            # Create material
            material = Create_material_simple(col_name + "_mat", 0.0, 0.0, 0.0, True)

            # Create small UV sphere to become the particle object
            b_ops.mesh.primitive_uv_sphere_add(radius=2, enter_editmode=False, location=(0, 0, -20))
            obj_fountain_pt = b_dat.objects.get("Sphere")
            obj_fountain_pt.name = col_name + "_particle"
            assign_to_collection(col_obj, obj_fountain_pt)
            obj_fountain_pt.parent = emp_par
            obj_fountain_pt.data.materials.append(material)

            # Create template
            obj_model = add_fountain(col_obj, col_name + "_template", material, -50 * self.cf, self.idx * self.cf, 0, emp_par)

            current_place = 0
            median_place = self.count_place // 2
            # Duplicate template, one by note
            for x in range(self.min_note, self.max_note + 1):
                if x in self.list_note:
                    fountain_name = col_name + "_" + str(x)
                    add_duplicate_linked(col_obj, fountain_name, (current_place - median_place) * self.cf, 0, 0, obj_model)
                current_place += 1

            # add properties to obj_model for channel properties
            obj_model['pitchbend'] = 0

            return None

        def Channel_is_PB():
            """
            Instanciate with a channel typed : PB - Paper Ball
            """
            col_name = 'PB_' + str(self.idx)
            # Create collection for this channel
            col_obj = create_collection(col_name, new_collec, delete=True)
            # Create the empty parent off all light
            emp_par_name = 'PB_' + str(self.idx) + '_Parent'
            emp_par = add_empty(col_obj, emp_par_name, 0, self.idx * self.cf, 4)
            # Create material
            material = Create_material_simple(col_name + "_mat", 0.0, 0.0, 0.0, True)
            # Create template
            obj_model = add_pb(col_obj, col_name + "_template", material, -50 * self.cf, self.idx * self.cf, 0, emp_par)

            current_place = 0
            median_place = self.count_place // 2
            # Duplicate template, one by note
            for x in range(self.min_note, self.max_note + 1):
                if x in self.list_note:
                    paperball_name = col_name + "_" + str(x)
                    add_duplicate_linked(col_obj, paperball_name, (current_place - median_place) * self.cf, 0, 0, obj_model)
                current_place += 1

            # add properties to obj_model for channel properties
            obj_model['pitchbend'] = 0

            return None

        """ ======= Main of __init__ ========================================== """

        # initialize note status
        for note in self.list_note:
            self.last_note_status[note] = 0

        # If no note in this channel then return without creating any object
        # Because no event will be treated later
        # Code here maybe for SMF 2 ?
        if not self.list_note or self.locked =="True":
            return None

        print('Generate Channel {}: {}'.format(self.idx, self.name))
        self.min_note = min(self.list_note)
        self.max_note = max(self.list_note)
        self.count_place = (self.max_note - self.min_note) + 1
        self.curve = framerate // 8
        # All objects are created the most centered as possible
        # Type BG = Bargraphs
        if self.visual_type == "BG":
            Channel_is_BG()
        # Type GD = Grid
        elif self.visual_type == "GD":
            Channel_is_GD()
        # Type LT = Light
        elif self.visual_type == "LT":
            Channel_is_LT()
        # Type FT = Fountain
        elif self.visual_type == "FT":
            Channel_is_FT()
        # Type PB = Paper Ball
        elif self.visual_type == "PB":
            Channel_is_PB()

        return None

    # Add an new midi event related to the channel
    def add_evt(self, evt, frame, note, velocity):

        def BG_note_evt(obj, frame, note, velocity):
            """ BG = Bargraphs
            Place note_on with Channel object, velocity and keyframe
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
            # To avoid bargraphs slowly grow before the note
            if velocity != self.last_note_status[note]:
                BG_note_evt(obj, frame - self.curve, note, self.last_note_status[note])
            obj.scale = 1.0, 1.0, (velocity / 16) + 1.0
            obj.keyframe_insert(data_path='scale', frame=frame)
            vel = velocity - self.last_note_status[note]
            vec = mathutils.Vector((0.0, 0.0, vel / 16))
            obj.location = obj.location + vec
            obj.keyframe_insert(data_path='location', frame=frame)
            obj.keyframe_insert(data_path="""["velocity"]""", frame=frame)
            self.last_note_status[note] = velocity
            return None

        def GD_note_evt(obj, frame, note, velocity):
            """ GD = Grid
            Place note_on with Channel object, velocity and keyframe
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
            if velocity != self.last_note_status[note]:
                GD_note_evt(obj, frame - self.curve, note, self.last_note_status[note])
            vel = velocity - self.last_note_status[note]
            vec = mathutils.Vector((0.0, 0.0, vel / 12))
            obj.location = obj.location + vec
            obj.keyframe_insert(data_path='location', frame=frame)
            self.last_note_status[note] = velocity
            return None

        def LT_note_evt(obj, frame, note, velocity):
            """ LT = Light
            Change energy of light/note accordingly to velocity
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
            if velocity != self.last_note_status[note]:
                LT_note_evt(obj, frame - self.curve, note, self.last_note_status[note])
            energy = velocity * 400
            obj.data.energy = energy
            obj.data.keyframe_insert(data_path='energy', frame=frame)
            self.last_note_status[note] = velocity
            return None

        def FT_note_evt(obj, frame, note, velocity):
            """ FT = Fountain
            Activate emitter of fountain accordingly to velocity
            Using 1 new PS (Particles System) with frame_start/frame_end and not keyframed
            Self.last_note_status contain the last current PS in progress
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note velocity
            OUT
                None
            """
            # Create new PS with set of frame_start
            if velocity != 0:

                current_ps = self.last_note_status[note] + 1

                # add particle system to the ico sphere emitter
                ps = obj.modifiers.new(name='particles', type='PARTICLE_SYSTEM')
                ps = obj.particle_systems
                name_of_ps = obj.name + "_PS_" + str(current_ps)
                ps.active.name = name_of_ps

                # Set all usefull parameters to emitter
                obj_particle_name = 'FT_' + str(self.idx) + "_particle"
                obj_particle = b_dat.objects[obj_particle_name]
                ps.active.settings.name = name_of_ps
                ps.active.settings.render_type = 'OBJECT'
                ps.active.settings.instance_object = obj_particle
                ps.active.settings.count = velocity * 2

                # Be sure to initialize frame_end before frame_start because
                # frame_start can't be greather than frame_end at any time
                ps.active.settings.frame_end = frame
                ps.active.settings.frame_start = frame
                ps.active.settings.lifetime = framerate * 4
                ps.active.settings.emit_from = 'FACE'
                ps.active.settings.distribution = 'JIT'
                ps.active.settings.userjit = 10
                ps.active.settings.object_align_factor[2] = velocity // 8

                self.last_note_status[note] = current_ps

            # set frame_end of existing current PS
            else:
                current_ps = self.last_note_status[note]
                ps_name = obj.name + "_PS_" + str(current_ps)
                ps = b_dat.particles[ps_name]
                ps.frame_end = frame

            return None

        def PB_note_evt(obj, frame, note, velocity):
            """ PB = Paper Ball
            Place note_on with Channel object, velocity and keyframe
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
            # To avoid pb slowly grow before the note
            if velocity != self.last_note_status[note]:
                PB_note_evt(obj, frame - self.curve, note, self.last_note_status[note])
            mod = obj.modifiers[1]
            mod.strength = (velocity / 127) * 5
            mod.keyframe_insert(data_path='strength', frame=frame)
            self.last_note_status[note] = velocity
            return None

        # Main - add_evt - For now suppose all type evt is note_on or note_off
        # Dispatch by type of object

        # Animate always custom properties of object
        obj_name = self.visual_type + "_" + str(self.idx) + "_" + str(note)
        # if object doesn't exist, it's probabilly a XX model
        if obj_name not in b_dat.objects:
            return None
        obj = b_dat.objects[obj_name]
        obj['velocity'] = velocity
        obj.keyframe_insert(data_path="""["velocity"]""", frame=frame)

        # Animate if needed directly the object
        if self.animate == "True":
            if self.visual_type == "BG":
                BG_note_evt(obj, frame, note, velocity)
            elif self.visual_type == "GD":
                GD_note_evt(obj, frame, note, velocity)
            elif self.visual_type == "LT":
                LT_note_evt(obj, frame, note, velocity)
            elif self.visual_type == "FT":
                FT_note_evt(obj, frame, note, velocity)
            elif self.visual_type == "PB":
                PB_note_evt(obj, frame, note, velocity)

        return None


""" ========================= MAIN ========================= """

time_start = time.time()

# Clear system console
os.system("cls")

# Create the principal collection, mean Midi To Blender
col_name = "MTB"
new_collec = create_collection(col_name, b_con.scene.collection, delete=False)

# path and name of midi file - temporary => replaced when this become an add-on
# path = "H:\\Python\\MTB\\data"
path = "D:\\OneDrive\\Blog\\YT_Patrick Mauger\\02 - Midi_To_Blend\\MTB\\data"
filename = "T1_meanwoman"
filemid = path + "\\" + filename + ".mid"
fileaudio = path + "\\" + filename + ".mp3"
filejson = path + "\\" + filename + ".json"

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
    b_con.scene.sequence_editor.sequences_all[filename + ".mp3"].volume = 0.25

# If JSON parameter file with the same name of MIDI file exist then use it for configuration
# Else create it with BG type for all of channels
mtb_data = []  # List of channels
if os.path.exists(filejson):
    jsoninit = False
    # Load json file
    with open(filejson, 'r') as f:
        mtb_data = json.load(f)
else:
    jsoninit = True

# Set pulsation per quarter note (ppq)
# Mean the number of pulsation per round note / 4 = black note
ppq = mid.ticks_per_beat

# Init Max frame number founded for all channel, mean the end of animation
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

# Dictionnary of Channel <= receive object Channel_Class
ChannelList = {}

""" STEP 1 - Creating the 3D channel vizualisation objects """
l_channel = []
name_of_channel = {}
list_channel_notes = {}
# Fill l_channel with all channels found in all tracks
# and set some channel parameters
for current_track, track in enumerate(mid.tracks):
    for msg in track:
        if msg.type == ('note_on'):
            if msg.channel not in l_channel:
                l_channel.append(msg.channel)
                name_of_channel[msg.channel] = track.name  # most of the time one track equal one channel
                list_channel_notes[msg.channel] = []
            if msg.note not in list_channel_notes[msg.channel]:
                list_channel_notes[msg.channel].append(msg.note)

l_channel = sorted(l_channel)
# Create one vizualisation object per channel
for cur_chan in l_channel:
    list_channel_notes[cur_chan] = sorted(list_channel_notes[cur_chan])
    if jsoninit:
        mtb_channel = {}
        mtb_channel["Channel"] = cur_chan
        mtb_channel["Locked"] = "False"
        mtb_channel["Name"] = name_of_channel[cur_chan]
        mtb_channel["Type"] = "BG"
        mtb_channel["Template"] = ""
        mtb_channel["Animate"] = "True"
        mtb_data.append(mtb_channel)
        ChannelList[cur_chan] = Channel_Class(cur_chan, list_channel_notes[cur_chan], name_of_channel[cur_chan], mtb_channel)
    else:
        mtb_channel = search_channel_in_mtb_data(cur_chan)
        ChannelList[cur_chan] = Channel_Class(cur_chan, list_channel_notes[cur_chan], name_of_channel[cur_chan], mtb_channel)

# Save json file if initialising
if jsoninit:
    with open(filejson, 'w') as f:
        f.write(json.dumps(mtb_data, indent=4))

""" STEP 2 - Main LOOP on midifile track for set all events """
for current_track, track in enumerate(mid.tracks):
    print('Parse track {}: {} evt(s)'.format(current_track, len(track)))

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

        # Filter meta and sysex message
        # Notice : They haven't notion of channel
        if msg.is_meta or msg.type == "sysex":
            continue

        # Check if note_on with velocity 0 will become note_off
        if (msg.type == 'note_on') and (msg.velocity == 0):
            msgtype = 'note_off'
        else:
            msgtype = msg.type

        # If note_on or note_off invoke Class function appropriate
        if msgtype in ('note_on', 'note_off'):
            velocity = msg.velocity * (msgtype == 'note_on')  # to avoid note_off with velocity != 0
            ChannelList[msg.channel].add_evt(msgtype, current_frame, msg.note, velocity)

        # here, later, how to deal with other msg type like
        # control_change
        # program_change
        # pitchwheel
        # aftertouch
        # and so on...

    # Manage the last frame number : mean the end of animation
    if current_frame > max_num_frame:
        max_num_frame = current_frame

# Add one second at the end of animation
b_scn.frame_end = max_num_frame + framerate

print("Script Finished: %.4f sec" % (time.time() - time_start))

# End of script - Enjoy
