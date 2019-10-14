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
# version = 1.009
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
    mat = b_dat.materials.new(name=name_of_color)
    mat.use_nodes = True
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
    # b_ops.object.modifier_apply({"OBJECT": obj_cube}, apply_as='DATA', modifier="Bevel")  # https://blender.stackexchange.com/questions/133291/scriptinghow-to-correctly-add-a-boolean-modifer-to-an-object

    assign_to_collection(collect, obj_cube)

    return obj_cube


def add_plane(collect, name_of_plane, material, x, y, z, emp_par):
    """ Create a Plane Mesh
    IN
        collect         obj     collection
        name_of_cube    str     name of created cube
        x, y, z         float   coordinates
        mat             obj     material
    OUT
        The object cube created
    """
    b_ops.mesh.primitive_plane_add(size=4, enter_editmode=False, location=(0, 0, 0))

    # ToDO remark : Assume the last plane created is named "Plane"
    # because this name is free... Dangerous
    obj_plane = b_dat.objects.get("Plane")
    obj_plane.name = name_of_plane
    obj_plane.parent = emp_par
    obj_plane.data.materials.append(material)

    assign_to_collection(collect, obj_plane)

    return obj_plane


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


def add_icosphere(collect, name_of_icosphere, material, x, y, z, emp_par):
    """ Create a icosphere
    IN
        collect             obj     collection
        name_of_icosphere   str     name of created light
        x, y, z             float   coordinates
    OUT
        The object icosphere created
    """

    b_ops.mesh.primitive_ico_sphere_add(radius=0.5, subdivisions=2, enter_editmode=False, location=(x, y, z))
    obj_icosphere = b_dat.objects.get("Icosphere")
    obj_icosphere.name = name_of_icosphere
    assign_to_collection(collect, obj_icosphere)
    obj_icosphere.parent = emp_par

    return obj_icosphere


