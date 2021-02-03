import bpy
import bmesh
import mathutils
import math
import random
import time
import os
import os.path
import json
# for material
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper

# How to install a new python module in the blender (here mido) :
# Blender 2.8  => http://www.codeplastic.com/2019/03/12/how-to-install-python-modules-in-blender/
# Blender 2.9x => https://b3d.interplanety.org/en/how-to-install-required-packages-to-the-blender-python-with-pip/
# Mido is a library for working with MIDI messages and ports.
# It’s designed to be as straight forward and Pythonic as possible:
# https://mido.readthedocs.io/en/latest/installing.html
from mido import MidiFile

# Global blender objects
b_dat = bpy.data
b_con = bpy.context
b_scn = b_con.scene
b_ops = bpy.ops

# ********************************************************************
# Midi_To_Blend
# version = 1.011
# Blender version = 2.8
# Author = Patrick Mauger
# Web Site = docouatzat.com
# Mail = docouatzat@gmail.com
#
# Licence used = GNU General Public License V3
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


def add_empty(collect, name_of_empty, location):
    """ Create an empty
    IN
        collect     obj     collection
        name        str     name of created empty
        x, y, z     float   coordinates
    OUT
        The object empty created
    """
    o = bpy.data.objects.new("empty", None)
    b_con.scene.collection.objects.link(o)
    o.location = location
    o.empty_display_size = 2
    o.empty_display_type = 'PLAIN_AXES'
    o.name = name_of_empty
    assign_to_collection(collect, o)
    return o


def duplicate_linked(collect, name, location, model):
    """ Create a duplicate and linked object from template
    IN
        collect         obj     collection
        name_of_object  str     name of new object from duplicate
        location        float   coordinates
        template        obj     object template
    OUT
        The object created from duplication
    """
    if model:
        obj = model.copy()
        obj.name = name
        obj.location = location

        # add properties to all objects/notes and fix it to frame 0
        obj['velocity'] = 0
        obj.keyframe_insert(data_path="""["velocity"]""", frame=0)

        collect.objects.link(obj)
    return obj


def apply_modifiers(obj, scene, render=False):  # Bug
    """ Apply all modifiers on an object """
    settings_type = 'PREVIEW' if not render else 'RENDER'
    obj.data = obj.to_mesh(preserve_all_data_layers=True, depsgraph=None)
    obj.modifiers.clear()


