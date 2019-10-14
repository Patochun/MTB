********************************************************************
Midi To Blend Project
Blender version = 2.8
Author = Patrick Mauger
Web Site = docouatzat.com
Mail = docouatzat@gmail.com

Licence used = Creative Commons CC BY
Check licence here : https://creativecommons.org

********************************************************************

The purpose of this script is to convert Midi file to 3D vizualisation into Blender

Type of MIDI file accepted = 0 and 1. The type 2 is not accepted yet. Maybe later.


Type of visual Blender object (VBO) are :
-----------------------------------------

BG - Bargraphs

1 bar per note
It's the default VBO

GD - Grid

12x11 faces used, one per note

LT - Lights

1 light per note. Color randomly choosed

FT - Fountain type

Particules from small icosphere mimic a fountain

FS - Fountain Solo

Particules one by note

SW - Fountain type II

PB - Paperball

TP - Texture Paint



Hierarchy :
-----------

All objects created are grouped into a master collection named MTB (mean MIDI To Blender)
Each VBO is grouped into a collection named from type of VBO and track number
Sample collection name for Track 2 associated with grid object (GD) = GD_2
Into each VBO collection we have an empty object who are the parent of all objects into this collection
And finally each note is figured by one object

Grid is a special case. Grid is only one grid object and notes are figured by faces. Theses faces are hooked.
So each note is figured by one hook.

At each execution of script the master collection MTB is used


Workflow :
----------

-   First of all, because MTB script use the framerate setting in blender, you must set the propper value
if needed. In context/Output.

-   You must have the MIDI file (type 0 or 1) ready and the MP3 linked

-   Start the script for the first time. If everything is ok, you must have a blender with channel figured by range of cubes.
When you launch animation, all bargraphs are animated accordingly with MIDI file and of course with the MP3 file.

-   Now you understand how channel are located and you can choose different VBO. Just edit the json file linked to the MIDI file
and set appropriate VBO.

- You can launch the script again. Everything is cleaned and created again following your recommandations.

- Place objects as you want and change color for exemple. Then lock the channel modified. To do this, just edit json file and set
True to the value locked. Now only channel not locked will be created again

- You can change object template and use your own template. Create it in blencer, name it and set this name into template value
in json file.

- Maybe you want manage yourself the animation of channel object. Set Animate value to False in json file. And now objects are
not animated anymore, just custom properties does. You can animate everything you want with use of driver (or AN) and custom properties.


Notes :
-------

note : MIDI_to_Blender use the Frame Rate configured into Blender (Context Output). If the music is fast some
artefacts like slowly growing object may appears. To avoid this behavior, increase the Blender Frame Rate.
60 FPS offer a good MIDI music to 3D resolution.

Note : file audio mp3 is imported if exists (in same directory than the MIDI file) with a sound value of 0.025 (relatively quiet). It's up to you to
adjust the gain later. The file audio must have the same prefix name than the MIDI file.


Format of json parameter file :

[
    {
        "Channel": <ID Number of channel>,
        "Name": "<Name of track, most case is the instrument name>",
        "Type": "<Type of VBO>",
        "Template": "<Name of object Template, not mandatory",
        "Animate": "<True or False>"
    },
    {
        "Channel": 3,
        "Name": "VOICES",
        "Type": "XX",
        "Template": "",
        "Animate": "True"
    },

Type XX, mean you don't want any object. In this case this channel is purely ignored and Animate value doesn't matter like template.


If Animate = False, then objects for notes are created, with template if provided, and not animated. Only custom properties
are setted and animated.

To use custom properties for example :

- Add driver to property you want to animate
    - For example Add a modifier simple deform, type stretch, Axis Z
    - On deform factor ctrl+D or context menu add driver
    - Driver type = Scripted expression
    - Expression = self['velocity'] / 4
    - Check the radio button 'self'
    - And all is good, object become animated by driver apply on variable velocity (your animated custom property)

velocity and aftertouch are apply to each object note
pitchbend is apply to channel, so is apply to object model