def add_cylinder(collect, name_of_cylinder, material, x, y, z, emp_par):
    """ Create a cylinder
    IN
        collect             obj     collection
        name_of_cylinder    str     name of created light
        x, y, z             float   coordinates
    OUT
        The object icosphere created
    """

    b_ops.mesh.primitive_cylinder_add(radius=1, depth=0.2, enter_editmode=False, location=(x, y, z))

    obj_cylinder = b_dat.objects.get("Cylinder")
    obj_cylinder.name = name_of_cylinder
    assign_to_collection(collect, obj_cylinder)
    obj_cylinder.parent = emp_par

    return obj_cylinder


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
        self.last_note_status_FS = {}   # same as last_note_status but for FS vizualisation Target
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
            obj_model = add_icosphere(col_obj, col_name + "_template", material, -50 * self.cf, self.idx * self.cf, 0, emp_par)

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


        def Channel_is_FS():
            """
            Instanciate with a channel typed : FS - Fountain Solo
            """
            col_name = 'FS_' + str(self.idx)
            # Create collection for this channel
            col_obj = create_collection(col_name, new_collec, delete=True)
            # Create the empty parent off all light
            emp_par_name = 'FS_' + str(self.idx) + '_Parent'
            emp_par = add_empty(col_obj, emp_par_name, 0, self.idx * self.cf, 4)
            # Create material
            material = Create_material_simple(col_name + "_mat", 0.0, 0.0, 0.0, True)

            # Create UV spheres to become the particle object represent note
            # Multiple Object for multiple type of note : note, demi note and quarter note and so on.
            b_ops.mesh.primitive_uv_sphere_add(radius=8, enter_editmode=False, location=(-50 * self.cf, 0, -20))
            obj_fountain_pt = b_dat.objects.get("Sphere")
            obj_fountain_pt.name = col_name + "_particle"
            assign_to_collection(col_obj, obj_fountain_pt)
            obj_fountain_pt.parent = emp_par
            obj_fountain_pt.data.materials.append(material)

            # Create template
            # Create icosphere for the emitter
            # All particles stuff are created with event note_on/note_off
            obj_model = add_cylinder(col_obj, col_name + "_template", material, -50 * self.cf, self.idx * self.cf, 0, emp_par)

            # Duplicate template, only one for all notes
            fountain_name = col_name
            add_duplicate_linked(col_obj, fountain_name, 0, 0, 4, obj_model)

            mat_black = Create_material_simple(col_name + "_mat_black", 0.0, 0.0, 0.0, False)
            mat_white = Create_material_simple(col_name + "_mat_white", 1.0, 1.0, 1.0, False)

            theta = math.radians(360)  # 2 Pi, just one circle
            alpha = theta / 12  # 12 is the Number of notes per octave

            # 11 octaves
            for o in range(11):
                # Create 12 notes targets (0-11)
                for n in range(12):
                    plane_name = col_name + "_Target_" + str(o) + "_" + str(n)
                    if len(octave[n]) == 2:
                        obj_plane = add_plane(col_obj, plane_name, mat_black, 0, 0, 0, emp_par)
                    else:
                        obj_plane = add_plane(col_obj, plane_name, mat_white, 0, 0, 0, emp_par)
                    b_ops.transform.resize(value=(0.3, 0.4 + (o / 6), 1), orient_type='GLOBAL')
                    b_ops.object.modifier_add(type='COLLISION')
                    angle = (12 - n) * alpha
                    distance = (o * 1.25) + 4
                    x = (distance * math.cos(angle))
                    y = (distance * math.sin(angle))
                    obj_plane.location = (x, y, 0.0)
                    rot = math.radians( math.degrees( angle))
                    obj_plane.rotation_euler = (0, 0, rot)

            # add properties to obj_model for channel properties
            obj_model['pitchbend'] = 0

            # initialize note status fo FS
            for note in self.list_note:
                self.last_note_status_FS[note] = 0

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
        # Type FS = Fountain Solo
        elif self.visual_type == "FS":
            Channel_is_FS()
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
                ps.active.settings.lifetime = framerate * 20  # *4
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


        def animate_target(obj, frame, note, velocity):
            """
            Animate the target for one note
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note on velocity
            OUT
                None
            """
            if velocity != self.last_note_status_FS[note]:
                animate_target(obj, frame - self.curve, note, self.last_note_status_FS[note])

            # Find target
            target_name = 'FS_' + str(self.idx) + '_Target_' + str(midinote_to_octave[note]) + '_' + str(midinote_to_note_num[note])
            obj = b_dat.objects[target_name]
            if velocity != 0:
                scale_y = 0.2 + (midinote_to_octave[note] / 6)
            else:
                scale_y = 0.4 + (midinote_to_octave[note] / 6)
            obj.scale = obj.scale.x, scale_y, obj.scale.z
            obj.keyframe_insert(data_path='scale', frame=frame)
            obj['velocity'] = velocity
            obj.keyframe_insert(data_path="""["velocity"]""", frame=frame)
            self.last_note_status_FS[note] = velocity
            return None

        def FS_note_evt(obj, frame, note, velocity):
            """ FS = Fountain Solo
            Activate emitter of fountain solo accordingly to velocity
            Using 1 new PS (Particles System) with frame_start/frame_end and not keyframed
            Self.last_note_status contain the last current PS in progress
            Emit only one particule to reach note designed by plane
            IN
                frame       int     Index of frame
                note        int     note number (0-127)
                velocity    int     note velocity
            OUT
                None
            """
            animate_target(obj, frame, note, velocity)

            # Create new PS with set of frame_start
            # This vizualisation react only to note_on
            if velocity != 0:

                # empirical values of the coefficient applied to z velocity following the octave
                coef_z = {
                     0:7.8,
                     1:6.3,
                     2:5.5,
                     3:5.0,
                     4:4.7,
                     5:4.45,
                     6:4.3,
                     7:4.2,
                     8:4.1,
                     9:4.0,
                    10:3.8,
                    11:3.6
                }

                current_ps = self.last_note_status[note] + 1

                # add particle system to the ico sphere emitter
                ps = obj.modifiers.new(name='particles', type='PARTICLE_SYSTEM')
                ps = obj.particle_systems
                name_of_ps = obj.name + "_PS_" + str(current_ps)
                ps.active.name = name_of_ps

                # Set all usefull parameters to emitter
                obj_particle_name = 'FS_' + str(self.idx) + "_particle"
                obj_particle = b_dat.objects[obj_particle_name]
                ps.active.settings.name = name_of_ps
                ps.active.settings.render_type = 'OBJECT'
                ps.active.settings.instance_object = obj_particle
                ps.active.settings.count = 1

                # Be sure to initialize frame_end before frame_start because
                # frame_start can't be greather than frame_end at any time
                delay_time = 39  # Probabily use math with coef_z
                ps.active.settings.frame_end = frame - delay_time + (framerate * 4)
                ps.active.settings.frame_start = frame - delay_time

                ps.active.settings.lifetime = framerate * 4
                ps.active.settings.emit_from = 'FACE'
                ps.active.settings.distribution = 'GRID'
                ps.active.settings.grid_resolution = 1
                ps.active.settings.grid_random = 0

                theta = math.radians(360)  # 2 Pi, just one circle
                alpha = theta / 12  # 12 is the Number of notes per octave

                angle = (12 - midinote_to_note_num[note]) * alpha
                distance = midinote_to_octave[note] + 2
                x = (distance * math.cos(angle))
                y = (distance * math.sin(angle))
                z = coef_z[midinote_to_octave[note]]

                ps.active.settings.object_align_factor[0] = x
                ps.active.settings.object_align_factor[1] = y
                ps.active.settings.object_align_factor[2] = z

                self.last_note_status[note] = current_ps

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
        # Deal with mono object for all notes or multi objects each by note
        if self.visual_type == "FS":
            obj_name = self.visual_type + "_" + str(self.idx)
        else:
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
            elif self.visual_type == "FS":
                FS_note_evt(obj, frame, note, velocity)
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
filename = "T1_VT_Medley_Rock"
filemid = path + "\\" + filename + ".mid"
fileaudio = path + "\\" + filename + ".mp3"
filejson = path + "\\" + filename + ".json"