def add_VBO_grid(collect, parent, material, location, sx, sy, list_note, note_object):
    """ Create a Grid Mesh and 127 empty hooked to 127 faces
    IN
        collect         obj     collection
        name_of_grid    str     name of created grid
        location         float   coordinates
        mat             obj     material
        sx              int     subdivisions x
        sy              int     subdivisions y
        list_note       list    list of used notes
    OUT
        The object grid created
    """
    o = add_VBO(
        Type="Grid",
        Col=collect,
        Name=collect.name,
        Mat=material,
        Size=64.0,
        Location=location,
        X_Seg=37,
        Y_Seg=34,
        Parent=parent
    )

    # Add a hook for each note used on respective face
    me = o.data
    for x in range(1, 127):
        if x not in list_note:
            continue
        # Math to distribute hooks with harmony on faces
        num_face = ((x * 3 - 2) + ((((x - 1) // 12) + 1) * 72)) - 36
        # Select vertice
        fc = b_dat.meshes[me.name].polygons[num_face]
        verts_in_face = fc.vertices[:]
        # Create vertex group
        group = o.vertex_groups.new()
        group.add(verts_in_face, 1.0, 'ADD')
        group.name = collect.name + "_VG_" + str(x)
        # Empty for parenting the hook to
        emp_name = collect.name + "_" + str(x)
        emp_hook = add_empty(collect, emp_name, (0, 0, 0))
        emp_hook.location = o.location
        emp_hook.parent = parent
        note_object[x] = emp_hook
        # Create the hook
        mod = o.modifiers.new(name=collect.name + "_" + str(x), type='HOOK')
        mod.object = emp_hook
        mod.vertex_group = group.name

    return o


def add_VBO_light(collect, name, location, parent):
    """ Create a Light
    IN
        collect         obj     collection
        name_of_light   str     name of created light
        x, y, z         float   coordinates
    OUT
        The object light created
    """
    # Create light datablock, set attributes
    obj_data = b_dat.lights.new(name=name, type='POINT')
    obj_data.energy = 0  # mean no note velocity at this time

    # Create new object with our light datablock
    obj_light = b_dat.objects.new(name=name, object_data=obj_data)
    obj_light.location = location
    obj_light.data.color = rgb_random_color()
    obj_light.parent = parent

    b_con.view_layer.active_layer_collection.collection.objects.link(obj_light)
    assign_to_collection(collect, obj_light)

    return obj_light


def add_VBO_mball(collect, name, material, location, parent):
    """ Create metaball
    IN
        collect             obj     collection
        name_of_icosphere   str     name of created metaball
        x, y, z             float   coordinates
    OUT
        The object sphere created
    """

    # add metaball object
    mball = bpy.data.metaballs.new(name)
    obj = bpy.data.objects.new(name, mball)
    b_con.scene.collection.objects.link(obj)

    # resolution is based on radius
    mball.resolution = 0.25
    mball.render_resolution = mball.resolution * 0.25
    mball.threshold = 0.8
    obj.scale = (2.0, 2.0, 2.0)
    obj.parent = parent
    obj.location = location

    assign_to_collection(collect, obj)

    return obj


def add_VBO_pb(collect, name_of_pb, material, x, y, z, empty_parent):
    """ Create a Paper Ball
    IN
        collect         obj     collection
        name_of_pb      str     name of Paper Ball
        x, y, z         float   coordinates
        mat             obj     material
    OUT
        The object Paper Ball created
    """
    obj_pb = add_VBO(
        Type="UVSphere",
        Col=collect,
        Name=name_of_pb,
        Mat=material,
        U_Seg=8,
        V_Seg=8,
        Location=(x, y, z),
        Diameter=2.0,
        Parent=empty_parent
    )

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

    return obj_pb


def add_VBO(**kwargs):
    """
    Add Visual Blender Object - Overloading all objects creations
    Take every parameters and manage default values for each
    IN
        Type = Cube, Plane
        many args accordingly with type of object
        If nothing in entry, create a default cube
    OUT
        The new object instanciated
    """
    # set default values
    TypeObj = kwargs.get("Type", "Cube")
    collect = kwargs.get("Col", "Error Col needed")
    parent = kwargs.get("Parent", "Error Parent needed")
    name = kwargs.get("Name", "NotNamed")
    mat = kwargs.get("Mat", Create_material_simple(name + "mat", 0, 0, 0, True))
    size = kwargs.get("Size", 1.0)
    location = kwargs.get("Location", (0.0, 0.0, 0.0))
    scale = kwargs.get("Scale", (1.0, 1.0, 1.0))
    rotate = kwargs.get("Rotate", (0.0, 0.0, 0.0))
    X_Seg = kwargs.get("X_Seg", 1)
    Y_Seg = kwargs.get("Y_Seg", 1)
    Subdivisions = kwargs.get("Subdivisions", 1)
    U_Seg = kwargs.get("U_Seg", 1)
    V_Seg = kwargs.get("V_Seg", 1)
    Diameter = kwargs.get("Diameter", 1)
    Segments = kwargs.get("Segments", 16)
    Depth = kwargs.get("Depth", 1)
    bevel = kwargs.get("Bevel", 0.0)

    # Create an empty mesh and the object.
    mesh = b_dat.meshes.new(TypeObj)
    o = b_dat.objects.new(TypeObj, mesh)
    b_con.scene.collection.objects.link(o)
    bm = bmesh.new()

    # Construct the bmesh following the Type and assign it to the blender mesh.
    if TypeObj == "Cube":
        bmesh.ops.create_cube(bm, size=size)
    if TypeObj == "Plane":
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size)
    if TypeObj == "Grid":
        bmesh.ops.create_grid(bm, x_segments=X_Seg, y_segments=Y_Seg, size=size)
    if TypeObj == "IcoSphere":
        bmesh.ops.create_icosphere(bm, subdivisions=Subdivisions, diameter=Diameter)
    if TypeObj == "UVSphere":
        bmesh.ops.create_uvsphere(bm, u_segments=U_Seg, v_segments=V_Seg, diameter=Diameter)
    if TypeObj == "Cylinder":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=Segments, diameter1=Diameter, diameter2=Diameter, depth=Depth)

    bm.to_mesh(mesh)
    bm.free()

    # Set generic values to the object created
    o.name = name
    o.parent = parent
    o.location = location
    o.scale = scale
    o.rotation_euler = rotate
    o.data.materials.append(mat)

    # Set a bevel if needed
    if bevel != 0.0:
        mod = o.modifiers.new(name="Bevel", type='BEVEL')
        mod.width = bevel

    # Assign to collection
    assign_to_collection(collect, o)

    return o


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


class Tempo_Class:

    # Channel initializations
    def __init__(self, track_to_analyze):
        """
        Initialization of the Class Tempo_MAP
        IN
            Track carrying the tempo instructions
        OUT
            The new object instanciated
            The tempo MAP is initialized with instanciation
        """
        # Parameters
        self.track = track_to_analyze       # track to analyze, always the track 0 for midi type 0 & 1
        self.tempo_map = [[]]               # 2D Matrice contain usefull data

        time_in_ticks_cumul = 0
        ticks_previous = 0
        tempo_previous = 0
        sec_cumul = 0

        # Generate the tempo MAP for the track
        for msg in self.track:
            time_in_ticks_cumul += msg.time
            if msg.type == 'set_tempo':
                if msg.tempo != 0:
                    row = []
                    tempo = msg.tempo
                    bpm = int(60000/(tempo/1000))
                    delta_ticks = time_in_ticks_cumul - ticks_previous
                    sec_per_ticks = (tempo_previous / ppq) / 1000000
                    sec = delta_ticks * sec_per_ticks
                    sec_cumul += sec

                    # memorize tempo MAP
                    row.append(time_in_ticks_cumul)     # 0
                    row.append(tempo)                   # 1
                    row.append(bpm)                     # 2
                    row.append(delta_ticks)             # 3
                    row.append(sec_per_ticks)           # 4
                    row.append(sec)                     # 5
                    row.append(sec_cumul)               # 6
                    self.tempo_map.append(row)

                    ticks_previous = time_in_ticks_cumul
                    tempo_previous = tempo

        return None

    # Return the frame calculated with absolute time in seconds from ticks cumul provided
    def frame(self, ticks_cumul):

        if ticks_cumul == 0:
            return 0

        # Search from the nearest cumul ticks in the past into tempo_map
        for row in self.tempo_map:
            if row:
                if row[0] > ticks_cumul:
                    break
                else:
                    founded_row = row

        seconds = founded_row[6]
        delta = ticks_cumul - founded_row[0]
        sec_per_ticks = (founded_row[1] / ppq) / 1000000
        seconds += delta * sec_per_ticks
        frame = seconds * framerate

        return frame


def Channel_is_BG(self, col_obj, empty_parent, material):
    """
    Instanciate with a channel typed : BG - BarGraphs
    """
    # Create template
    if self.template != "":
        obj_model = b_dat.objects.get(self.template)
    else:
        obj_model = add_VBO(
            Type="Cube",
            Col=col_obj,
            Name=col_obj.name + "_template",
            Mat=material,
            Size=2.0,
            Location=(-50 * self.cf, self.idx * self.cf, 0),
            Bevel=0.1,
            Parent=empty_parent
        )

    current_place = 0
    median_place = self.count_place // 2
    # Duplicate template, one by note
    for x in range(self.min_note, self.max_note + 1):
        if x in self.list_note:
            self.note_object[x] = duplicate_linked(
                collect=col_obj,
                name=col_obj.name + "_" + str(x),
                location=((current_place - median_place) * self.cf, 0, 0),
                model=obj_model
            )
        current_place += 1

    # add properties to obj_model for channel properties
    self.note_object[128] = obj_model

    return None


def BG_note_evt(self, obj, frame, note, velocity):
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
        BG_note_evt(self, obj, frame - self.curve, note, self.last_note_status[note])
    obj.scale = 1.0, 1.0, (velocity / 16) + 1.0
    obj.keyframe_insert(data_path='scale', frame=frame)
    vel = velocity - self.last_note_status[note]
    vec = mathutils.Vector((0.0, 0.0, vel / 16))
    obj.location = obj.location + vec
    obj.keyframe_insert(data_path='location', frame=frame)
    obj.keyframe_insert(data_path="""["velocity"]""", frame=frame)
    self.last_note_status[note] = velocity
    return None


def Channel_is_GD(self, col_obj, empty_parent, material):
    """
    Instanciate with a channel typed : GD - Grid
    """
    # Create grid x = (12x3) + 1) et y = (11*3) + 1 => (12*11 = 132 notes)
    obj_master = add_VBO_grid(
        collect=col_obj,
        parent=empty_parent,
        material=material,
        location=(0, 0, 0),
        sx=37,
        sy=34,
        list_note=self.list_note,
        note_object=self.note_object
    )

    self.note_object[128] = obj_master

    return None


def GD_note_evt(self, obj, frame, note, velocity):
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
        GD_note_evt(self, obj, frame - self.curve, note, self.last_note_status[note])
    vel = velocity - self.last_note_status[note]
    vec = mathutils.Vector((0.0, 0.0, vel / 6))
    obj.location = obj.location + vec
    obj.keyframe_insert(data_path='location', frame=frame)
    self.last_note_status[note] = velocity
    return None


def Channel_is_LT(self, col_obj, empty_parent):
    """
    Instanciate with a channel typed : LT - Light
    """
    # Create lampshade part hair
    mat_drak_grey = Create_material_simple(col_name + "_mat_dark_grey", 0.3, 0.3, 0.3, False)
    obj_model_part = add_VBO(
        Type="Cube",
        Col=col_obj,
        Name=col_obj.name + "_cube_strand",
        Mat=mat_drak_grey,
        Size=1.0,
        Location=(-50 * self.cf, self.idx * self.cf, 0),
        Parent=empty_parent
    )

    current_place = 0
    median_place = self.count_place // 2
    # Create one light by used note
    for x in range(self.min_note, self.max_note + 1):
        if x in self.list_note:
            self.note_object[x] = add_VBO_light(
                collect=col_obj,
                name=col_obj.name + "_Light_" + str(x),
                location=((current_place - median_place) * self.cf * 3, 0, 4),
                parent=empty_parent)
            # Create lampshade part hair
            obj_ics = add_VBO(
                Type="IcoSphere",
                Col=col_obj,
                Name=col_obj.name + "_Lampshade_" + str(x),
                Mat=mat_drak_grey,
                Location=((current_place - median_place) * self.cf * 3, 0, 4),
                Subdivisions=4,
                Diameter=4.0,
                Parent=empty_parent
            )
            # add particle system hair to the icosphere
            ps = obj_ics.modifiers.new(name='particles', type='PARTICLE_SYSTEM')
            ps = obj_ics.particle_systems
            name_of_ps = col_obj.name + "_PS_LS_" + str(x)
            ps.active.name = name_of_ps
            ps.active.settings.type = 'HAIR'
            ps.active.settings.emit_from = 'VERT'
            ps.active.settings.render_type = 'OBJECT'
            ps.active.settings.instance_object = obj_model_part
            ps.active.settings.count = 1000
            ps.active.settings.hair_length = 10
            ps.active.settings.hair_step = 2
            obj_ics.show_instancer_for_viewport = False
            obj_ics.show_instancer_for_render = False
#            ps.active.settings.show_instancer_for_render = False
#            ps.active.settings.show_instancer_for_viewport = False
        current_place += 1

    self.note_object[128] = obj_model_part

    return None


def LT_note_evt(self, obj, frame, note, velocity):
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
        LT_note_evt(self, obj, frame - self.curve, note, self.last_note_status[note])
    energy = velocity * 1000
    obj.data.energy = energy
    obj.data.keyframe_insert(data_path='energy', frame=frame)
    self.last_note_status[note] = velocity
    return None


def Channel_is_FT(self, col_obj, empty_parent, material):
    """
    Instanciate with a channel typed : FT - Fountain
    """
    # Create small UV sphere to become the particle object
    add_VBO(
        Type="UVSphere",
        Col=col_obj,
        Name=col_obj.name + "_particle",
        Mat=material,
        U_Seg=8,
        V_Seg=8,
        Location=(0, 0, -20),
        Diameter=2.0,
        Parent=empty_parent
    )
    # Create template
    obj_model = add_VBO(
        Type="IcoSphere",
        Col=col_obj,
        Name=col_obj.name + "_particle",
        Mat=material,
        Location=(-50 * self.cf, self.idx * self.cf, 0),
        Subdivisions=2,
        Diameter=0.5,
        Parent=empty_parent
    )

    current_place = 0
    median_place = self.count_place // 2
    # Duplicate template, one by note
    for x in range(self.min_note, self.max_note + 1):
        if x in self.list_note:
            fountain_name = col_obj.name + "_" + str(x)
            self.note_object[x] = duplicate_linked(
                collect=col_obj,
                name=fountain_name,
                location=((current_place - median_place) * self.cf, 0, 0),
                model=obj_model)
        current_place += 1

    self.note_object[128] = obj_model

    return None


def FT_note_evt(self, obj, frame, note, velocity):
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


def Channel_is_FS(self, col_obj, empty_parent, material):
    """
    Instanciate with a channel typed : FS - Fountain Solo
    """

    # Create UV spheres to become the particle object represent note
    # Multiple Object for multiple type of note : note, demi note and quarter note and so on.
    add_VBO(
        Type="UVSphere",
        Col=col_obj,
        Name=col_obj.name + "_particle",
        Mat=material,
        U_Seg=8,
        V_Seg=8,
        Location=(-50 * self.cf, 0, -20),
        Diameter=8.0,
        Parent=empty_parent
    )

    # Create emitter
    obj_model = add_VBO(
        Type="Cylinder",
        Col=col_obj,
        Name=col_obj.name + "_template",
        Mat=material,
        Location=(-50 * self.cf, self.idx * self.cf, 0),
        Subdivisions=2,
        Diameter=1.0,
        Depth=0.2,
        Parent=empty_parent
    )

    # Duplicate template, only one for all notes
    fountain_name = col_obj.name
    self.note_object[0] = duplicate_linked(
        collect=col_obj,
        name=fountain_name,
        location=(0, 0, 4),
        model=obj_model
    )

    mat_black = Create_material_simple(col_name + "_mat_black", 0.0, 0.0, 0.0, False)
    mat_white = Create_material_simple(col_name + "_mat_white", 1.0, 1.0, 1.0, False)

    theta = math.radians(360)  # 2 Pi, just one circle
    alpha = theta / 12  # 12 is the Number of notes per octave

    # 11 octaves
    for o in range(11):
        # Create 12 notes targets (0-11)
        for n in range(12):
            plane_name = col_obj.name + "_Target_" + str(o) + "_" + str(n)
            angle = (12 - n) * alpha
            distance = (o * 1.25) + 4
            x = (distance * math.cos(angle))
            y = (distance * math.sin(angle))
            rot = math.radians(math.degrees(angle))
            if len(octave[n]) == 2:
                obj_plane = add_VBO(
                    Type="Plane",
                    Col=col_obj,
                    Name=plane_name,
                    Mat=mat_black,
                    Size=2.0,
                    Location=(x, y, 0.0),
                    Scale=(0.3, 0.4 + (o/6), 1),
                    Rotate=(0, 0, rot),
                    Parent=empty_parent
                )
            else:
                obj_plane = add_VBO(
                    Type="Plane",
                    Col=col_obj,
                    Name=plane_name,
                    Mat=mat_white,
                    Size=2.0,
                    Location=(x, y, 0.0),
                    Scale=(0.3, 0.4 + (o/6), 1),
                    Rotate=(0, 0, rot),
                    Parent=empty_parent
                )
            obj_plane.modifiers.new(name="Collision", type='COLLISION')

    self.note_object[128] = obj_model

    # initialize note status fo FS
    for note in self.list_note:
        self.last_note_status_FS[note] = 0

    return None


def FS_animate_target(self, obj, frame, note, velocity):
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
        FS_animate_target(self, obj, frame - self.curve, note, self.last_note_status_FS[note])

    # Find target
    octave = str(midinote_to_octave[note])
    num_note = str(midinote_to_note_num[note])
    target_name = 'FS_' + str(self.idx) + '_Target_' + octave + '_' + num_note
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


def FS_note_evt(self, obj, frame, note, velocity):
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
    FS_animate_target(self, obj, frame, note, velocity)

    # Create new PS with set of frame_start
    # This vizualisation react only to note_on
    if velocity != 0:

        # empirical values of the coefficient applied to z velocity following the octave
        coef_z = {
            0:  7.8,
            1:  6.3,
            2:  5.5,
            3:  5.0,
            4:  4.7,
            5:  4.45,
            6:  4.3,
            7:  4.2,
            8:  4.1,
            9:  4.0,
            10: 3.8,
            11: 3.6
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


def Channel_is_SW(self, col_obj, empty_parent, material):
    """
    Instanciate with a channel typed : SW - Splash Wall
    """
    theta = math.radians(360)  # 2 Pi, just one circle
    alpha = theta / 360  # 12 is the Number of notes per octave
    rot = math.radians(math.degrees(90 * alpha))
    # Create Wall
    obj_wall = add_VBO(
        Type="Cube",
        Col=col_obj,
        Name=col_obj.name + '_wall',
        Mat=material,
        Size=1.0,
        Location=(0, 40, 0),
        Scale=(16.0, 16.0, 0.5),
        Rotate=(0, rot, rot),
        Parent=empty_parent
    )
    mod = obj_wall.modifiers.new(name="bing", type='COLLISION')
    mod.settings.stickiness = 10.0
    mod.settings.friction_factor = 1
    mod.settings.friction_random = 1

    # Create Plane after wall to kill particle
    obj_plane = add_VBO(
        Type="Plane",
        Col=col_obj,
        Name=col_obj.name + '_killer_plane',
        Mat=material,
        Size=2.0,
        Location=(0, 41, 0),
        Scale=(8.0, 8.0, 1.0),
        Rotate=(0, rot, rot),
        Parent=empty_parent
    )
    mod = obj_plane.modifiers.new(name="bing", type='COLLISION')
    mod.settings.use_particle_kill = True

    # Create gun
    self.note_object[0] = add_VBO(
        Type="Cylinder",
        Col=col_obj,
        Name=col_obj.name,
        Mat=material,
        Subdivisions=2,
        Diameter=1.0,
        Depth=1.0,
        Scale=(2.0, 2.0, 2.0),
        Rotate=(0, rot, rot),
        Parent=empty_parent
    )

    self.last_note_status[0] = 0  # become a counter of balls created later

    # Creating 12 materials for futures balls.
    Create_material_simple(col_obj.name + "_mat_0",  0.0, 0.0, 1.0, False)  # C  => Blue
    Create_material_simple(col_obj.name + "_mat_1",  0.0, 0.0, 0.0, True)   # C# => Random
    Create_material_simple(col_obj.name + "_mat_2",  0.0, 1.0, 0.0, False)  # D  => Green
    Create_material_simple(col_obj.name + "_mat_3",  0.0, 0.0, 0.0, True)   # D# => Random
    Create_material_simple(col_obj.name + "_mat_4",  1.0, 0.0, 0.0, False)  # E  => Red
    Create_material_simple(col_obj.name + "_mat_5",  0.0, 1.0, 1.0, False)  # F  => ???
    Create_material_simple(col_obj.name + "_mat_6",  0.0, 0.0, 0.0, True)   # F# => Random
    Create_material_simple(col_obj.name + "_mat_7",  1.0, 1.0, 0.0, False)  # G  => ???
    Create_material_simple(col_obj.name + "_mat_8",  0.0, 0.0, 0.0, True)   # G# => Random
    Create_material_simple(col_obj.name + "_mat_9",  1.0, 0.0, 1.0, False)  # A  => ???
    Create_material_simple(col_obj.name + "_mat_10", 0.0, 0.0, 0.0, True)   # A# => Random
    Create_material_simple(col_obj.name + "_mat_11", 0.0, 0.0, 0.0, True)   # B  => Random

    # Create 12 particles metaball type with these 12 colored materials
    for n in range(12):
        part_name = col_obj.name + "_particle_" + str(n)
        mat_name = col_obj.name + "_mat_" + str(n)
        material = b_dat.materials[mat_name]
        add_VBO_mball(
            collect=col_obj,
            name=part_name,
            material=material,
            location=(-50, 0, 0),
            parent=empty_parent
        )
        # add_VBO(
        #     Type="UVSphere",
        #     Col=col_obj,
        #     Name=part_name,
        #     Mat=material,
        #     U_Seg=8,
        #     V_Seg=8,
        #     Location=(-50, 0, 0),
        #     Diameter=1.0,
        #     Parent=empty_parent
        # )

    return None


def SW_note_evt(self, obj, frame, note, velocity):
    """ SW = Splash Wall
    Splash note_on figured by balls on the wall.
    Ball color follow the note and location on the impact follow octave
    IN
        frame       int     Index of frame
        note        int     note number (0-127)
        velocity    int     note on velocity
    OUT
        None
    """
    # Create new ball with all animation stuff
    if velocity != 0:

        # Material color used by this note
        mat_name = obj.name + "_mat_" + str(midinote_to_note_num[note])
        material = b_dat.materials[mat_name]

        self.last_note_status[0] += 1
        current_ball = self.last_note_status[0]

        # create ball
        obj_col = find_collection(b_con, obj)
        ball_name = obj.name + "_ball_" + str(current_ball)
        ball_obj = add_VBO(
            Type="UVSphere",
            Col=obj_col,
            Name=ball_name,
            Mat=material,
            U_Seg=16,
            V_Seg=16,
            Diameter=1.0,
            Parent=obj.parent
        )

#                ball_obj.data.shade_smooth()
        # Fix his start and end positions to animate movement
        pos_start = mathutils.Vector((0.0, 0.0, 0.0))
        x = 12 - (midinote_to_note_num[note] * 2)
        z = 12 - (midinote_to_octave[note] * 2)
        pos_impact = mathutils.Vector((x, 40.0, z))
        pos_end = mathutils.Vector((x, 45.0, z))
        delay = 50  # to be evaluated following framerate and distance between gun and wall
        ball_obj.location = pos_start
        ball_obj.keyframe_insert(data_path='location', frame=frame - delay)
        ball_obj.location = pos_impact
        ball_obj.keyframe_insert(data_path='location', frame=frame)
        ball_obj.location = pos_end
        ball_obj.keyframe_insert(data_path='location', frame=frame + framerate)

        # add modifier strech for flatten on impact
        mod = ball_obj.modifiers.new(name="flatten", type='SIMPLE_DEFORM')
        mod.deform_method = 'STRETCH'
        mod.deform_axis = 'Y'
        mod.factor = 0
        mod.keyframe_insert(data_path='factor', frame=frame - 3)
        mod.factor = -1
        mod.keyframe_insert(data_path='factor', frame=frame)

        # add metaball for particles system  # For testing one mball for one PS
        # part_name = ball_name + "_particle"
        # add_VBO_mball(
        #     collect=obj_col,
        #     name=part_name,
        #     material=material,
        #     location=(-50, 0, 0),
        #     parent=obj.parent
        # )

        # add particle system to create splash and animate him
        ps = ball_obj.modifiers.new(name='particles', type='PARTICLE_SYSTEM')
        ps = ball_obj.particle_systems
        name_of_ps = obj.name + "_SW_" + str(current_ball)
        ps.active.name = name_of_ps
        # obj_particle_name = obj.name + "_particle_" + str(midinote_to_note_num[note])
        # obj_particle = b_dat.objects[obj_particle_name]
        part_name = obj.name + "_particle_" + str(midinote_to_note_num[note])
        obj_particle = b_dat.objects[part_name]
        ps.active.settings.physics_type = 'FLUID'
        ps.active.settings.name = name_of_ps
        ps.active.settings.render_type = 'OBJECT'
        ps.active.settings.instance_object = obj_particle
        ps.active.settings.count = 500
        ps.active.settings.particle_size = 0.25

        # Be sure to initialize frame_end before frame_start because
        # frame_start can't be greather than frame_end at any time
        ps.active.settings.frame_end = frame + 5
        ps.active.settings.frame_start = frame - 5
        ps.active.settings.lifetime = framerate * 20
        ps.active.settings.emit_from = 'VERT'
        ps.active.settings.use_emit_random = True
        ps.active.settings.fluid.linear_viscosity = 1
        ps.active.settings.damping = 0.2
    else:
        pass

    return None


def Channel_is_PB(self, col_obj, empty_parent, material):
    """
    Instanciate with a channel typed : PB - Paper Ball
    """
    # Create template
    obj_model = add_VBO_pb(
        col_obj,
        col_obj.name + "_template",
        material,
        -50 * self.cf,
        self.idx * self.cf,
        0,
        empty_parent
    )

    current_place = 0
    median_place = self.count_place // 2
    # Duplicate template, one by note
    for x in range(self.min_note, self.max_note + 1):
        if x in self.list_note:
            paperball_name = col_obj.name + "_" + str(x)
            self.note_object[x] = duplicate_linked(
                collect=col_obj,
                name=paperball_name,
                location=((current_place - median_place) * self.cf, 0, 0),
                model=obj_model
            )
        current_place += 1

    self.note_object[128] = obj_model

    return None


def PB_note_evt(self, obj, frame, note, velocity):
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
        PB_note_evt(self, obj, frame - self.curve, note, self.last_note_status[note])
    mod = obj.modifiers[1]
    mod.strength = (velocity / 127) * 5
    mod.keyframe_insert(data_path='strength', frame=frame)
    self.last_note_status[note] = velocity
    return None


def Channel_is_TP(self, col_obj, empty_parent, material):
    """
    Instanciate with a channel typed : TP - Texture Paint
    """
    self.note_object[0] = add_VBO(
        Type="Plane",
        Col=col_obj,
        Name=col_obj.name,
        Mat=material,
        Size=2.0,
        Scale=(4.0, 4.0, 1),
        Parent=empty_parent
    )

    width = 200
    height = 200

    # Create an image texture
    image_object = b_dat.images.new(name=col_obj.name, width=width, height=height)
    # num_pixels = len(image_object.pixels)

    return None


def TP_note_evt(self, obj, frame, note, velocity):
    """ TP = Texture Paint
    Place note_on with Channel object, velocity and keyframe
    IN
        frame       int     Index of frame
        note        int     note number (0-127)
        velocity    int     note on velocity
    OUT
        None
    """
    # To avoid pb slowly grow before the note
    # Aplly it to objet (plane)

    # Paint it with note_evt...
    # x = midinote_to_note_num[note]
    # y = midinote_to_octave[note]
    # num = x * (y + 1)
    # image_object.pixels[num] = 1.0                  # R
    # image_object.pixels[num+1] = random.random()    # G
    # image_object.pixels[num+2] = random.random()    # B
    # image_object.pixels[num+3] = random.random()    # A

    return None


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
        self.note_object = {}           # dictionnary {note:object}, used by animation
        self.last_note_status = {}      # dictionnary {note:status}, used by animation
        self.last_note_status_FS = {}   # same as last_note_status but for FS vizualisation Target
        self.min_note = 128             # lower note of the channel, mean the first note
        self.max_note = 0               # highest note of the channel, mean the last note

        # Internal use for 3D
        self.count_place = 0            # count of places used in channel (with note or not)
        self.cf = 2.5                   # localisation coef (!)
        self.curve = 1                  # mean the delta number of frame between evt change

        """ ======= Main of __init__ ========================================== """

        # initialize note status
        for note in self.list_note:
            self.last_note_status[note] = 0

        # If no note in this channel then return without creating any object
        # Because no event will be treated later
        # Code here maybe for SMF 2 ?
        if self.locked == "True":
            return None

        print('Generate Channel {}: {}'.format(self.idx, self.name))
        if not self.list_note:
            self.min_note = 0
            self.max_note = 0
        else:
            self.min_note = min(self.list_note)
            self.max_note = max(self.list_note)

        self.count_place = (self.max_note - self.min_note) + 1
        self.curve = framerate // 8

        # Create cubes from only used notes
        col_name = self.visual_type + '_' + str(self.idx)
        # Create collection for this channel
        col_obj = create_collection(col_name, new_collec, delete=True)
        # Create the empty parent off all cubes
        empty_parent_name = col_name + '_Parent'
        empty_parent = add_empty(col_obj, empty_parent_name, (0, self.idx * self.cf, 0))
        # Create Default material with random color
        if self.visual_type != "LT":
            material = Create_material_simple(col_name + "_mat", 0.0, 0.0, 0.0, True)

        # All objects are created the most centered as possible
        # Type BG = Bargraphs
        if self.visual_type == "BG":
            Channel_is_BG(self, col_obj, empty_parent, material)
        # Type GD = Grid
        elif self.visual_type == "GD":
            Channel_is_GD(self, col_obj, empty_parent, material)
        # Type LT = Light
        elif self.visual_type == "LT":
            Channel_is_LT(self, col_obj, empty_parent)
        # Type FT = Fountain
        elif self.visual_type == "FT":
            Channel_is_FT(self, col_obj, empty_parent, material)
        # Type FS = Fountain Solo
        elif self.visual_type == "FS":
            Channel_is_FS(self, col_obj, empty_parent, material)
        # Type SW = Slpash Wall
        elif self.visual_type == "SW":
            Channel_is_SW(self, col_obj, empty_parent, material)
        # Type PB = Paper Ball
        elif self.visual_type == "PB":
            Channel_is_PB(self, col_obj, empty_parent, material)
        # Type TP = Texture Paint
        elif self.visual_type == "TP":
            Channel_is_TP(self, col_obj, empty_parent, material)

        self.note_object[128]['modulation_wheel'] = 0
        self.note_object[128].keyframe_insert(data_path="""["modulation_wheel"]""", frame=0)
        self.note_object[128]['pitchwheel'] = 0
        self.note_object[128].keyframe_insert(data_path="""["pitchwheel"]""", frame=0)
        self.note_object[128]['aftertouch'] = 0
        self.note_object[128].keyframe_insert(data_path="""["aftertouch"]""", frame=0)
        self.note_object[128]['pan'] = 0
        self.note_object[128].keyframe_insert(data_path="""["pan"]""", frame=0)
        self.note_object[128]['expression'] = 0
        self.note_object[128].keyframe_insert(data_path="""["expression"]""", frame=0)
        self.note_object[128]['volume'] = 0
        self.note_object[128].keyframe_insert(data_path="""["volume"]""", frame=0)
        self.note_object[128]['s_pedal'] = 0
        self.note_object[128].keyframe_insert(data_path="""["s_pedal"]""", frame=0)

        return None

    # Add an new midi event related to the channel
    def add_note_evt(self, evt, frame, note, velocity):
        """
        React to note event
        IN
            evt         'note_on' or 'note_off' - Not really used for now
            frame       frame number
            note        note number
            velocity    velocity
        OUT
            None
        """
        # Main - add_note_evt - For now suppose all type evt is note_on or note_off

        # Dispatch by type of object
        # Deal with mono object for all notes or multi objects each by note
        if self.visual_type in ("FS", "SW", "TP"):
            obj = self.note_object[0]
        else:
            obj = self.note_object[note]

        # if object doesn't exist, it's probabilly a XX model
        # if obj_name not in b_dat.objects:
        #     return None

        if self.locked == "True":
            return None

        # Animate if needed directly the object
        if self.animate == "True":

            # Animate always custom properties of object
            obj['velocity'] = velocity
            obj.keyframe_insert(data_path="""["velocity"]""", frame=frame)

            if self.visual_type == "BG":
                BG_note_evt(self, obj, frame, note, velocity)
            elif self.visual_type == "GD":
                GD_note_evt(self, obj, frame, note, velocity)
            elif self.visual_type == "LT":
                LT_note_evt(self, obj, frame, note, velocity)
            elif self.visual_type == "FT":
                FT_note_evt(self, obj, frame, note, velocity)
            elif self.visual_type == "FS":
                FS_note_evt(self, obj, frame, note, velocity)
            elif self.visual_type == "SW":
                SW_note_evt(self, obj, frame, note, velocity)
            elif self.visual_type == "PB":
                PB_note_evt(self, obj, frame, note, velocity)
            elif self.visual_type == "TP":
                TP_note_evt(self, obj, frame, note, velocity)

        return None

    # Add an new midi event related to the channel
    def add_pitchwheel_evt(self, frame, pitch):
        """
        React to pitchwheel event
        IN
            frame       frame number
            pitch       current pitch
        OUT
            None
        """
        obj = self.note_object[128]

        # Animate custom properties of object
        obj['pitchwheel'] = pitch
        obj.keyframe_insert(data_path="""["pitchwheel"]""", frame=frame)

        return None

    # Add an new midi event related to the channel
    def add_aftertouch_evt(self, frame, value):
        """
        React to aftertouch event
        IN
            frame       frame number
            value       current value
        OUT
            None
        """
        obj = self.note_object[128]

        # Animate custom properties of object
        obj['aftertouch'] = value
        obj.keyframe_insert(data_path="""["aftertouch"]""", frame=frame)

        return None

    # Add an new midi event related to the channel
    def add_ctrlchange_evt(self, frame, control, value):
        """
        React to control change event
        IN
            frame       frame number
            value       current value
        OUT
            None
        """
        obj = self.note_object[128]

        # modulation wheel = 1
        if control == 1:
            # Animate modulation wheel
            obj['modulation_wheel'] = value
            obj.keyframe_insert(data_path="""["modulation_wheel"]""", frame=frame)
        # channel volume = 7
        if control == 7:
            # Animate volume
            obj['volume'] = value
            obj.keyframe_insert(data_path="""["volume"]""", frame=frame)
        # Pan = 10
        elif control == 10:
            # Animate pan
            obj['pan'] = value
            obj.keyframe_insert(data_path="""["pan"]""", frame=frame)
        # Expression = 11
        elif control == 11:
            # Animate Expression
            obj['expression'] = value
            obj.keyframe_insert(data_path="""["expression"]""", frame=frame)
        # sustain pedal = 64
        elif control == 64:
            # Animate Sustain Pedal
            obj['s_pedal'] = value
            obj.keyframe_insert(data_path="""["s_pedal"]""", frame=frame)

        return None


""" ========================= MAIN ========================= """

time_start = time.time()

# Clear system console
os.system("cls")

# Create the principal collection if not exist, mean Midi To Blender
col_name = "MTB"
new_collec = create_collection(col_name, b_con.scene.collection, delete=False)

# path and name of midi file - temporary => replaced when this become an add-on
# path = "C:\\tmp\\MTB\\data"
path = "D:\\OneDrive\\Blog\\MTB extras\\data"
filename = "Melody 01"
# If use_channel = True then manage separate channel as usual, wherever the tracks where the channel event are
# If use_channel = False then MIDI File don't use channel info and we use 1 track = 1 channel
use_channel = False
filemid = path + "\\" + filename + ".mid"
fileaudio = path + "\\" + filename + ".mp3"
filejson = path + "\\" + filename + ".json"
filelog = path + "\\" + filename + ".log"

# Open log file for append
# flog = open(filelog, "w+")

# Open MIDIFile with the module MIDO
mid = MidiFile(filemid)
print("Midi type = "+str(mid.type))

# type = 0 - (single track): all messages are in one track and use the same tempo and start at the same time
# type = 1 - (synchronous): all messages are in separated tracks and use the same tempo and start at the same time
# type = 2 - (asynchronous): each track is independent of the others for tempo and for start - not yet supported
if (mid.type == 2):
    raise RuntimeError("Only type 0 or 1, type 2 is not yet supported")

""" STEP 1 - Prepare """

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
octave = {0: "C", 1: "C#", 2: "D", 3: "D#", 4: "E", 5: "F", 6: "F#", 7: "G", 8: "G#", 9: "A", 10: "A#", 11: "B"}

# To convert easily from midi notation to name of note
midinote_to_note_alpha = {
 0:   "C",   1: "C#",   2: "D",   3: "D#",   4: "E",   5: "F",   6: "F#",   7: "G",   8: "G#",   9: "A",  10: "A#",  11: "B",
 12:  "C",  13: "C#",  14: "D",  15: "D#",  16: "E",  17: "F",  18: "F#",  19: "G",  20: "G#",  21: "A",  22: "A#",  23: "B",
 24:  "C",  25: "C#",  26: "D",  27: "D#",  28: "E",  29: "F",  30: "F#",  31: "G",  32: "G#",  33: "A",  34: "A#",  35: "B",
 36:  "C",  37: "C#",  38: "D",  39: "D#",  40: "E",  41: "F",  42: "F#",  43: "G",  44: "G#",  45: "A",  46: "A#",  47: "B",
 48:  "C",  49: "C#",  50: "D",  51: "D#",  52: "E",  53: "F",  54: "F#",  55: "G",  56: "G#",  57: "A",  58: "A#",  59: "B",
 60:  "C",  61: "C#",  62: "D",  63: "D#",  64: "E",  65: "F",  66: "F#",  67: "G",  68: "G#",  69: "A",  70: "A#",  71: "B",
 72:  "C",  73: "C#",  74: "D",  75: "D#",  76: "E",  77: "F",  78: "F#",  79: "G",  80: "G#",  81: "A",  82: "A#",  83: "B",
 84:  "C",  85: "C#",  86: "D",  87: "D#",  88: "E",  89: "F",  90: "F#",  91: "G",  92: "G#",  93: "A",  94: "A#",  95: "B",
 96:  "C",  97: "C#",  98: "D",  99: "D#", 100: "E", 101: "F", 102: "F#", 103: "G", 104: "G#", 105: "A", 106: "A#", 107: "B",
 108: "C", 109: "C#", 110: "D", 111: "D#", 112: "E", 113: "F", 114: "F#", 115: "G", 116: "G#", 117: "A", 118: "A#", 119: "B",
 120: "C", 121: "C#", 122: "D", 123: "D#", 124: "E", 125: "F", 126: "F#", 127: "G"
}

# To convert easily from midi notation to number of note
midinote_to_note_num = {
 0:   0,   1: 1,   2: 2,   3: 3,   4: 4,   5: 5,   6: 6,   7: 7,   8: 8,   9: 9,  10: 10,  11: 11,
 12:  0,  13: 1,  14: 2,  15: 3,  16: 4,  17: 5,  18: 6,  19: 7,  20: 8,  21: 9,  22: 10,  23: 11,
 24:  0,  25: 1,  26: 2,  27: 3,  28: 4,  29: 5,  30: 6,  31: 7,  32: 8,  33: 9,  34: 10,  35: 11,
 36:  0,  37: 1,  38: 2,  39: 3,  40: 4,  41: 5,  42: 6,  43: 7,  44: 8,  45: 9,  46: 10,  47: 11,
 48:  0,  49: 1,  50: 2,  51: 3,  52: 4,  53: 5,  54: 6,  55: 7,  56: 8,  57: 9,  58: 10,  59: 11,
 60:  0,  61: 1,  62: 2,  63: 3,  64: 4,  65: 5,  66: 6,  67: 7,  68: 8,  69: 9,  70: 10,  71: 11,
 72:  0,  73: 1,  74: 2,  75: 3,  76: 4,  77: 5,  78: 6,  79: 7,  80: 8,  81: 9,  82: 10,  83: 11,
 84:  0,  85: 1,  86: 2,  87: 3,  88: 4,  89: 5,  90: 6,  91: 7,  92: 8,  93: 9,  94: 10,  95: 11,
 96:  0,  97: 1,  98: 2,  99: 3, 100: 4, 101: 5, 102: 6, 103: 7, 104: 8, 105: 9, 106: 10, 107: 11,
 108: 0, 109: 1, 110: 2, 111: 3, 112: 4, 113: 5, 114: 6, 115: 7, 116: 8, 117: 9, 118: 10, 119: 11,
 120: 0, 121: 1, 122: 2, 123: 3, 124: 4, 125: 5, 126: 6, 127: 7
}

# To convert easily from midi notation to octave of note

midinote_to_octave = {
 0:   0,    1: 0,    2: 0,    3: 0,    4: 0,    5: 0,    6: 0,    7: 0,   8: 0,   9: 0,  10: 0,  11: 0,
 12:  1,   13: 1,   14: 1,   15: 1,   16: 1,   17: 1,   18: 1,   19: 1,  20: 1,  21: 1,  22: 1,  23: 1,
 24:  2,   25: 2,   26: 2,   27: 2,   28: 2,   29: 2,   30: 2,   31: 2,  32: 2,  33: 2,  34: 2,  35: 2,
 36:  3,   37: 3,   38: 3,   39: 3,   40: 3,   41: 3,   42: 3,   43: 3,  44: 3,  45: 3,  46: 3,  47: 3,
 48:  4,   49: 4,   50: 4,   51: 4,   52: 4,   53: 4,   54: 4,   55: 4,  56: 4,  57: 4,  58: 4,  59: 4,
 60:  5,   61: 5,   62: 5,   63: 5,   64: 5,   65: 5,   66: 5,   67: 5,  68: 5,  69: 5,  70: 5,  71: 5,
 72:  6,   73: 6,   74: 6,   75: 6,   76: 6,   77: 6,   78: 6,   79: 6,  80: 6,  81: 6,  82: 6,  83: 6,
 84:  7,   85: 7,   86: 7,   87: 7,   88: 7,   89: 7,   90: 7,   91: 7,  92: 7,  93: 7,  94: 7,  95: 7,
 96:  8,   97: 8,   98: 8,   99: 8,  100: 8,  101: 8,  102: 8,  103: 8, 104: 8, 105: 8, 106: 8, 107: 8,
 108: 9,  109: 9,  110: 9,  111: 9,  112: 9,  113: 9,  114: 9,  115: 9, 116: 9, 117: 9, 118: 9, 119: 9,
 120: 10, 121: 10, 122: 10, 123: 10, 124: 10, 125: 10, 126: 10, 127: 10
}

# Set pulsation per quarter note (ppq)
# Mean the number of pulsation per round note / 4 = black note
ppq = mid.ticks_per_beat
print("PPQ resolution = " + str(ppq))

# Init Max frame number founded for all channel, mean the end of animation
max_num_frame = 0

# take the framerate directly from blender
framerate = b_con.scene.render.fps

# For type 0 and 1 midifile
# instanciate single time_map
time_map = Tempo_Class(mid.tracks[0])
print("Tempo count = " + str(len(time_map.tempo_map)))

""" STEP 2 - Creating the 3D channel vizualisation objects """

# Dictionnary of Channel <= receive object Channel_Class
ChannelList = {}

l_channel = []
channel_name = {}
l_channel_notes = {}
# Fill l_channel with all channels found in all tracks
# and set some channel parameters
if use_channel:
    for current_track, track in enumerate(mid.tracks):
        for msg in track:
            if msg.type == ('note_on'):
                if msg.channel not in l_channel:
                    l_channel.append(msg.channel)
                    channel_name[msg.channel] = track.name
                    l_channel_notes[msg.channel] = []
                if msg.note not in l_channel_notes[msg.channel]:
                    l_channel_notes[msg.channel].append(msg.note)
    l_channel = sorted(l_channel)
else:
    for current_track, track in enumerate(mid.tracks):
        l_channel.append(current_track)
        channel_name[current_track] = track.name
        l_channel_notes[current_track] = []
        for msg in track:
            if msg.type == ('note_on'):
                if msg.note not in l_channel_notes[current_track]:
                    l_channel_notes[current_track].append(msg.note)
    l_channel = sorted(l_channel)

# Create one vizualisation object per channel
for cur_chan in l_channel:
    l_channel_notes[cur_chan] = sorted(l_channel_notes[cur_chan])
    if jsoninit:
        mtb_channel = {}
        mtb_channel["Channel"] = cur_chan
        mtb_channel["Locked"] = "False"
        mtb_channel["Name"] = channel_name[cur_chan]
        mtb_channel["Type"] = "BG"
        mtb_channel["Template"] = ""
        mtb_channel["Animate"] = "True"
        mtb_data.append(mtb_channel)
        ChannelList[cur_chan] = Channel_Class(cur_chan, l_channel_notes[cur_chan], channel_name[cur_chan], mtb_channel)
    else:
        mtb_channel = search_channel_in_mtb_data(cur_chan)
        ChannelList[cur_chan] = Channel_Class(cur_chan, l_channel_notes[cur_chan], channel_name[cur_chan], mtb_channel)

# Save json file if initialising
if jsoninit:
    with open(filejson, 'w') as f:
        f.write(json.dumps(mtb_data, indent=4))

# flog.write("channel;type;note;velocity;time_ticks;time_in_ticks_cumul;current_tempo;time_in_sec;time_in_sec_Cumul;current_frame\n")

current_frame = 0
""" STEP 3 - Main LOOP on midifile track for all events """
for current_track, track in enumerate(mid.tracks):
    print('Parse track {}: {} evt(s)'.format(current_track, len(track)))

#   Initialize the time cumul in ticks and second for the track
    time_in_ticks_cumul = 0

    # Parse midi message for the current track
    for msg in track:

        if msg.type == "sysex":
            continue

        time_in_ticks_cumul += msg.time

        if msg.is_meta:
            continue

        # Check if note_on with velocity 0 will become note_off
        if (msg.type == 'note_on') and (msg.velocity == 0):
            msgtype = 'note_off'
        else:
            msgtype = msg.type

        # Check real channel following the value of lag use_channel
        if use_channel:
            current_channel = msg.channel
        else:
            current_channel = current_track

        # If note_on or note_off event
        if msgtype in ('note_on', 'note_off'):
            # Evaluate the current frame following Tempo MAP
            current_frame = time_map.frame(time_in_ticks_cumul)
            # flog.write(str(msg.channel) + ";" + msgtype + ";" + str(msg.note) + ";" + str(msg.velocity) + ";" + str(msg.time) + ";" + str(time_in_ticks_cumul) + ";" + str(current_frame)+ "\n")
            velocity = msg.velocity * (msgtype == 'note_on')  # to avoid note_off with velocity != 0
            ChannelList[current_channel].add_note_evt(msgtype, current_frame, msg.note, velocity)
        # if pitchwheel event
        elif msg.type == 'pitchwheel':
            ChannelList[current_channel].add_pitchwheel_evt(current_frame, msg.pitch)
        elif msg.type == 'aftertouch':
            ChannelList[current_channel].add_aftertouch_evt(current_frame, msg.value)
        elif msg.type == 'control_change':
            # print("ctrlchg " + str(current_frame) + " " + str(msg.control) + " " + str(msg.value))
            ChannelList[current_channel].add_ctrlchange_evt(current_frame, msg.control, msg.value)
        else:
            print(msg.type)

        # here, later, how to deal with other msg type like
        # control_change
        #   sustain pedal (64), stop all notes (123)
        # program_change
        # and so on...

    # Manage the last frame number : mean the end of animation
    if current_frame > max_num_frame:
        max_num_frame = current_frame

# Add one second at the end of animation
b_scn.frame_end = max_num_frame + framerate

print("Script Finished: %.2f sec" % (time.time() - time_start))
# flog.close()

# End of script - Enjoy