# Open MIDIFile with the module MIDO
mid = MidiFile(filemid)
print("Midi type = "+str(mid.type))

# type = 0 - (single track): all messages are in one track and use the same tempo and start at the same time
# type = 1 - (synchronous): all messages are in separated tracks and use the same tempo and start at the same time
# type = 2 - (asynchronous): each track is independent of the others for tempo and for start - not yet supported
if (mid.type == 2):
    raise RuntimeError("Only type 0 or 1, type 2 is not yet supported")

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

# Some musical definitions
octave = {0:"C",1:"C#",2:"D",3:"D#",4:"E",5:"F",6:"F#",7:"G",8:"G#",9:"A",10:"A#",11:"B"}

# To convert easily from midi notation to name of note
midinote_to_note_alpha = {
   0:"C",  1:"C#",  2:"D",  3:"D#",  4:"E",  5:"F",  6:"F#",  7:"G",  8:"G#",  9:"A", 10:"A#", 11:"B"
 ,12:"C", 13:"C#", 14:"D", 15:"D#", 16:"E", 17:"F", 18:"F#", 19:"G", 20:"G#", 21:"A", 22:"A#", 23:"B"
 ,24:"C", 25:"C#", 26:"D", 27:"D#", 28:"E", 29:"F", 30:"F#", 31:"G", 32:"G#", 33:"A", 34:"A#", 35:"B"
 ,36:"C", 37:"C#", 38:"D", 39:"D#", 40:"E", 41:"F", 42:"F#", 43:"G", 44:"G#", 45:"A", 46:"A#", 47:"B"
 ,48:"C", 49:"C#", 50:"D", 51:"D#", 52:"E", 53:"F", 54:"F#", 55:"G", 56:"G#", 57:"A", 58:"A#", 59:"B"
 ,60:"C", 61:"C#", 62:"D", 63:"D#", 64:"E", 65:"F", 66:"F#", 67:"G", 68:"G#", 69:"A", 70:"A#", 71:"B"
 ,72:"C", 73:"C#", 74:"D", 75:"D#", 76:"E", 77:"F", 78:"F#", 79:"G", 80:"G#", 81:"A", 82:"A#", 83:"B"
 ,84:"C", 85:"C#", 86:"D", 87:"D#", 88:"E", 89:"F", 90:"F#", 91:"G", 92:"G#", 93:"A", 94:"A#", 95:"B"
 ,96:"C", 97:"C#", 98:"D", 99:"D#",100:"E",101:"F",102:"F#",103:"G",104:"G#",105:"A",106:"A#",107:"B"
,108:"C",109:"C#",110:"D",111:"D#",112:"E",113:"F",114:"F#",115:"G",116:"G#",117:"A",118:"A#",119:"B"
,120:"C",121:"C#",122:"D",123:"D#",124:"E",125:"F",126:"F#",127:"G"
}

# To convert easily from midi notation to number of note
midinote_to_note_num = {
   0:0,  1:1,  2:2,  3:3,  4:4,  5:5,  6:6,  7:7,  8:8,  9:9, 10:10, 11:11
 ,12:0, 13:1, 14:2, 15:3, 16:4, 17:5, 18:6, 19:7, 20:8, 21:9, 22:10, 23:11
 ,24:0, 25:1, 26:2, 27:3, 28:4, 29:5, 30:6, 31:7, 32:8, 33:9, 34:10, 35:11
 ,36:0, 37:1, 38:2, 39:3, 40:4, 41:5, 42:6, 43:7, 44:8, 45:9, 46:10, 47:11
 ,48:0, 49:1, 50:2, 51:3, 52:4, 53:5, 54:6, 55:7, 56:8, 57:9, 58:10, 59:11
 ,60:0, 61:1, 62:2, 63:3, 64:4, 65:5, 66:6, 67:7, 68:8, 69:9, 70:10, 71:11
 ,72:0, 73:1, 74:2, 75:3, 76:4, 77:5, 78:6, 79:7, 80:8, 81:9, 82:10, 83:11
 ,84:0, 85:1, 86:2, 87:3, 88:4, 89:5, 90:6, 91:7, 92:8, 93:9, 94:10, 95:11
 ,96:0, 97:1, 98:2, 99:3,100:4,101:5,102:6,103:7,104:8,105:9,106:10,107:11
,108:0,109:1,110:2,111:3,112:4,113:5,114:6,115:7,116:8,117:9,118:10,119:11
,120:0,121:1,122:2,123:3,124:4,125:5,126:6,127:7
}

# To convert easily from midi notation to number of octave

midinote_to_octave = {
  0:0,   1:0,   2:0,   3:0,   4:0,   5:0,   6:0,   7:0,   8:0,   9:0,  10:0,  11:0,
 12:1,  13:1,  14:1,  15:1,  16:1,  17:1,  18:1,  19:1,  20:1,  21:1,  22:1,  23:1,
 24:2,  25:2,  26:2,  27:2,  28:2,  29:2,  30:2,  31:2,  32:2,  33:2,  34:2,  35:2,
 36:3,  37:3,  38:3,  39:3,  40:3,  41:3,  42:3,  43:3,  44:3,  45:3,  46:3,  47:3,
 48:4,  49:4,  50:4,  51:4,  52:4,  53:4,  54:4,  55:4,  56:4,  57:4,  58:4,  59:4,
 60:5,  61:5,  62:5,  63:5,  64:5,  65:5,  66:5,  67:5,  68:5,  69:5,  70:5,  71:5,
 72:6,  73:6,  74:6,  75:6,  76:6,  77:6,  78:6,  79:6,  80:6,  81:6,  82:6,  83:6,
 84:7,  85:7,  86:7,  87:7,  88:7,  89:7,  90:7,  91:7,  92:7,  93:7,  94:7,  95:7,
 96:8,  97:8,  98:8,  99:8, 100:8, 101:8, 102:8, 103:8, 104:8, 105:8, 106:8, 107:8,
108:9, 109:9, 110:9, 111:9, 112:9, 113:9, 114:9, 115:9, 116:9, 117:9, 118:9, 119:9,
120:10,121:10,122:10,123:10,124:10,125:10,126:10,127:10
}

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
#   take care if there is no tempo at all. Use default tempo 500 000 (120 BPM)
    if tempo_count == 0:
        current_tempo = 500000
    else:
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
        #   ie : pan (10), volume (7), sustain pedal (64), stop all notes (123)
        # program_change
        # pitchwheel
        # aftertouch
        # and so on...

    # Manage the last frame number : mean the end of animation
    if current_frame > max_num_frame:
        max_num_frame = current_frame

# Add one second at the end of animation
b_scn.frame_end = max_num_frame + framerate

print("Script Finished: %.2f sec" % (time.time() - time_start))

# End of script - Enjoy
